package br.fiap.pontofalante.transporte;

import br.fiap.pontofalante.sistema.ErroApi;
import br.fiap.pontofalante.sistema.PfProps;
import br.fiap.pontofalante.transporte.Modelos.DadosPrevisao;
import br.fiap.pontofalante.transporte.Modelos.Fonte;
import br.fiap.pontofalante.transporte.Modelos.Linha;
import br.fiap.pontofalante.transporte.Modelos.LinhaNoPonto;
import br.fiap.pontofalante.transporte.Modelos.Ponto;
import br.fiap.pontofalante.transporte.Modelos.PrevisoesPonto;
import br.fiap.pontofalante.transporte.Modelos.RespostaItinerario;
import br.fiap.pontofalante.transporte.Modelos.RespostaLinhas;
import br.fiap.pontofalante.transporte.Modelos.RespostaLinhasDoPonto;
import br.fiap.pontofalante.transporte.Modelos.RespostaPontos;
import br.fiap.pontofalante.transporte.Modelos.SentidoLinha;
import br.fiap.pontofalante.transporte.RedeGtfs.Parada;
import br.fiap.pontofalante.transporte.RedeGtfs.ParadaEncontrada;
import br.fiap.pontofalante.transporte.RedeGtfs.Viagem;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.time.Clock;
import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.List;

/**
 * Escolhe a origem dos dados (real ou demonstração) e monta as respostas públicas.
 *
 * No modo real, a busca de pontos usa o cadastro oficial (GTFS, em {@link RedeGtfs}) porque a busca de paradas da
 * Olho Vivo só enxerga cerca de 360 paradas com nome e devolve todas elas para qualquer número. Previsões continuam
 * vindo só da Olho Vivo.
 */
@Service
public class TransporteService {
    static final int LIMITE_RESULTADOS = 20;
    private final PfProps props;
    private final OlhoVivoProvider olhoVivo;
    private final DemoProvider demo;
    private final Clock relogio;
    private final RedeGtfs rede;

    public TransporteService(PfProps props, OlhoVivoProvider olhoVivo, DemoProvider demo, Clock relogio) {
        this(props, olhoVivo, demo, relogio, new RedeGtfs());
    }

    @Autowired
    public TransporteService(PfProps props, OlhoVivoProvider olhoVivo, DemoProvider demo, Clock relogio, RedeGtfs rede) {
        this.props = props;
        this.olhoVivo = olhoVivo;
        this.demo = demo;
        this.relogio = relogio;
        this.rede = rede;
    }

    /** modo=demo força a demonstração; sem token configurado, auto também é demonstração. */
    public ProvedorTransporte escolher(String modo) {
        if (modo != null && !modo.isBlank() && !modo.equalsIgnoreCase("auto") && !modo.equalsIgnoreCase("demo")) {
            throw ErroApi.requisicaoInvalida("O modo deve ser auto ou demo.");
        }
        boolean forcaDemo = "demo".equalsIgnoreCase(modo);
        return forcaDemo || !props.temTokenSptrans() ? demo : olhoVivo;
    }

    public RedeGtfs rede() {
        return rede;
    }

    /** Verdadeiro quando a busca usa o cadastro oficial (modo real com o índice carregado). */
    public boolean usaCadastro(String modo) {
        return escolher(modo).fonte() != Fonte.SIMULADO && rede.disponivel();
    }

    public PrevisoesPonto previsoes(long codigo, String modo) {
        ProvedorTransporte provedor = escolher(modo);
        DadosPrevisao d = provedor.previsoes(codigo);
        boolean simulado = provedor.fonte() == Fonte.SIMULADO;
        Ponto ponto = d.ponto();
        if (!simulado && rede.disponivel()) {
            // A Olho Vivo devolve nome vazio para a maioria das paradas; o cadastro tem nome e referência.
            Parada p = rede.parada(codigo);
            if (p != null && (ponto.nome() == null || ponto.nome().isBlank())) {
                ponto = new Ponto(codigo, p.nome(), p.referencia().isBlank() ? ponto.endereco() : p.referencia(),
                        p.latitude(), p.longitude(), Fonte.OLHO_VIVO, rede.letreirosDaParada(codigo), null);
            }
        }
        String frase = FraseFalada.montar(ponto.nome(), d.onibus(), simulado);
        return new PrevisoesPonto(ponto, provedor.fonte(), "PREVISAO", d.horarioReferencia(),
                OffsetDateTime.now(relogio), d.onibus(), frase);
    }

    // ---------- busca de pontos ----------

    public RespostaPontos buscarPontos(String termo, String modo) {
        ProvedorTransporte provedor = escolher(modo);
        if (provedor.fonte() == Fonte.SIMULADO || !rede.disponivel()) {
            return new RespostaPontos(provedor.fonte(), provedor.buscarPontos(termo));
        }
        String digitos = termo.replaceAll("[\\s.\\-]", "");
        if (digitos.length() >= 4 && digitos.chars().allMatch(Character::isDigit)) {
            return porCodigo(digitos);
        }
        List<Ponto> pontos = new ArrayList<>();
        for (ParadaEncontrada e : rede.buscarParadas(termo, LIMITE_RESULTADOS)) {
            pontos.add(ponto(e.parada(), null));
        }
        if (pontos.isEmpty()) {
            return new RespostaPontos(Fonte.OLHO_VIVO, pontos,
                    "Não encontrei ponto com esse nome ou endereço. Tente só o nome da rua, o código da placa do "
                            + "ponto ou use a localização para ver os pontos perto de você.");
        }
        return new RespostaPontos(Fonte.OLHO_VIVO, pontos, avisoDeNumero(termo, pontos.get(0)));
    }

    /** Código digitado: correspondência exata; nunca uma lista de pontos sem relação com o número. */
    private RespostaPontos porCodigo(String digitos) {
        if (digitos.length() <= 12) {
            long codigo = Long.parseLong(digitos);
            Parada exata = rede.parada(codigo);
            if (exata != null) {
                return new RespostaPontos(Fonte.OLHO_VIVO, List.of(ponto(exata, null)));
            }
            try {
                // Código fora do cadastro: confirma na Olho Vivo antes de dizer que não existe.
                Ponto real = olhoVivo.previsoes(codigo).ponto();
                String nome = real.nome() == null || real.nome().isBlank() ? "Ponto " + codigo : real.nome();
                return new RespostaPontos(Fonte.OLHO_VIVO, List.of(new Ponto(codigo, nome, real.endereco(),
                        real.latitude(), real.longitude(), Fonte.OLHO_VIVO)));
            } catch (TransporteIndisponivelException e) {
                // Falha da SPTrans não é prova de que o código não existe.
                return new RespostaPontos(Fonte.OLHO_VIVO, List.of(), "O código " + digitos
                        + " não está no cadastro de pontos e a SPTrans não respondeu agora para confirmar. "
                        + "Tente de novo em instantes.");
            } catch (ErroApi e) {
                // código inexistente: segue para o código incompleto
            }
        }
        List<Ponto> parecidos = new ArrayList<>();
        if (digitos.length() >= 6) {
            for (Parada p : rede.paradasPorPrefixoDeCodigo(digitos, 10)) {
                parecidos.add(ponto(p, null));
            }
        }
        return new RespostaPontos(Fonte.OLHO_VIVO, parecidos, parecidos.isEmpty()
                ? "Não existe ponto com o código " + digitos + ". Confira o número na placa do ponto ou busque pelo nome da rua."
                : "Não existe ponto com o código " + digitos + ". Estes códigos começam com os mesmos números.");
    }

    private static String avisoDeNumero(String termo, Ponto primeiro) {
        java.util.regex.Matcher m = java.util.regex.Pattern.compile("\\b(\\d{1,6})\\b").matcher(termo);
        if (!m.find()) {
            return null;
        }
        return primeiro.nome().matches(".*\\b" + m.group(1) + "\\b.*") ? null
                : "Não há ponto exatamente no número " + m.group(1) + ". Estes são os pontos da mesma via com numeração mais próxima.";
    }

    public RespostaPontos pontosProximos(double lat, double lon, int raioMetros, String modo) {
        ProvedorTransporte provedor = escolher(modo);
        if (provedor.fonte() == Fonte.SIMULADO || !rede.disponivel()) {
            return new RespostaPontos(provedor.fonte(), List.of(),
                    "A busca por proximidade só funciona com os dados reais da SPTrans.");
        }
        if (lat < -24.2 || lat > -23.1 || lon < -47.2 || lon > -46.0) {
            return new RespostaPontos(Fonte.OLHO_VIVO, List.of(),
                    "Essa localização fica fora da área atendida pelos ônibus municipais de São Paulo.");
        }
        List<Ponto> pontos = new ArrayList<>();
        for (ParadaEncontrada e : rede.proximas(lat, lon, raioMetros, LIMITE_RESULTADOS)) {
            pontos.add(ponto(e.parada(), e.distanciaMetros()));
        }
        return new RespostaPontos(Fonte.OLHO_VIVO, pontos, pontos.isEmpty()
                ? "Não há ponto de ônibus a até " + raioMetros + " metros dessa localização." : null);
    }

    private Ponto ponto(Parada p, Integer distancia) {
        return new Ponto(p.codigo(), p.nome(), p.referencia().isBlank() ? null : p.referencia(), p.latitude(),
                p.longitude(), Fonte.GTFS_SPTRANS, rede.letreirosDaParada(p.codigo()), distancia);
    }

    // ---------- linhas ----------

    public RespostaLinhas buscarLinhas(String termo, String modo) {
        ProvedorTransporte provedor = escolher(modo);
        if (provedor.fonte() == Fonte.SIMULADO) {
            return new RespostaLinhas(provedor.fonte(), provedor.buscarLinhas(termo));
        }
        List<Linha> linhas = List.of();
        boolean numero = !termo.isBlank() && Character.isDigit(termo.trim().charAt(0));
        if (numero || !rede.disponivel()) {
            try {
                linhas = provedor.buscarLinhas(termo);
            } catch (TransporteIndisponivelException e) {
                if (!rede.disponivel()) {
                    throw e;
                }
            }
        }
        if (linhas.isEmpty() && rede.disponivel()) {
            // Nome ou destino ("paulista", "terminal santo amaro"): a Olho Vivo só busca pelo letreiro.
            List<Linha> doCadastro = new ArrayList<>();
            for (Viagem v : rede.buscarLinhas(termo, LIMITE_RESULTADOS * 2)) {
                String[] pontas = v.nomeLinha().split(" - ", 2);
                doCadastro.add(new Linha(null, v.letreiro(), v.sentido(), pontas[0],
                        pontas.length > 1 ? pontas[1] : null, v.destino(), false));
            }
            linhas = doCadastro;
        }
        return new RespostaLinhas(provedor.fonte(), linhas);
    }

    public RespostaItinerario itinerario(String letreiro, String modo) {
        if (!usaCadastro(modo)) {
            return new RespostaItinerario(escolher(modo).fonte(), letreiro, List.of(),
                    "O itinerário das linhas só está disponível com os dados reais da SPTrans.");
        }
        List<Viagem> vs = rede.viagensDaLinha(letreiro);
        if (vs.isEmpty()) {
            List<String> opcoes = rede.letreirosPorNumero(letreiro);
            throw new ErroApi(org.springframework.http.HttpStatus.NOT_FOUND, "LINHA_NAO_ENCONTRADA", opcoes.isEmpty()
                    ? "Não encontrei a linha " + letreiro + " no cadastro da SPTrans."
                    : "Há mais de uma linha com esse número: " + String.join(", ", opcoes.subList(0, Math.min(8, opcoes.size()))) + ".");
        }
        List<SentidoLinha> sentidos = new ArrayList<>();
        for (Viagem v : vs) {
            List<Ponto> paradas = new ArrayList<>();
            for (long id : v.paradas()) {
                Parada p = rede.parada(id);
                if (p != null) {
                    paradas.add(new Ponto(p.codigo(), p.nome(), p.referencia().isBlank() ? null : p.referencia(),
                            p.latitude(), p.longitude(), Fonte.GTFS_SPTRANS));
                }
            }
            sentidos.add(new SentidoLinha(v.letreiro(), v.sentido(), v.destino(), v.nomeLinha(), paradas));
        }
        return new RespostaItinerario(Fonte.GTFS_SPTRANS, vs.get(0).letreiro(), sentidos, null);
    }

    public RespostaLinhasDoPonto linhasDoPonto(long codigo, String modo) {
        if (!usaCadastro(modo)) {
            return new RespostaLinhasDoPonto(escolher(modo).fonte(), codigo, List.of(),
                    "A lista de linhas do ponto só está disponível com os dados reais da SPTrans.");
        }
        List<LinhaNoPonto> linhas = new ArrayList<>();
        for (Viagem v : rede.viagensDaParada(codigo)) {
            linhas.add(new LinhaNoPonto(v.letreiro(), v.sentido(), v.destino(), v.nomeLinha()));
        }
        linhas.sort(java.util.Comparator.comparing(LinhaNoPonto::letreiro));
        return new RespostaLinhasDoPonto(Fonte.GTFS_SPTRANS, codigo, linhas,
                linhas.isEmpty() ? "Este ponto não aparece no cadastro de itinerários da SPTrans." : null);
    }
}

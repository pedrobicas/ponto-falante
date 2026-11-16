package br.fiap.pontofalante.embarque;

import br.fiap.pontofalante.embarque.EmbarqueDtos.AlteracaoFavorito;
import br.fiap.pontofalante.embarque.EmbarqueDtos.Conferencia;
import br.fiap.pontofalante.embarque.EmbarqueDtos.Desfecho;
import br.fiap.pontofalante.embarque.EmbarqueDtos.Favorito;
import br.fiap.pontofalante.embarque.EmbarqueDtos.Indicadores;
import br.fiap.pontofalante.embarque.EmbarqueDtos.LinhaEscolhida;
import br.fiap.pontofalante.embarque.EmbarqueDtos.NovaSessao;
import br.fiap.pontofalante.embarque.EmbarqueDtos.NovoFavorito;
import br.fiap.pontofalante.embarque.EmbarqueDtos.Sessao;
import br.fiap.pontofalante.embarque.EmbarqueDtos.Situacao;
import br.fiap.pontofalante.embarque.EmbarqueRepositorios.ConferenciaVisaoRepository;
import br.fiap.pontofalante.embarque.EmbarqueRepositorios.FavoritoEmbarqueRepository;
import br.fiap.pontofalante.embarque.EmbarqueRepositorios.SessaoEmbarqueRepository;
import br.fiap.pontofalante.embarque.Entidades.ConferenciaVisao;
import br.fiap.pontofalante.embarque.Entidades.FavoritoEmbarque;
import br.fiap.pontofalante.embarque.Entidades.SessaoEmbarque;
import br.fiap.pontofalante.sistema.ErroApi;
import br.fiap.pontofalante.transporte.FraseFalada;
import br.fiap.pontofalante.transporte.Modelos.Fonte;
import br.fiap.pontofalante.transporte.Modelos.OnibusPrevisto;
import br.fiap.pontofalante.transporte.Modelos.PrevisoesPonto;
import br.fiap.pontofalante.transporte.RedeGtfs;
import br.fiap.pontofalante.transporte.TransporteService;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Clock;
import java.time.Duration;
import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.UUID;

/**
 * Regras do Embarque Assistido. As previsões vêm sempre do TransporteService (SPTrans ou demonstração identificada);
 * este serviço só filtra as linhas escolhidas, registra o acompanhamento e nunca calcula ou estima horários.
 */
@Service
public class EmbarqueService {
    static final int MAX_FAVORITOS = 30;
    /** Um acompanhamento esquecido aberto expira: ninguém espera um ônibus por mais de 3 horas. */
    static final Duration VALIDADE_SESSAO = Duration.ofHours(3);

    private final FavoritoEmbarqueRepository favoritos;
    private final SessaoEmbarqueRepository sessoes;
    private final ConferenciaVisaoRepository conferencias;
    private final TransporteService transporte;
    private final ReconhecedorLetreiro visao;
    private final Clock relogio;

    public EmbarqueService(FavoritoEmbarqueRepository favoritos, SessaoEmbarqueRepository sessoes,
                           ConferenciaVisaoRepository conferencias, TransporteService transporte,
                           ReconhecedorLetreiro visao, Clock relogio) {
        this.favoritos = favoritos;
        this.sessoes = sessoes;
        this.conferencias = conferencias;
        this.transporte = transporte;
        this.visao = visao;
        this.relogio = relogio;
    }

    // ---------- favoritos ----------

    @Transactional(readOnly = true)
    public List<Favorito> favoritos(String dispositivo) {
        return favoritos.findByDispositivoOrderByCriadoEmAsc(dispositivo).stream().map(EmbarqueService::dto).toList();
    }

    @Transactional
    public Favorito salvarFavorito(String dispositivo, NovoFavorito n) {
        String linha = letreiro(n.linha());
        boolean simulado = Boolean.TRUE.equals(n.simulado());
        List<FavoritoEmbarque> atuais = favoritos.findByDispositivoOrderByCriadoEmAsc(dispositivo);
        for (FavoritoEmbarque f : atuais) {
            if (f.ponto == n.ponto() && f.linha.equals(linha) && java.util.Objects.equals(f.sentido, n.sentido())
                    && f.simulado == simulado) {
                // Salvar de novo o mesmo trajeto só atualiza o apelido: a ação é idempotente para a voz.
                if (n.apelido() != null) f.apelido = apelido(n.apelido());
                return dto(f);
            }
        }
        if (atuais.size() >= MAX_FAVORITOS) {
            throw new ErroApi(HttpStatus.CONFLICT, "LIMITE_FAVORITOS",
                    "Você já tem " + MAX_FAVORITOS + " trajetos salvos. Remova um para salvar outro.");
        }
        FavoritoEmbarque f = favoritos.save(new FavoritoEmbarque(dispositivo, n.ponto(), texto(n.pontoNome(), 120), linha,
                n.sentido(), n.destino() == null ? null : texto(n.destino(), 120), apelido(n.apelido()), simulado,
                OffsetDateTime.now(relogio)));
        return dto(f);
    }

    @Transactional
    public Favorito alterarFavorito(String dispositivo, long id, AlteracaoFavorito a) {
        FavoritoEmbarque f = favoritos.findByIdAndDispositivo(id, dispositivo)
                .orElseThrow(() -> ErroApi.naoEncontrado("Este trajeto não está nos seus favoritos."));
        f.apelido = apelido(a.apelido());
        return dto(f);
    }

    @Transactional
    public void removerFavorito(String dispositivo, long id) {
        FavoritoEmbarque f = favoritos.findByIdAndDispositivo(id, dispositivo)
                .orElseThrow(() -> ErroApi.naoEncontrado("Este trajeto não está nos seus favoritos."));
        favoritos.delete(f);
    }

    // ---------- acompanhamento ----------

    @Transactional
    public Sessao iniciar(String dispositivo, NovaSessao n) {
        boolean simulado = "demo".equals(n.modo());
        String modo = simulado ? "demo" : "auto";
        List<LinhaEscolhida> escolhas = new ArrayList<>();
        Set<String> vistas = new LinkedHashSet<>();
        for (LinhaEscolhida l : n.linhas()) {
            String letreiro = letreiro(l.letreiro());
            if (vistas.add(letreiro + ":" + l.sentido())) {
                escolhas.add(new LinhaEscolhida(letreiro, l.sentido(), l.destino()));
            }
        }
        conferirNoCadastro(n.ponto(), escolhas, modo);
        OffsetDateTime agora = OffsetDateTime.now(relogio);
        for (SessaoEmbarque aberta : sessoes.findByDispositivoAndEncerradaEmIsNull(dispositivo)) {
            aberta.encerradaEm = agora;
            aberta.desfecho = Desfecho.SUBSTITUIDA.name();
        }
        SessaoEmbarque s = sessoes.save(new SessaoEmbarque(UUID.randomUUID(), dispositivo, n.ponto(),
                texto(n.pontoNome(), 120), escolhas, simulado, agora));
        return dto(s);
    }

    /**
     * Confere no cadastro oficial (GTFS) se cada linha escolhida para mesmo neste ponto e no sentido informado.
     * Evita acompanhar um ônibus que nunca vai passar ali. Sem cadastro (demonstração), não há o que conferir.
     */
    void conferirNoCadastro(long ponto, List<LinhaEscolhida> escolhas, String modo) {
        if (!transporte.usaCadastro(modo)) return;
        List<RedeGtfs.Viagem> viagens = transporte.rede().viagensDaParada(ponto);
        if (viagens.isEmpty()) return; // ponto fora do cadastro: as previsões dirão se há ônibus
        for (LinhaEscolhida e : escolhas) {
            boolean para = viagens.stream().anyMatch(v -> v.letreiro().equalsIgnoreCase(e.letreiro())
                    && (e.sentido() == null || v.sentido() == e.sentido()));
            if (!para) {
                throw new ErroApi(HttpStatus.UNPROCESSABLE_ENTITY, "LINHA_NAO_PARA_NO_PONTO",
                        "Segundo o cadastro da SPTrans, a linha " + e.letreiro()
                                + (e.sentido() == null ? "" : " nesse sentido") + " não para neste ponto. "
                                + "Confira o ponto ou escolha outra linha.");
            }
        }
    }

    @Transactional
    public java.util.Optional<Sessao> atual(String dispositivo) {
        return sessoes.findFirstByDispositivoAndEncerradaEmIsNullOrderByIniciadaEmDesc(dispositivo)
                .filter(s -> !expirarSeVencida(s))
                .map(EmbarqueService::dto);
    }

    @Transactional(noRollbackFor = ErroApi.class)
    public Situacao situacao(String dispositivo, UUID id) {
        SessaoEmbarque s = sessaoAberta(dispositivo, id);
        PrevisoesPonto p;
        try {
            p = transporte.previsoes(s.ponto, s.simulado ? "demo" : "auto");
        } catch (ErroApi e) {
            s.consultas++;
            s.consultasComFalha++;
            throw e;
        }
        List<LinhaEscolhida> escolhas = s.escolhas();
        List<OnibusPrevisto> filtrados = filtrar(p.onibus(), escolhas);
        Set<String> outras = new LinkedHashSet<>();
        for (OnibusPrevisto o : p.onibus()) {
            if (!filtrados.contains(o)) outras.add(o.letreiro());
        }
        s.consultas++;
        if (!filtrados.isEmpty()) {
            int min = Math.max(0, filtrados.get(0).minutos());
            if (s.primeiraPrevisaoMin == null) s.primeiraPrevisaoMin = min;
            s.ultimaPrevisaoMin = min;
        }
        boolean simulado = p.fonte() == Fonte.SIMULADO;
        String frase = filtrados.isEmpty()
                ? (simulado ? "Demonstração. " : "") + "Nenhum ônibus " + nomes(escolhas)
                        + " está previsto agora neste ponto. Continuo acompanhando."
                : FraseFalada.montar(p.ponto().nome() == null || p.ponto().nome().isBlank() ? s.pontoNome : p.ponto().nome(),
                        filtrados.subList(0, Math.min(3, filtrados.size())), simulado);
        return new Situacao(dto(s), p.fonte(), p.consultadoEm(), p.horarioReferencia(), filtrados,
                filtrados.isEmpty() ? null : filtrados.get(0), frase, List.copyOf(outras));
    }

    /** Mantém só os ônibus das linhas escolhidas (e do sentido, quando informado), na ordem da SPTrans. */
    static List<OnibusPrevisto> filtrar(List<OnibusPrevisto> onibus, List<LinhaEscolhida> escolhas) {
        List<OnibusPrevisto> r = new ArrayList<>();
        for (OnibusPrevisto o : onibus == null ? List.<OnibusPrevisto>of() : onibus) {
            for (LinhaEscolhida e : escolhas) {
                if (e.letreiro().equalsIgnoreCase(o.letreiro())
                        && (e.sentido() == null || o.sentido() == null || e.sentido().equals(o.sentido()))) {
                    r.add(o);
                    break;
                }
            }
        }
        r.sort(java.util.Comparator.comparingInt(OnibusPrevisto::minutos));
        return r;
    }

    @Transactional
    public Sessao encerrar(String dispositivo, UUID id, Desfecho desfecho) {
        if (desfecho != Desfecho.EMBARQUEI && desfecho != Desfecho.DESISTI) {
            throw ErroApi.requisicaoInvalida("Informe EMBARQUEI ou DESISTI.");
        }
        SessaoEmbarque s = sessoes.findByIdAndDispositivo(id, dispositivo)
                .orElseThrow(() -> ErroApi.naoEncontrado("Não encontrei este acompanhamento."));
        if (s.aberta()) {
            s.encerradaEm = OffsetDateTime.now(relogio);
            s.desfecho = desfecho.name();
        }
        return dto(s);
    }

    @Transactional
    public void apagarDados(String dispositivo) {
        conferencias.apagarDoDispositivo(dispositivo);
        sessoes.apagarDoDispositivo(dispositivo);
        favoritos.apagarDoDispositivo(dispositivo);
    }

    @Transactional(readOnly = true)
    public Indicadores indicadores() {
        OffsetDateTime desde = OffsetDateTime.now(relogio).minusDays(30);
        long total = sessoes.contarReaisDesde(desde);
        long embarques = sessoes.contarReaisComDesfechoDesde(desde, Desfecho.EMBARQUEI.name());
        Double media = sessoes.mediaEsperaPrevistaDesde(desde);
        return new Indicadores(total, embarques, total == 0 ? null : (int) Math.round(100.0 * embarques / total),
                media == null ? null : Math.round(media * 10) / 10.0, favoritos.countBySimuladoFalse(),
                "Contagens de uso real nos últimos 30 dias, sem dados pessoais. A espera é a prevista pela SPTrans "
                        + "no início do acompanhamento, não um tempo medido.");
    }

    // ---------- visão computacional ----------

    public boolean visaoConectada() {
        return visao.conectado();
    }

    @Transactional
    public Conferencia conferir(String dispositivo, byte[] imagem, String tipo, String linhaEsperada, UUID sessao) {
        String esperada = letreiro(linhaEsperada);
        if (sessao != null) {
            sessoes.findByIdAndDispositivo(sessao, dispositivo)
                    .orElseThrow(() -> ErroApi.naoEncontrado("Não encontrei este acompanhamento."));
        }
        ReconhecedorLetreiro.Leitura leitura = visao.ler(imagem, tipo);
        ConferenciaLetreiro.Resultado r = ConferenciaLetreiro.comparar(esperada, leitura.leituras());
        conferencias.save(new ConferenciaVisao(sessao, dispositivo, esperada, r.linhaLida(), r.confianca(),
                r.resultado().name(), leitura.modelo(), OffsetDateTime.now(relogio)));
        return new Conferencia(r.resultado(), esperada, r.linhaLida(), r.confianca(), r.frase(), leitura.modelo(),
                leitura.latenciaMs());
    }

    // ---------- auxiliares ----------

    private SessaoEmbarque sessaoAberta(String dispositivo, UUID id) {
        SessaoEmbarque s = sessoes.findByIdAndDispositivo(id, dispositivo)
                .orElseThrow(() -> ErroApi.naoEncontrado("Não encontrei este acompanhamento."));
        if (!s.aberta() || expirarSeVencida(s)) {
            throw new ErroApi(HttpStatus.CONFLICT, "ACOMPANHAMENTO_ENCERRADO",
                    "Este acompanhamento já terminou. Escolha o ônibus de novo para acompanhar.");
        }
        return s;
    }

    private boolean expirarSeVencida(SessaoEmbarque s) {
        if (s.aberta() && s.iniciadaEm.plus(VALIDADE_SESSAO).isBefore(OffsetDateTime.now(relogio))) {
            s.encerradaEm = OffsetDateTime.now(relogio);
            s.desfecho = Desfecho.EXPIRADA.name();
            return true;
        }
        return false;
    }

    static String letreiro(String bruto) {
        String l = bruto == null ? "" : bruto.strip().toUpperCase(Locale.ROOT);
        if (!l.matches(EmbarqueDtos.LETREIRO)) {
            throw ErroApi.requisicaoInvalida("Informe a linha como aparece no letreiro, por exemplo 875A-10.");
        }
        return l;
    }

    private static String apelido(String a) {
        if (a == null) return null;
        String limpo = a.replaceAll("[\\p{Cntrl}<>]", "").strip();
        return limpo.isEmpty() ? null : texto(limpo, 40);
    }

    private static String texto(String t, int max) {
        String limpo = t.replaceAll("\\p{Cntrl}", " ").strip();
        return limpo.length() > max ? limpo.substring(0, max) : limpo;
    }

    private static String nomes(List<LinhaEscolhida> escolhas) {
        List<String> n = escolhas.stream().map(LinhaEscolhida::letreiro).toList();
        return n.size() == 1 ? "da linha " + n.get(0) : "das linhas " + String.join(", ", n);
    }

    static Favorito dto(FavoritoEmbarque f) {
        return new Favorito(f.id, f.ponto, f.pontoNome, f.linha, f.sentido, f.destino, f.apelido, f.simulado, f.criadoEm);
    }

    static Sessao dto(SessaoEmbarque s) {
        return new Sessao(s.id, s.ponto, s.pontoNome, s.escolhas(), s.simulado, s.iniciadaEm, s.encerradaEm,
                s.desfecho == null ? null : Desfecho.valueOf(s.desfecho));
    }
}

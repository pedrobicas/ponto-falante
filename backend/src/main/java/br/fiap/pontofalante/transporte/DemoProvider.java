package br.fiap.pontofalante.transporte;

import br.fiap.pontofalante.sistema.ErroApi;
import br.fiap.pontofalante.transporte.Modelos.DadosPrevisao;
import br.fiap.pontofalante.transporte.Modelos.Fonte;
import br.fiap.pontofalante.transporte.Modelos.Linha;
import br.fiap.pontofalante.transporte.Modelos.OnibusPrevisto;
import br.fiap.pontofalante.transporte.Modelos.Ponto;
import org.springframework.stereotype.Component;

import java.text.Normalizer;
import java.time.Clock;
import java.time.ZonedDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Locale;

/**
 * Dados SIMULADOS para a demonstração. Os códigos dos pontos (990001...) são fictícios e não existem na SPTrans.
 * As previsões são geradas a partir da hora atual, de forma determinística (mesmo minuto, mesmos ônibus).
 */
@Component
public class DemoProvider implements ProvedorTransporte {
    private static final DateTimeFormatter HHMM = DateTimeFormatter.ofPattern("HH:mm");

    record DemoLinha(long codigo, String letreiro, String terminalPrincipal, String terminalSecundario,
                     boolean circular, int intervaloMin) {
    }

    private static final List<DemoLinha> LINHAS = List.of(
            new DemoLinha(990101, "8000-10", "Term. Pq. Dom Pedro II", "Lapa", false, 9),
            new DemoLinha(990102, "5100-10", "Term. Santo Amaro", "Praça da Sé", false, 12),
            new DemoLinha(990103, "6200-10", "Metrô Ana Rosa", "Pinheiros", false, 10),
            new DemoLinha(990104, "7300-10", "Term. Bandeira", "Vila Madalena", false, 15),
            new DemoLinha(990105, "4400-10", "Term. Princesa Isabel", "Brooklin", false, 8),
            new DemoLinha(990106, "3500-10", "Metrô Tatuapé", "Penha", false, 14),
            new DemoLinha(990107, "2600-10", "Circular Paulista", "Circular Paulista", true, 11),
            new DemoLinha(990108, "1700-10", "Term. Sacomã", "Ipiranga", false, 13));

    private static final List<Ponto> PONTOS = List.of(
            ponto(990001, "Paulista - Museu de Arte", "Av. Paulista, 1578", -23.5614, -46.6559),
            ponto(990002, "Paulista - Trianon", "Av. Paulista, 1000", -23.5652, -46.6513),
            ponto(990003, "Brigadeiro Luís Antônio - Paraíso", "Av. Brigadeiro Luís Antônio, 2500", -23.5705, -46.6431),
            ponto(990004, "Rebouças - Faria Lima", "Av. Rebouças, 3000", -23.5675, -46.6987),
            ponto(990005, "Faria Lima - Pinheiros", "Av. Brigadeiro Faria Lima, 1800", -23.5679, -46.6934),
            ponto(990006, "Consolação - Higienópolis", "Rua da Consolação, 2200", -23.5446, -46.6575),
            ponto(990007, "Rio Branco - Luz", "Av. Rio Branco, 600", -23.5339, -46.6366),
            ponto(990008, "Ipiranga - República", "Av. Ipiranga, 300", -23.5436, -46.6429),
            ponto(990009, "São João - Largo do Arouche", "Av. São João, 900", -23.5410, -46.6460),
            ponto(990010, "Santo Amaro - Largo 13", "Av. Santo Amaro, 5000", -23.6540, -46.7090),
            ponto(990011, "Berrini - Brooklin", "Av. Engenheiro Luís Carlos Berrini, 1200", -23.6010, -46.6960),
            ponto(990012, "Tiradentes - Luz", "Av. Tiradentes, 800", -23.5330, -46.6340),
            ponto(990013, "Celso Garcia - Tatuapé", "Av. Celso Garcia, 4000", -23.5400, -46.5780),
            ponto(990014, "Vergueiro - Ana Rosa", "Rua Vergueiro, 2400", -23.5810, -46.6390),
            ponto(990015, "Sumaré - Perdizes", "Av. Doutor Arnaldo, 1500", -23.5370, -46.6720));

    private final Clock relogio;
    private final HashVeiculo hasher;

    public DemoProvider(Clock relogio, HashVeiculo hasher) {
        this.relogio = relogio;
        this.hasher = hasher;
    }

    private static Ponto ponto(long cod, String nome, String ed, double lat, double lon) {
        return new Ponto(cod, nome, ed, lat, lon, Fonte.SIMULADO);
    }

    @Override
    public Fonte fonte() {
        return Fonte.SIMULADO;
    }

    @Override
    public List<Ponto> buscarPontos(String termo) {
        String t = normalizar(termo);
        return PONTOS.stream()
                .filter(p -> normalizar(p.nome()).contains(t) || normalizar(p.endereco()).contains(t)
                        || String.valueOf(p.codigo()).contains(t))
                .toList();
    }

    @Override
    public List<Linha> buscarLinhas(String termo) {
        String t = normalizar(termo);
        List<Linha> saida = new ArrayList<>();
        for (DemoLinha l : LINHAS) {
            if (normalizar(l.letreiro()).contains(t) || normalizar(l.terminalPrincipal()).contains(t)
                    || normalizar(l.terminalSecundario()).contains(t)) {
                saida.add(linha(l, 1));
                if (!l.circular()) {
                    saida.add(linha(l, 2));
                }
            }
        }
        return saida;
    }

    private static Linha linha(DemoLinha l, int sentido) {
        return new Linha(l.codigo(), l.letreiro(), sentido, l.terminalPrincipal(), l.terminalSecundario(),
                sentido == 1 ? l.terminalSecundario() : l.terminalPrincipal(), l.circular());
    }

    @Override
    public DadosPrevisao previsoes(long codigoPonto) {
        int indice = -1;
        for (int i = 0; i < PONTOS.size(); i++) {
            if (PONTOS.get(i).codigo() == codigoPonto) {
                indice = i;
            }
        }
        if (indice < 0) {
            throw ErroApi.naoEncontrado("Não encontramos esse ponto de ônibus.");
        }
        ZonedDateTime agora = relogio.instant().atZone(relogio.getZone());
        long minutoAbsoluto = relogio.instant().getEpochSecond() / 60;
        List<OnibusPrevisto> onibus = new ArrayList<>();
        for (int k = 0; k < 3; k++) {
            int idxLinha = (indice + k * 3) % LINHAS.size();
            DemoLinha l = LINHAS.get(idxLinha);
            int sentido = (indice + k) % 2 == 0 ? 1 : 2;
            int intervalo = l.intervaloMin();
            long deslocamento = (codigoPonto * 7 + idxLinha * 3L) % intervalo;
            long x = minutoAbsoluto + deslocamento;
            int resto = (int) (x % intervalo);
            int primeiro = resto == 0 ? 0 : intervalo - resto;
            for (int j = 0; j < 2; j++) {
                int minutos = primeiro + j * intervalo;
                long ciclo = (x + minutos) / intervalo;
                String veiculo = hasher.hash("demo-" + l.letreiro() + "-" + ciclo);
                onibus.add(new OnibusPrevisto(l.letreiro(),
                        sentido == 1 ? l.terminalSecundario() : l.terminalPrincipal(), sentido,
                        agora.plusMinutes(minutos).format(HHMM), minutos, ciclo % 3 != 0, veiculo));
            }
        }
        onibus.sort(Comparator.comparingInt(OnibusPrevisto::minutos));
        return new DadosPrevisao(PONTOS.get(indice), agora.format(HHMM), onibus);
    }

    static String normalizar(String s) {
        if (s == null) {
            return "";
        }
        return Normalizer.normalize(s, Normalizer.Form.NFD).replaceAll("\\p{M}+", "")
                .toLowerCase(Locale.ROOT).trim();
    }
}

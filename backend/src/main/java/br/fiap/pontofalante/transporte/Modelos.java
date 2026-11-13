package br.fiap.pontofalante.transporte;

import java.time.OffsetDateTime;
import java.util.List;

/** Modelos da API pública de transporte (JSON snake_case via configuração global do Jackson). */
public final class Modelos {
    private Modelos() {
    }

    /** OLHO_VIVO: tempo real da SPTrans. GTFS_SPTRANS: cadastro oficial de paradas e itinerários. SIMULADO: demonstração. */
    public enum Fonte {OLHO_VIVO, GTFS_SPTRANS, SIMULADO}

    /** linhas: letreiros que param no ponto (cadastro); distanciaMetros: só em buscas por proximidade. */
    public record Ponto(long codigo, String nome, String endereco, Double latitude, Double longitude, Fonte fonte,
                        List<String> linhas, Integer distanciaMetros) {
        public Ponto(long codigo, String nome, String endereco, Double latitude, Double longitude, Fonte fonte) {
            this(codigo, nome, endereco, latitude, longitude, fonte, null, null);
        }
    }

    public record Linha(Long codigo, String letreiro, Integer sentido, String terminalPrincipal,
                        String terminalSecundario, String destino, boolean circular) {
    }

    public record OnibusPrevisto(String letreiro, String destino, Integer sentido, String previstoEm, int minutos,
                                 boolean acessivel, String veiculo) {
    }

    /** Resultado bruto de um provedor (sem frase falada). */
    public record DadosPrevisao(Ponto ponto, String horarioReferencia, List<OnibusPrevisto> onibus) {
    }

    public record PrevisoesPonto(Ponto ponto, Fonte fonte, String tipo, String horarioReferencia,
                                 OffsetDateTime consultadoEm, List<OnibusPrevisto> onibus, String fraseFalada) {
    }

    /** aviso: explicação curta para o passageiro (busca aproximada, código não encontrado, limite da fonte). */
    public record RespostaPontos(Fonte fonte, List<Ponto> pontos, String aviso) {
        public RespostaPontos(Fonte fonte, List<Ponto> pontos) {
            this(fonte, pontos, null);
        }
    }

    /** Uma linha em um sentido, com as paradas em ordem (cadastro GTFS). */
    public record SentidoLinha(String letreiro, int sentido, String destino, String nomeLinha, List<Ponto> paradas) {
    }

    public record RespostaItinerario(Fonte fonte, String letreiro, List<SentidoLinha> sentidos, String aviso) {
    }

    public record LinhaNoPonto(String letreiro, int sentido, String destino, String nomeLinha) {
    }

    public record RespostaLinhasDoPonto(Fonte fonte, long codigo, List<LinhaNoPonto> linhas, String aviso) {
    }

    public record RespostaLinhas(Fonte fonte, List<Linha> linhas) {
    }
}

package br.fiap.pontofalante.transporte;

import java.time.OffsetDateTime;
import java.util.List;

/** Modelos da API pública de transporte (JSON snake_case via configuração global do Jackson). */
public final class Modelos {
    private Modelos() {
    }

    public enum Fonte {OLHO_VIVO, SIMULADO}

    public record Ponto(long codigo, String nome, String endereco, Double latitude, Double longitude, Fonte fonte) {
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

    public record RespostaPontos(Fonte fonte, List<Ponto> pontos) {
    }

    public record RespostaLinhas(Fonte fonte, List<Linha> linhas) {
    }
}

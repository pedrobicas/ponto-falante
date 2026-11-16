package br.fiap.pontofalante.embarque;

import br.fiap.pontofalante.transporte.Modelos.Fonte;
import br.fiap.pontofalante.transporte.Modelos.OnibusPrevisto;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

import java.time.OffsetDateTime;
import java.util.List;
import java.util.UUID;

/** Contratos JSON do Embarque Assistido (snake_case pela configuração global do Jackson). */
public final class EmbarqueDtos {
    private EmbarqueDtos() {
    }

    /** Letreiro como aparece no ônibus: 875A-10, N137-11, 8000-10. */
    public static final String LETREIRO = "[0-9A-Za-z]{2,6}(-[0-9]{1,2})?";

    public enum Desfecho {EMBARQUEI, DESISTI, SUBSTITUIDA, EXPIRADA}

    public record LinhaEscolhida(
            @NotBlank(message = "Informe a linha.")
            @Pattern(regexp = LETREIRO, message = "Informe a linha como aparece no letreiro, por exemplo 875A-10.") String letreiro,
            @Min(value = 1, message = "O sentido deve ser 1 ou 2.") @Max(value = 2, message = "O sentido deve ser 1 ou 2.") Integer sentido,
            @Size(max = 120) String destino) {
    }

    public record NovoFavorito(
            @NotNull(message = "Informe o ponto.") @Min(1) @Max(999_999_999_999L) Long ponto,
            @NotBlank(message = "Informe o nome do ponto.") @Size(max = 120) String pontoNome,
            @NotBlank(message = "Informe a linha.")
            @Pattern(regexp = LETREIRO, message = "Informe a linha como aparece no letreiro, por exemplo 875A-10.") String linha,
            @Min(value = 1, message = "O sentido deve ser 1 ou 2.") @Max(value = 2, message = "O sentido deve ser 1 ou 2.") Integer sentido,
            @Size(max = 120) String destino,
            @Size(max = 40, message = "O apelido pode ter no máximo 40 letras.") String apelido,
            Boolean simulado) {
    }

    public record AlteracaoFavorito(@Size(max = 40, message = "O apelido pode ter no máximo 40 letras.") String apelido) {
    }

    public record Favorito(long id, long ponto, String pontoNome, String linha, Integer sentido, String destino,
                           String apelido, boolean simulado, OffsetDateTime criadoEm) {
    }

    public record NovaSessao(
            @NotNull(message = "Informe o ponto.") @Min(1) @Max(999_999_999_999L) Long ponto,
            @NotBlank(message = "Informe o nome do ponto.") @Size(max = 120) String pontoNome,
            @NotEmpty(message = "Escolha ao menos uma linha.") @Size(max = 3, message = "Acompanhe no máximo 3 linhas ao mesmo tempo.")
            List<@Valid @NotNull LinhaEscolhida> linhas,
            @Pattern(regexp = "auto|demo", message = "O modo deve ser auto ou demo.") String modo) {
    }

    public record Sessao(UUID id, long ponto, String pontoNome, List<LinhaEscolhida> linhas, boolean simulado,
                         OffsetDateTime iniciadaEm, OffsetDateTime encerradaEm, Desfecho desfecho) {
    }

    public record Encerramento(@NotNull(message = "Informe como terminou o acompanhamento.") Desfecho desfecho) {
    }

    /**
     * Situação de um acompanhamento: as previsões REAIS (ou simuladas, identificadas) só das linhas escolhidas.
     * proximo é o primeiro ônibus da lista; nenhum valor é estimado pelo Ponto Falante.
     */
    public record Situacao(Sessao sessao, Fonte fonte, OffsetDateTime consultadoEm, String horarioReferencia,
                           List<OnibusPrevisto> onibus, OnibusPrevisto proximo, String fraseFalada,
                           List<String> outrasLinhasPrevistas) {
    }

    public record Indicadores(long acompanhamentos30Dias, long embarquesConfirmados30Dias, Integer taxaConfirmacaoPct,
                              Double esperaPrevistaMediaMin, long trajetosFavoritos, String observacao) {
    }

    public enum ResultadoConferencia {CONFERE, NUMERO_CONFERE, NAO_CONFERE, INCONCLUSIVO}

    /** Uma leitura devolvida pelo modelo de visão: texto do letreiro, confiança (0 a 1) e caixa opcional. */
    public record LeituraLetreiro(String texto, double confianca, List<Integer> caixa) {
    }

    public record Conferencia(ResultadoConferencia resultado, String linhaEsperada, String linhaLida, Double confianca,
                              String fraseFalada, String modelo, Integer latenciaMs) {
    }

    public record EstadoVisao(boolean conectada, String mensagem) {
    }
}

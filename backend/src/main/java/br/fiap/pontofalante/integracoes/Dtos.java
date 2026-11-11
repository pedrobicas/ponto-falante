package br.fiap.pontofalante.integracoes;

import br.fiap.pontofalante.transporte.Modelos.Fonte;
import jakarta.validation.constraints.DecimalMax;
import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

import java.time.OffsetDateTime;

public final class Dtos {
    private Dtos() {
    }

    public record DeteccaoVisaoDto(
            @NotNull(message = "Informe o ponto.") Long ponto,
            @NotBlank(message = "Informe a linha reconhecida.")
            @Size(max = 20, message = "A linha reconhecida pode ter no máximo 20 caracteres.") String linhaReconhecida,
            @NotNull(message = "Informe a confiança.")
            @DecimalMin(value = "0.0", message = "A confiança deve estar entre 0 e 1.")
            @DecimalMax(value = "1.0", message = "A confiança deve estar entre 0 e 1.") Double confianca,
            @NotNull(message = "Informe quando a imagem foi capturada.") OffsetDateTime capturadoEm,
            @NotBlank(message = "Informe o dispositivo.")
            @Size(max = 64, message = "O dispositivo pode ter no máximo 64 caracteres.") String dispositivo) {
    }

    public record RespostaDeteccao(long id, String fraseFalada) {
    }

    public enum TipoEvento {BOTAO_PRESSIONADO, HEARTBEAT}

    public record EventoDispositivoDto(
            @NotBlank(message = "Informe o dispositivo.")
            @Size(max = 64, message = "O dispositivo pode ter no máximo 64 caracteres.") String dispositivoId,
            @NotNull(message = "Informe o ponto.") Long ponto,
            @NotNull(message = "Informe o tipo do evento.") TipoEvento tipo,
            @NotNull(message = "Informe quando o evento ocorreu.") OffsetDateTime ocorridoEm,
            @Min(value = 0, message = "A bateria deve estar entre 0 e 100.")
            @Max(value = 100, message = "A bateria deve estar entre 0 e 100.") Integer bateriaPct) {
    }

    public record RespostaEvento(String fraseFalada, Fonte fonte) {
    }
}

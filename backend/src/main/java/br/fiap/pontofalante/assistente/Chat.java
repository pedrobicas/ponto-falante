package br.fiap.pontofalante.assistente;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

import java.util.List;

public final class Chat {
    private Chat() {
    }

    public record PerguntaChat(
            @NotBlank(message = "Escreva sua pergunta.")
            @Size(max = 500, message = "A pergunta pode ter no máximo 500 letras.")
            String pergunta) {
        public PerguntaChat {
            pergunta = pergunta == null ? null : pergunta.strip();
        }
    }

    public record FonteCitada(String documento, String trechoId) {
    }

    /**
     * @param origem TEMPO_REAL (backend consultou a SPTrans ou a demonstração, sem LLM), BASE_OFICIAL (GenAI local com
     *               fontes oficiais) ou INDISPONIVEL (assistente fora do ar)
     */
    public record RespostaChat(String resposta, List<FonteCitada> fontes, String confianca, boolean naoConsta,
                               boolean disponivel, Integer latenciaMs, String origem) {
    }
}

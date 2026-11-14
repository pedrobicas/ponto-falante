package br.fiap.pontofalante.assistente;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.Max;

import java.util.List;

public final class Chat {
    private Chat() {
    }

    public record PerguntaChat(
            @NotBlank(message = "Escreva sua pergunta.")
            @Size(max = 500, message = "A pergunta pode ter no máximo 500 letras.")
            String pergunta, @Valid Contexto contexto) {
        public PerguntaChat(String pergunta) { this(pergunta, null); }
        public PerguntaChat {
            pergunta = pergunta == null ? null : pergunta.strip();
        }
    }

    public record Contexto(
            @Min(1) @Max(999999999999L) Long ponto,
            @Pattern(regexp = "[0-9]{3,4}[A-Za-z]?(-[0-9]{1,2})?") String linha,
            @Min(1) @Max(2) Integer sentido,
            @Pattern(regexp = "PONTO_PREVISAO|PONTO_LINHAS|LINHA|PONTO") String pendencia,
            @Pattern(regexp = "BILHETE|GRATUIDADE|ACESSIBILIDADE") String tema,
            @Pattern(regexp = "IDOSO|PCD|ESTUDANTE") String publico,
            @Min(0) @Max(120) Integer idade) {
        public Contexto(Long ponto, String linha, Integer sentido, String pendencia, String tema) {
            this(ponto, linha, sentido, pendencia, tema, null, null);
        }
        public static Contexto vazio() { return new Contexto(null, null, null, null, null); }
    }

    public record Acao(String titulo, String pergunta, String rota) {}

    public record FonteCitada(String documento, String trechoId, String url) {
        public FonteCitada(String documento, String trechoId) { this(documento, trechoId, null); }
    }

    /**
     * @param origem TEMPO_REAL (backend consultou a SPTrans ou a demonstração, sem LLM), BASE_OFICIAL (GenAI local com
     *               fontes oficiais) ou INDISPONIVEL (assistente fora do ar)
     */
    public record RespostaChat(String resposta, List<FonteCitada> fontes, String confianca, boolean naoConsta,
                               boolean disponivel, Integer latenciaMs, String origem, Contexto contexto, List<Acao> acoes,
                               String naturezaDados) {
        public RespostaChat(String resposta, List<FonteCitada> fontes, String confianca, boolean naoConsta,
                            boolean disponivel, Integer latenciaMs, String origem, Contexto contexto, List<Acao> acoes) {
            this(resposta, fontes, confianca, naoConsta, disponivel, latenciaMs, origem, contexto, acoes, null);
        }
        public RespostaChat(String resposta, List<FonteCitada> fontes, String confianca, boolean naoConsta,
                            boolean disponivel, Integer latenciaMs, String origem) {
            this(resposta, fontes, confianca, naoConsta, disponivel, latenciaMs, origem, null, List.of());
        }
        public RespostaChat comContexto(Contexto c, List<Acao> a) {
            return new RespostaChat(resposta, fontes, confianca, naoConsta, disponivel, latenciaMs, origem, c, a, naturezaDados);
        }
        public RespostaChat comNatureza(String natureza) {
            return new RespostaChat(resposta, fontes, confianca, naoConsta, disponivel, latenciaMs, origem, contexto, acoes,
                    List.of("ESTIMADO", "SIMULADO", "INDISPONIVEL").contains(natureza) ? natureza : null);
        }
    }
}

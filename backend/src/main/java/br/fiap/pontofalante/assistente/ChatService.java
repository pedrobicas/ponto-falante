package br.fiap.pontofalante.assistente;

import br.fiap.pontofalante.assistente.Chat.FonteCitada;
import br.fiap.pontofalante.assistente.Chat.RespostaChat;
import br.fiap.pontofalante.sistema.PfProps;
import com.fasterxml.jackson.databind.JsonNode;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClient;

import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * Repassa a pergunta ao serviço GenAI. Se ele estiver fora (PC desligado, túnel caído, timeout, 4xx/5xx),
 * devolve um aviso amigável com disponivel=false e abre um "disjuntor" simples que evita novas tentativas por 30 s.
 * O texto da pergunta nunca é gravado nem registrado em log.
 */
@Service
public class ChatService {
    private static final Logger log = LoggerFactory.getLogger(ChatService.class);
    static final String MSG_INDISPONIVEL = "O assistente está indisponível agora. Tente de novo em alguns minutos.";

    private final PfProps props;
    private final RestClient rest;
    private volatile long circuitoAbertoAteNanos;

    public ChatService(PfProps props) {
        this.props = props;
        this.rest = ClienteGenai.criar(props, props.genaiConnectTimeoutMs(), props.genaiReadTimeoutMs());
    }

    public RespostaChat perguntar(String pergunta) {
        if (!props.temGenai()) {
            return indisponivel();
        }
        if (System.nanoTime() - circuitoAbertoAteNanos < 0) {
            return indisponivel();
        }
        long inicio = System.nanoTime();
        try {
            JsonNode r = rest.post().uri("/chat")
                    .header("X-API-Key", props.genaiApiKey() == null ? "" : props.genaiApiKey())
                    .body(Map.of("pergunta", pergunta))
                    .retrieve().body(JsonNode.class);
            RespostaChat resposta = converter(r, (System.nanoTime() - inicio) / 1_000_000);
            if (resposta == null) {
                throw new IllegalStateException("resposta sem texto");
            }
            return resposta;
        } catch (Exception e) {
            // Só o tipo da falha vai para o log; nunca a pergunta.
            log.warn("Assistente (GenAI) indisponível: {}", e.getClass().getSimpleName());
            circuitoAbertoAteNanos = System.nanoTime() + Duration.ofSeconds(props.genaiCircuitoSegundos()).toNanos();
            return indisponivel();
        }
    }

    static RespostaChat converter(JsonNode r, long msTotal) {
        if (r == null || !r.hasNonNull("resposta") || r.get("resposta").asText().isBlank()) {
            return null;
        }
        List<FonteCitada> fontes = new ArrayList<>();
        for (JsonNode f : r.path("fontes")) {
            fontes.add(new FonteCitada(f.path("documento").asText(""), f.path("trecho_id").asText("")));
        }
        String confianca = r.path("confianca").asText("baixa");
        if (!List.of("alta", "media", "baixa").contains(confianca)) {
            confianca = "baixa";
        }
        Integer ms = r.hasNonNull("latencia_ms") ? r.get("latencia_ms").asInt() : (int) msTotal;
        return new RespostaChat(r.get("resposta").asText(), fontes, confianca, r.path("nao_consta").asBoolean(false),
                true, ms);
    }

    static RespostaChat indisponivel() {
        return new RespostaChat(MSG_INDISPONIVEL, List.of(), "baixa", true, false, null);
    }
}

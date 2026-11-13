package br.fiap.pontofalante.assistente;

import br.fiap.pontofalante.assistente.Chat.FonteCitada;
import br.fiap.pontofalante.assistente.Chat.RespostaChat;
import br.fiap.pontofalante.sistema.PfProps;
import com.fasterxml.jackson.databind.JsonNode;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import br.fiap.pontofalante.sistema.ErroApi;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.client.HttpClientErrorException;
import org.springframework.web.client.RestClient;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;

import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * Perguntas de tempo real são respondidas pelo backend (AssistenteTempoReal); as demais vão ao serviço GenAI. Se ele estiver fora (PC desligado, túnel caído, timeout, 4xx/5xx),
 * devolve um aviso amigável com disponivel=false e abre um "disjuntor" simples que evita novas tentativas por 30 s.
 * O texto da pergunta nunca é gravado nem registrado em log.
 */
@Service
public class ChatService {
    private static final Logger log = LoggerFactory.getLogger(ChatService.class);
    static final String MSG_INDISPONIVEL = "O assistente está indisponível agora. Tente de novo em alguns minutos.";

    private final PfProps props;
    private final RestClient rest;
    private final AssistenteTempoReal tempoReal;
    private final EnderecoGenai endereco;
    private volatile long circuitoAbertoAteNanos;

    public ChatService(PfProps props, AssistenteTempoReal tempoReal) {
        this(props, tempoReal, new EnderecoGenai(props));
    }

    @org.springframework.beans.factory.annotation.Autowired
    public ChatService(PfProps props, AssistenteTempoReal tempoReal, EnderecoGenai endereco) {
        this.props = props;
        this.tempoReal = tempoReal;
        this.endereco = endereco;
        this.rest = ClienteGenai.criar(props, props.genaiConnectTimeoutMs(), props.genaiReadTimeoutMs());
    }

    /** Identificador pseudônimo do usuário para a cota individual na GenAI: hash salgado do IP, nunca o IP. */
    public String idCliente(String ip) {
        try {
            MessageDigest md = MessageDigest.getInstance("SHA-256");
            md.update(props.salt().getBytes(StandardCharsets.UTF_8));
            md.update((byte) 0);
            md.update(String.valueOf(ip).getBytes(StandardCharsets.UTF_8));
            return HexFormat.of().formatHex(md.digest()).substring(0, 32);
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException(e);
        }
    }

    public RespostaChat perguntar(String pergunta) {
        return perguntar(pergunta, null);
    }

    public RespostaChat perguntar(String pergunta, String idCliente) {
        // Horários e previsões vêm só do backend (SPTrans ou demonstração identificada), nunca do modelo.
        long inicioTempoReal = System.nanoTime();
        var direta = tempoReal.responder(pergunta);
        if (direta.isPresent()) {
            RespostaChat r = direta.get();
            return new RespostaChat(r.resposta(), r.fontes(), r.confianca(), r.naoConsta(), r.disponivel(),
                    (int) ((System.nanoTime() - inicioTempoReal) / 1_000_000), r.origem());
        }
        var base = endereco.base();
        if (base.isEmpty()) {
            return indisponivel();
        }
        if (System.nanoTime() - circuitoAbertoAteNanos < 0) {
            return indisponivel();
        }
        long inicio = System.nanoTime();
        try {
            JsonNode r = rest.post().uri(base.get() + "/chat")
                    .header("X-API-Key", props.genaiApiKey() == null ? "" : props.genaiApiKey())
                    .headers(h -> { if (idCliente != null) h.set("X-PF-Cliente", idCliente); })
                    .body(Map.of("pergunta", pergunta))
                    .retrieve().body(JsonNode.class);
            RespostaChat resposta = converter(r, (System.nanoTime() - inicio) / 1_000_000);
            if (resposta == null) {
                throw new IllegalStateException("resposta sem texto");
            }
            return resposta;
        } catch (HttpClientErrorException.TooManyRequests e) {
            // Limite da GenAI (individual ou de capacidade): avisa o usuário sem derrubar o assistente para todos.
            throw new ErroApi(HttpStatus.TOO_MANY_REQUESTS, "MUITAS_PERGUNTAS",
                    "O assistente está recebendo muitas perguntas agora. Espere um minuto e tente de novo.");
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
                true, ms, "BASE_OFICIAL");
    }

    static RespostaChat indisponivel() {
        return new RespostaChat(MSG_INDISPONIVEL, List.of(), "baixa", true, false, null, "INDISPONIVEL");
    }

    /** Novo endereço registrado: não esperar o fim do disjuntor aberto pelo túnel antigo. */
    void fecharCircuito() {
        circuitoAbertoAteNanos = System.nanoTime();
    }
}

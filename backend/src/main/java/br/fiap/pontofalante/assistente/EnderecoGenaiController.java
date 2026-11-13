package br.fiap.pontofalante.assistente;

import br.fiap.pontofalante.sistema.ErroApi;
import br.fiap.pontofalante.sistema.PfProps;
import com.fasterxml.jackson.databind.JsonNode;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.client.RestClient;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.net.http.HttpClient;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.util.HexFormat;
import java.time.Duration;
import java.time.Instant;
import java.util.Map;

/**
 * O PC que roda FastAPI + Ollama informa o endereço atual do túnel (X-API-Key = GENAI_API_KEY, conferida pelo
 * ChavesApiInterceptor). Antes de aceitar, o backend exige {url}/health com HTTP 200 e status "ok" e um desafio de
 * identidade: {url}/identidade?desafio=N precisa devolver HMAC-SHA256(GENAI_API_KEY, "pf-genai-identidade:" + N).
 * Só a FastAPI que conhece a chave responde certo, e a chave nunca viaja nesse teste. Um túnel caído ou de outro
 * serviço não substitui o endereço em uso. Registros são serializados: um teste lento não sobrescreve um mais novo.
 */
@RestController
@RequestMapping("/api/genai")
public class EnderecoGenaiController {
    private static final Logger log = LoggerFactory.getLogger(EnderecoGenaiController.class);
    private static final Duration INTERVALO_MINIMO = Duration.ofSeconds(5);

    public record PedidoEndereco(String url) {
    }

    private final EnderecoGenai endereco;
    private final SaudeGenai saude;
    private final ChatService chat;
    private final PfProps props;
    private final RestClient rest;
    private final SecureRandom aleatorio = new SecureRandom();
    private Instant ultimaTentativa = Instant.EPOCH;

    public EnderecoGenaiController(PfProps props, EnderecoGenai endereco, SaudeGenai saude, ChatService chat) {
        this.props = props;
        this.endereco = endereco;
        this.saude = saude;
        this.chat = chat;
        this.rest = RestClient.builder().requestFactory(fabrica()).build();
    }

    private static org.springframework.http.client.JdkClientHttpRequestFactory fabrica() {
        HttpClient http = HttpClient.newBuilder().version(HttpClient.Version.HTTP_1_1)
                .connectTimeout(Duration.ofSeconds(5)).followRedirects(HttpClient.Redirect.NEVER).build();
        var f = new org.springframework.http.client.JdkClientHttpRequestFactory(http);
        f.setReadTimeout(Duration.ofSeconds(8));
        return f;
    }

    @PutMapping("/endereco")
    public synchronized Map<String, Object> registrar(@RequestBody PedidoEndereco pedido) {
        String url = endereco.validar(pedido == null ? null : pedido.url());
        Instant agora = Instant.now();
        if (Duration.between(ultimaTentativa, agora).compareTo(INTERVALO_MINIMO) < 0) {
            throw new ErroApi(HttpStatus.TOO_MANY_REQUESTS, "MUITAS_TENTATIVAS", "Aguarde alguns segundos.");
        }
        ultimaTentativa = agora;
        if (!saudavel(url)) {
            throw new ErroApi(HttpStatus.UNPROCESSABLE_ENTITY, "GENAI_SEM_SAUDE",
                    "O endereço informado não respondeu /health com sucesso; o endereço anterior foi mantido.");
        }
        if (!provaIdentidade(url)) {
            throw new ErroApi(HttpStatus.UNPROCESSABLE_ENTITY, "GENAI_SEM_IDENTIDADE",
                    "O endereço informado não comprovou ser a GenAI deste projeto; o endereço anterior foi mantido.");
        }
        endereco.registrar(url);
        saude.esquecer();
        chat.fecharCircuito();
        log.info("Endereço da GenAI atualizado pelo PC (host terminado em {})", url.substring(Math.max(0, url.length() - 20)));
        return Map.of("registrado", true, "origem", endereco.origem(), "registrado_em", endereco.registradoEm().toString());
    }

    boolean saudavel(String url) {
        try {
            var r = rest.get().uri(url + "/health").retrieve().toEntity(JsonNode.class);
            // Sem seguir redirecionamentos, um 3xx volta "com sucesso" do RestClient: só 200 com o contrato vale.
            return r.getStatusCode().value() == 200 && r.getBody() != null
                    && "ok".equals(r.getBody().path("status").asText());
        } catch (Exception e) {
            log.warn("Registro de endereço da GenAI recusado: /health não respondeu ({})", e.getClass().getSimpleName());
            return false;
        }
    }

    boolean provaIdentidade(String url) {
        String chave = props.genaiApiKey();
        if (chave == null || chave.isBlank()) {
            return false;
        }
        byte[] bytes = new byte[32];
        aleatorio.nextBytes(bytes);
        String desafio = HexFormat.of().formatHex(bytes);
        try {
            var r = rest.get().uri(url + "/identidade?desafio=" + desafio).retrieve().toEntity(JsonNode.class);
            if (r.getStatusCode().value() != 200 || r.getBody() == null) {
                return false;
            }
            byte[] recebida = r.getBody().path("prova").asText("").getBytes(StandardCharsets.US_ASCII);
            byte[] esperada = prova(chave, desafio).getBytes(StandardCharsets.US_ASCII);
            return MessageDigest.isEqual(recebida, esperada);
        } catch (Exception e) {
            log.warn("Registro de endereço da GenAI recusado: desafio de identidade falhou ({})", e.getClass().getSimpleName());
            return false;
        }
    }

    static String prova(String chave, String desafio) {
        try {
            Mac mac = Mac.getInstance("HmacSHA256");
            mac.init(new SecretKeySpec(chave.getBytes(StandardCharsets.UTF_8), "HmacSHA256"));
            return HexFormat.of().formatHex(mac.doFinal(("pf-genai-identidade:" + desafio).getBytes(StandardCharsets.UTF_8)));
        } catch (Exception e) {
            throw new IllegalStateException(e);
        }
    }
}

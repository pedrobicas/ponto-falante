package br.fiap.pontofalante.assistente;

import br.fiap.pontofalante.sistema.ErroApi;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.client.RestClient;

import java.net.http.HttpClient;
import java.time.Duration;
import java.time.Instant;
import java.util.Map;

/**
 * O PC que roda FastAPI + Ollama informa o endereço atual do túnel (X-API-Key = GENAI_API_KEY, conferida pelo
 * ChavesApiInterceptor). Antes de aceitar, o backend confirma que {url}/health responde: um túnel caído ou
 * de outro serviço não substitui o endereço em uso.
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
    private final RestClient rest;
    private volatile Instant ultimaTentativa = Instant.EPOCH;

    public EnderecoGenaiController(EnderecoGenai endereco, SaudeGenai saude, ChatService chat) {
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
    public Map<String, Object> registrar(@RequestBody PedidoEndereco pedido) {
        String url = endereco.validar(pedido == null ? null : pedido.url());
        Instant agora = Instant.now();
        if (Duration.between(ultimaTentativa, agora).compareTo(INTERVALO_MINIMO) < 0) {
            throw new ErroApi(HttpStatus.TOO_MANY_REQUESTS, "MUITAS_TENTATIVAS", "Aguarde alguns segundos.");
        }
        ultimaTentativa = agora;
        try {
            rest.get().uri(url + "/health").retrieve().toBodilessEntity();
        } catch (Exception e) {
            log.warn("Registro de endereço da GenAI recusado: /health não respondeu ({})", e.getClass().getSimpleName());
            throw new ErroApi(HttpStatus.UNPROCESSABLE_ENTITY, "GENAI_SEM_SAUDE",
                    "O endereço informado não respondeu /health com sucesso; o endereço anterior foi mantido.");
        }
        endereco.registrar(url);
        saude.esquecer();
        chat.fecharCircuito();
        log.info("Endereço da GenAI atualizado pelo PC (host terminado em {})", url.substring(Math.max(0, url.length() - 20)));
        return Map.of("registrado", true, "origem", endereco.origem(), "registrado_em", endereco.registradoEm().toString());
    }
}

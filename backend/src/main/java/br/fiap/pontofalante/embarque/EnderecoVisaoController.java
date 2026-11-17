package br.fiap.pontofalante.embarque;

import br.fiap.pontofalante.sistema.ErroApi;
import br.fiap.pontofalante.sistema.PfProps;
import com.fasterxml.jackson.databind.JsonNode;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.client.JdkClientHttpRequestFactory;
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
import java.time.Duration;
import java.time.Instant;
import java.util.HexFormat;
import java.util.Map;

/**
 * O PC que roda o modelo de visão informa o endereço atual do túnel (X-API-Key = chave do serviço de visão, conferida
 * pelo ChavesApiInterceptor). Antes de aceitar, o backend exige {url}/health com status "ok" (modelo carregado) e um
 * desafio de identidade: {url}/identidade?desafio=N precisa devolver HMAC-SHA256(chave, "pf-visao-identidade:" + N).
 * Só o serviço que conhece a chave responde certo, e a chave nunca viaja nesse teste.
 */
@RestController
@RequestMapping("/api/visao")
public class EnderecoVisaoController {
    private static final Logger log = LoggerFactory.getLogger(EnderecoVisaoController.class);
    private static final Duration INTERVALO_MINIMO = Duration.ofSeconds(5);

    public record PedidoEndereco(String url) {
    }

    private final EnderecoVisao endereco;
    private final ReconhecedorLetreiro reconhecedor;
    private final PfProps props;
    private final RestClient rest;
    private final SecureRandom aleatorio = new SecureRandom();
    private Instant ultimaTentativa = Instant.EPOCH;

    public EnderecoVisaoController(PfProps props, EnderecoVisao endereco, ReconhecedorLetreiro reconhecedor) {
        this.props = props;
        this.endereco = endereco;
        this.reconhecedor = reconhecedor;
        HttpClient http = HttpClient.newBuilder().version(HttpClient.Version.HTTP_1_1)
                .connectTimeout(Duration.ofSeconds(5)).followRedirects(HttpClient.Redirect.NEVER).build();
        JdkClientHttpRequestFactory f = new JdkClientHttpRequestFactory(http);
        f.setReadTimeout(Duration.ofSeconds(8));
        this.rest = RestClient.builder().requestFactory(f).build();
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
            throw new ErroApi(HttpStatus.UNPROCESSABLE_ENTITY, "VISAO_SEM_SAUDE",
                    "O endereço informado não respondeu /health com o modelo carregado; o endereço anterior foi mantido.");
        }
        if (!provaIdentidade(url)) {
            throw new ErroApi(HttpStatus.UNPROCESSABLE_ENTITY, "VISAO_SEM_IDENTIDADE",
                    "O endereço informado não comprovou ser o serviço de visão deste projeto; o endereço anterior foi mantido.");
        }
        endereco.registrar(url);
        reconhecedor.esquecerSaude();
        log.info("Endereço da visão atualizado pelo PC (host terminado em {})", url.substring(Math.max(0, url.length() - 20)));
        return Map.of("registrado", true, "origem", endereco.origem(), "registrado_em", endereco.registradoEm().toString());
    }

    boolean saudavel(String url) {
        try {
            var r = rest.get().uri(url + "/health").retrieve().toEntity(JsonNode.class);
            return r.getStatusCode().value() == 200 && r.getBody() != null
                    && "ok".equals(r.getBody().path("status").asText());
        } catch (Exception e) {
            log.warn("Registro de endereço da visão recusado: /health não respondeu ({})", e.getClass().getSimpleName());
            return false;
        }
    }

    boolean provaIdentidade(String url) {
        String chave = props.visaoServicoChave();
        if (chave == null || chave.isBlank()) return false;
        byte[] bytes = new byte[32];
        aleatorio.nextBytes(bytes);
        String desafio = HexFormat.of().formatHex(bytes);
        try {
            var r = rest.get().uri(url + "/identidade?desafio=" + desafio).retrieve().toEntity(JsonNode.class);
            if (r.getStatusCode().value() != 200 || r.getBody() == null) return false;
            byte[] recebida = r.getBody().path("prova").asText("").getBytes(StandardCharsets.US_ASCII);
            byte[] esperada = prova(chave, desafio).getBytes(StandardCharsets.US_ASCII);
            return MessageDigest.isEqual(recebida, esperada);
        } catch (Exception e) {
            log.warn("Registro de endereço da visão recusado: desafio de identidade falhou ({})", e.getClass().getSimpleName());
            return false;
        }
    }

    static String prova(String chave, String desafio) {
        try {
            Mac mac = Mac.getInstance("HmacSHA256");
            mac.init(new SecretKeySpec(chave.getBytes(StandardCharsets.UTF_8), "HmacSHA256"));
            return HexFormat.of().formatHex(mac.doFinal(("pf-visao-identidade:" + desafio).getBytes(StandardCharsets.UTF_8)));
        } catch (Exception e) {
            throw new IllegalStateException(e);
        }
    }
}

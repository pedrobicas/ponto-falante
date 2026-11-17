package br.fiap.pontofalante.embarque;

import br.fiap.pontofalante.embarque.EmbarqueDtos.LeituraLetreiro;
import br.fiap.pontofalante.sistema.ErroApi;
import br.fiap.pontofalante.sistema.PfProps;
import com.fasterxml.jackson.databind.JsonNode;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.client.RestClient;

import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Collection;
import java.util.List;
import java.util.Optional;

/**
 * Adaptador para o serviço de visão computacional da equipe (visao/servico: YOLO11n treinado + EasyOCR).
 * Contrato: contratos/openapi-visao-letreiro.yaml. Sem endereço configurado nem registrado pelo PC, o recurso fica
 * desligado e a API responde 503 VISAO_NAO_CONECTADA; com o PC desligado, 503 VISAO_INDISPONIVEL. Nenhum resultado é
 * simulado.
 */
@Component
public class ReconhecedorLetreiro {
    private static final Logger log = LoggerFactory.getLogger(ReconhecedorLetreiro.class);
    public static final String MSG_NAO_CONECTADA = "A conferência do letreiro pela câmera ainda não está conectada. "
            + "Confirme a linha com o motorista ou com alguém no ponto.";
    public static final String MSG_INDISPONIVEL = "O reconhecimento do letreiro roda no computador da equipe e está "
            + "desligado agora. Confirme a linha com o motorista ou com alguém no ponto.";
    private static final Duration CACHE_SAUDE_OK = Duration.ofSeconds(30);
    private static final Duration CACHE_SAUDE_FALHA = Duration.ofSeconds(10);

    /**
     * Resposta do serviço. onibus/letreiros: quantos o detector encontrou na foto (null se o serviço não informar);
     * validada: o texto foi conferido contra as linhas do ponto.
     */
    public record Leitura(String modelo, List<LeituraLetreiro> leituras, Integer latenciaMs, Integer onibus,
                          Integer letreiros, boolean validada) {
        public Leitura(String modelo, List<LeituraLetreiro> leituras, Integer latenciaMs) {
            this(modelo, leituras, latenciaMs, null, null, false);
        }
    }

    private final EnderecoVisao endereco;
    private final String chave;
    private final RestClient rest;
    private final RestClient restSaude;
    private volatile String saudeBase;
    private volatile boolean saudeOk;
    private volatile Instant saudeEm = Instant.EPOCH;

    public ReconhecedorLetreiro(PfProps props, EnderecoVisao endereco) {
        this.endereco = endereco;
        this.chave = props.visaoServicoChave();
        this.rest = RestClient.builder().requestFactory(fabrica(3000, 8000)).build();
        this.restSaude = RestClient.builder().requestFactory(fabrica(2000, 3000)).build();
    }

    private static SimpleClientHttpRequestFactory fabrica(int conexaoMs, int leituraMs) {
        SimpleClientHttpRequestFactory f = new SimpleClientHttpRequestFactory();
        f.setConnectTimeout(conexaoMs);
        f.setReadTimeout(leituraMs);
        return f;
    }

    /** Há um endereço configurado (PF_VISAO_URL) ou registrado pelo PC. */
    public boolean conectado() {
        return endereco.base().isPresent();
    }

    /** Conectado e respondendo /health agora (resultado guardado por 30 s; falha, por 10 s). */
    public boolean disponivel() {
        Optional<String> base = endereco.base();
        if (base.isEmpty()) return false;
        Instant agora = Instant.now();
        if (base.get().equals(saudeBase)
                && agora.isBefore(saudeEm.plus(saudeOk ? CACHE_SAUDE_OK : CACHE_SAUDE_FALHA))) {
            return saudeOk;
        }
        boolean ok;
        try {
            JsonNode r = restSaude.get().uri(base.get() + "/health").retrieve().body(JsonNode.class);
            ok = r != null && "ok".equals(r.path("status").asText());
        } catch (Exception e) {
            ok = false;
        }
        saudeBase = base.get();
        saudeOk = ok;
        saudeEm = agora;
        return ok;
    }

    /** Esquece o /health guardado (endereço novo registrado pelo PC). */
    void esquecerSaude() {
        saudeEm = Instant.EPOCH;
    }

    /**
     * Envia a foto ao serviço. linhasDoPonto: linhas que passam no ponto (e as esperadas); o serviço só aceita uma
     * leitura que case com uma delas. Vazio: o serviço lê sem validar e reduz a confiança.
     */
    public Leitura ler(byte[] imagem, String tipo, Collection<String> linhasDoPonto) {
        String base = endereco.base().orElseThrow(
                () -> new ErroApi(HttpStatus.SERVICE_UNAVAILABLE, "VISAO_NAO_CONECTADA", MSG_NAO_CONECTADA));
        MultiValueMap<String, Object> partes = new LinkedMultiValueMap<>();
        partes.add("imagem", new ByteArrayResource(imagem) {
            @Override
            public String getFilename() {
                return "quadro." + (MediaType.IMAGE_PNG_VALUE.equals(tipo) ? "png" : "jpg");
            }
        });
        if (linhasDoPonto != null && !linhasDoPonto.isEmpty()) {
            partes.add("linhas", String.join(",", linhasDoPonto));
        }
        try {
            JsonNode r = rest.post().uri(base + "/v1/letreiro")
                    .header("X-API-Key", chave == null ? "" : chave)
                    .contentType(MediaType.MULTIPART_FORM_DATA)
                    .body(partes)
                    .retrieve().body(JsonNode.class);
            return converter(r);
        } catch (ErroApi e) {
            throw e;
        } catch (Exception e) {
            log.warn("Serviço de visão indisponível: {}", e.getClass().getSimpleName());
            esquecerSaude();
            throw new ErroApi(HttpStatus.SERVICE_UNAVAILABLE, "VISAO_INDISPONIVEL",
                    "Não consegui conferir o letreiro agora. Confirme a linha com o motorista.");
        }
    }

    /** Valida a resposta do modelo: campos fora do contrato viram erro, nunca um resultado inventado. */
    static Leitura converter(JsonNode r) {
        if (r == null || !r.path("leituras").isArray() || r.path("modelo").asText("").isBlank()) {
            throw new ErroApi(HttpStatus.BAD_GATEWAY, "VISAO_RESPOSTA_INVALIDA",
                    "O serviço de visão respondeu fora do contrato. Confirme a linha com o motorista.");
        }
        List<LeituraLetreiro> leituras = new ArrayList<>();
        for (JsonNode l : r.path("leituras")) {
            double conf = l.path("confianca").asDouble(Double.NaN);
            String texto = l.path("texto").asText("");
            if (texto.isBlank() || texto.length() > 40 || !(conf >= 0 && conf <= 1)) continue;
            List<Integer> caixa = null;
            if (l.path("caixa").isArray() && l.path("caixa").size() == 4) {
                caixa = new ArrayList<>();
                for (JsonNode c : l.path("caixa")) caixa.add(c.asInt());
            }
            leituras.add(new LeituraLetreiro(texto.strip(), conf, caixa));
        }
        String modelo = r.path("modelo").asText().strip();
        JsonNode det = r.path("deteccoes");
        return new Leitura(modelo.length() > 80 ? modelo.substring(0, 80) : modelo, leituras,
                r.hasNonNull("latencia_ms") ? r.get("latencia_ms").asInt() : null,
                contagem(det, "onibus"), contagem(det, "letreiros"), r.path("linhas_validadas").asBoolean(false));
    }

    private static Integer contagem(JsonNode det, String campo) {
        JsonNode n = det.path(campo);
        return n.isInt() && n.asInt() >= 0 ? n.asInt() : null;
    }
}

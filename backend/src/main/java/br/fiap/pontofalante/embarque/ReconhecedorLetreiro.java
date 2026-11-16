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

import java.util.ArrayList;
import java.util.List;

/**
 * Adaptador para o serviço de visão computacional (modelo treinado pela equipe de Applied Computer Vision).
 * Contrato: contratos/openapi-visao-letreiro.yaml. Enquanto PF_VISAO_URL não estiver configurada, o recurso fica
 * desligado e a API responde 503 VISAO_NAO_CONECTADA: nenhum resultado é simulado.
 */
@Component
public class ReconhecedorLetreiro {
    private static final Logger log = LoggerFactory.getLogger(ReconhecedorLetreiro.class);
    public static final String MSG_NAO_CONECTADA = "A conferência do letreiro pela câmera ainda não está conectada. "
            + "Confirme a linha com o motorista ou com alguém no ponto.";

    public record Leitura(String modelo, List<LeituraLetreiro> leituras, Integer latenciaMs) {
    }

    private final String base;
    private final String chave;
    private final RestClient rest;

    public ReconhecedorLetreiro(PfProps props) {
        String url = props.visaoUrl() == null ? "" : props.visaoUrl().strip();
        this.base = url.replaceAll("/+$", "");
        this.chave = props.visaoServicoChave();
        SimpleClientHttpRequestFactory f = new SimpleClientHttpRequestFactory();
        f.setConnectTimeout(3000);
        f.setReadTimeout(8000);
        this.rest = RestClient.builder().requestFactory(f).build();
    }

    public boolean conectado() {
        return base.startsWith("http://") || base.startsWith("https://");
    }

    public Leitura ler(byte[] imagem, String tipo) {
        if (!conectado()) {
            throw new ErroApi(HttpStatus.SERVICE_UNAVAILABLE, "VISAO_NAO_CONECTADA", MSG_NAO_CONECTADA);
        }
        MultiValueMap<String, Object> partes = new LinkedMultiValueMap<>();
        partes.add("imagem", new ByteArrayResource(imagem) {
            @Override
            public String getFilename() {
                return "quadro." + (MediaType.IMAGE_PNG_VALUE.equals(tipo) ? "png" : "jpg");
            }
        });
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
        return new Leitura(modelo.length() > 80 ? modelo.substring(0, 80) : modelo, leituras,
                r.hasNonNull("latencia_ms") ? r.get("latencia_ms").asInt() : null);
    }
}

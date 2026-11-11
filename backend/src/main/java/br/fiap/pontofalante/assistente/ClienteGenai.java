package br.fiap.pontofalante.assistente;

import br.fiap.pontofalante.sistema.PfProps;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.web.client.RestClient;

import java.net.http.HttpClient;
import java.time.Duration;

/** Fábrica de RestClient para o serviço GenAI (HTTP/1.1, timeouts explícitos). */
final class ClienteGenai {
    private ClienteGenai() {
    }

    static String baseUrl(PfProps props) {
        String url = props.genaiUrl().trim();
        return url.endsWith("/") ? url.substring(0, url.length() - 1) : url;
    }

    static RestClient criar(PfProps props, int connectMs, int readMs) {
        HttpClient http = HttpClient.newBuilder()
                .version(HttpClient.Version.HTTP_1_1)
                .connectTimeout(Duration.ofMillis(connectMs))
                .build();
        JdkClientHttpRequestFactory fabrica = new JdkClientHttpRequestFactory(http);
        fabrica.setReadTimeout(Duration.ofMillis(readMs));
        RestClient.Builder b = RestClient.builder().requestFactory(fabrica);
        if (props.temGenai()) {
            b.baseUrl(baseUrl(props));
        }
        return b.build();
    }
}

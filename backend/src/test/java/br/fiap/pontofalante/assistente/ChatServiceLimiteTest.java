package br.fiap.pontofalante.assistente;

import br.fiap.pontofalante.sistema.ErroApi;
import br.fiap.pontofalante.sistema.PfProps;
import com.sun.net.httpserver.HttpServer;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.boot.context.properties.bind.Bindable;
import org.springframework.boot.context.properties.bind.Binder;
import org.springframework.boot.context.properties.source.MapConfigurationPropertySource;

import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.Map;
import java.util.concurrent.atomic.AtomicInteger;

import static org.assertj.core.api.Assertions.*;

/** GenAI respondendo 429 não abre o disjuntor global, e o Spring envia só um id pseudônimo do usuário. */
class ChatServiceLimiteTest {
    HttpServer server;
    ChatService service;
    AtomicInteger chamadas = new AtomicInteger();
    volatile int status = 429;
    volatile String clienteRecebido;

    @BeforeEach void iniciar() throws Exception {
        server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.createContext("/chat", ex -> {
            chamadas.incrementAndGet();
            clienteRecebido = ex.getRequestHeaders().getFirst("X-PF-Cliente");
            byte[] body = (status == 200
                    ? "{\"resposta\":\"Sim.\",\"fontes\":[],\"confianca\":\"alta\",\"nao_consta\":false}"
                    : "{\"detail\":\"limite\"}").getBytes(StandardCharsets.UTF_8);
            ex.getResponseHeaders().add("Content-Type", "application/json");
            if (status == 429) ex.getResponseHeaders().add("Retry-After", "30");
            ex.sendResponseHeaders(status, body.length);
            ex.getResponseBody().write(body);
            ex.close();
        });
        server.start();
        PfProps props = new Binder(new MapConfigurationPropertySource(Map.of(
                "pf.genai-url", "http://127.0.0.1:" + server.getAddress().getPort(),
                "pf.genai-api-key", "chave-teste",
                "pf.salt", "salt-teste"))).bind("pf", Bindable.of(PfProps.class)).get();
        service = new ChatService(props);
    }

    @AfterEach void parar() { server.stop(0); }

    @Test void limiteDaGenaiViraAvisoSemDerrubarOAssistente() {
        String id = service.idCliente("198.51.100.9");
        assertThatThrownBy(() -> service.perguntar("pergunta", id))
                .isInstanceOfSatisfying(ErroApi.class, e -> assertThat(e.getMessage()).contains("Espere um minuto"));
        status = 200;
        var r = service.perguntar("pergunta", id);
        assertThat(r.disponivel()).isTrue();
        assertThat(chamadas.get()).isEqualTo(2);
    }

    @Test void enviaIdPseudonimoEstavelSemOIp() {
        status = 200;
        String id = service.idCliente("198.51.100.9");
        service.perguntar("pergunta", id);
        assertThat(clienteRecebido).isEqualTo(id).matches("[0-9a-f]{32}").doesNotContain("198");
        assertThat(service.idCliente("198.51.100.9")).isEqualTo(id);
        assertThat(service.idCliente("198.51.100.10")).isNotEqualTo(id);
    }
}

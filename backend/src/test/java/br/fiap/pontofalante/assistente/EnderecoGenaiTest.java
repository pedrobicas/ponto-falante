package br.fiap.pontofalante.assistente;

import br.fiap.pontofalante.sistema.ChavesApiInterceptor;
import br.fiap.pontofalante.sistema.ErroApi;
import br.fiap.pontofalante.sistema.PfProps;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.sun.net.httpserver.HttpServer;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.boot.context.properties.bind.Bindable;
import org.springframework.boot.context.properties.bind.Binder;
import org.springframework.boot.context.properties.source.MapConfigurationPropertySource;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;
import org.springframework.web.servlet.HandlerMapping;

import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.atomic.AtomicInteger;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/** Endereço da GenAI trocado pelo túnel do PC: só HTTPS em host permitido, protegido pela chave da GenAI. */
class EnderecoGenaiTest {
    static PfProps props(String url, String chave) {
        Map<String, String> m = new HashMap<>(Map.of("pf.salt", "salt-teste"));
        m.put("pf.genai-url", url);
        m.put("pf.genai-api-key", chave);
        return new Binder(new MapConfigurationPropertySource(m)).bind("pf", Bindable.of(PfProps.class)).get();
    }

    @Test void aceitaTunelRapidoEHostConfigurado() {
        var e = new EnderecoGenai(props("https://genai.exemplo.org", "k"));
        assertThat(e.validar("https://palavra-outra-mais.trycloudflare.com/")).isEqualTo("https://palavra-outra-mais.trycloudflare.com");
        assertThat(e.validar("https://GENAI.exemplo.org")).isEqualTo("https://genai.exemplo.org");
    }

    @ParameterizedTest
    @ValueSource(strings = {"http://abc.trycloudflare.com", "https://abc.trycloudflare.com/chat",
            "https://abc.trycloudflare.com?x=1", "https://u:p@abc.trycloudflare.com", "https://evil.com",
            "https://abc.trycloudflare.com.evil.com", "https://127.0.0.1:11434", "https://169.254.169.254",
            "ftp://abc.trycloudflare.com", "", "nao e url"})
    void recusaEnderecoForaDaRegra(String url) {
        var e = new EnderecoGenai(props("", "k"));
        assertThatThrownBy(() -> e.validar(url)).isInstanceOf(ErroApi.class);
    }

    @Test void semConfiguracaoNemRegistroNaoHaGenai() {
        var e = new EnderecoGenai(props("", "k"));
        assertThat(e.configurado()).isFalse();
        assertThat(e.origem()).isEqualTo("nenhum");
    }

    @Test void chatPassaAUsarOEnderecoRegistrado() throws Exception {
        HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        AtomicInteger chamadas = new AtomicInteger();
        server.createContext("/chat", ex -> {
            chamadas.incrementAndGet();
            byte[] body = "{\"resposta\":\"Sim.\",\"fontes\":[],\"confianca\":\"alta\",\"nao_consta\":false}"
                    .getBytes(StandardCharsets.UTF_8);
            ex.getResponseHeaders().add("Content-Type", "application/json");
            ex.sendResponseHeaders(200, body.length);
            ex.getResponseBody().write(body);
            ex.close();
        });
        server.start();
        try {
            PfProps p = props("", "k");
            var endereco = new EnderecoGenai(p);
            var chat = new ChatService(p, new AssistenteTempoReal(null), endereco);
            assertThat(chat.perguntar("Como funciona o Bilhete Único?").disponivel()).isFalse();
            // registrar() é chamado só depois de validar() e de /health no controller; aqui o teste usa loopback.
            endereco.registrar("http://127.0.0.1:" + server.getAddress().getPort());
            assertThat(chat.perguntar("Como funciona o Bilhete Único?").disponivel()).isTrue();
            assertThat(chamadas.get()).isEqualTo(1);
            assertThat(endereco.origem()).isEqualTo("registro");
        } finally {
            server.stop(0);
        }
    }

    @Test void registroExigeAChaveDaGenai() throws Exception {
        var interceptor = new ChavesApiInterceptor(props("", "chave-genai"), new ObjectMapper());
        assertThat(interceptor.preHandle(pedido(null), new MockHttpServletResponse(), null)).isFalse();
        assertThat(interceptor.preHandle(pedido("errada"), new MockHttpServletResponse(), null)).isFalse();
        assertThat(interceptor.preHandle(pedido("chave-genai"), new MockHttpServletResponse(), null)).isTrue();
        var semChave = new ChavesApiInterceptor(props("", ""), new ObjectMapper());
        MockHttpServletResponse r = new MockHttpServletResponse();
        assertThat(semChave.preHandle(pedido("qualquer"), r, null)).isFalse();
        assertThat(r.getStatus()).isEqualTo(503);
    }

    private static MockHttpServletRequest pedido(String chave) {
        var req = new MockHttpServletRequest("PUT", "/api/genai/endereco");
        req.setAttribute(HandlerMapping.BEST_MATCHING_PATTERN_ATTRIBUTE, "/api/genai/endereco");
        if (chave != null) {
            req.addHeader("X-API-Key", chave);
        }
        return req;
    }
}

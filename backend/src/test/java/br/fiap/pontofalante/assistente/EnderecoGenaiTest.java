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

    /** Servidor local que imita a FastAPI: /health e /identidade configuráveis. */
    private static HttpServer servidor(int statusSaude, String corpoSaude, String chaveDaProva) throws Exception {
        HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.createContext("/health", ex -> {
            byte[] body = corpoSaude.getBytes(StandardCharsets.UTF_8);
            if (statusSaude == 302) {
                ex.getResponseHeaders().add("Location", "https://outro.exemplo/health");
            }
            ex.getResponseHeaders().add("Content-Type", "application/json");
            ex.sendResponseHeaders(statusSaude, body.length);
            ex.getResponseBody().write(body);
            ex.close();
        });
        server.createContext("/identidade", ex -> {
            String desafio = ex.getRequestURI().getQuery().replace("desafio=", "");
            byte[] body = ("{\"prova\":\"" + EnderecoGenaiController.prova(chaveDaProva, desafio) + "\"}")
                    .getBytes(StandardCharsets.UTF_8);
            ex.getResponseHeaders().add("Content-Type", "application/json");
            ex.sendResponseHeaders(200, body.length);
            ex.getResponseBody().write(body);
            ex.close();
        });
        server.start();
        return server;
    }

    private static EnderecoGenaiController controlador(PfProps p) {
        var endereco = new EnderecoGenai(p);
        return new EnderecoGenaiController(p, endereco, new SaudeGenai(p, endereco),
                new ChatService(p, new AssistenteTempoReal(null), endereco));
    }

    @Test void saudeSoValeCom200EStatusOk() throws Exception {
        var c = controlador(props("", "chave-genai"));
        for (var caso : new Object[][] {{200, "{\"status\":\"ok\"}", true}, {302, "{\"status\":\"ok\"}", false},
                {200, "{\"status\":\"degradado\"}", false}, {200, "<html>outro servico</html>", false},
                {503, "{\"status\":\"degradado\"}", false}}) {
            HttpServer s = servidor((int) caso[0], (String) caso[1], "chave-genai");
            try {
                assertThat(c.saudavel("http://127.0.0.1:" + s.getAddress().getPort()))
                        .as("health %s %s", caso[0], caso[1]).isEqualTo(caso[2]);
            } finally {
                s.stop(0);
            }
        }
    }

    @Test void identidadeExigeProvaComAMesmaChave() throws Exception {
        var c = controlador(props("", "chave-genai"));
        HttpServer certo = servidor(200, "{\"status\":\"ok\"}", "chave-genai");
        HttpServer outro = servidor(200, "{\"status\":\"ok\"}", "outra-chave");
        try {
            assertThat(c.provaIdentidade("http://127.0.0.1:" + certo.getAddress().getPort())).isTrue();
            assertThat(c.provaIdentidade("http://127.0.0.1:" + outro.getAddress().getPort())).isFalse();
        } finally {
            certo.stop(0);
            outro.stop(0);
        }
    }

    @Test void falhaDoEnderecoAntigoNaoReabreODisjuntorDoNovo() {
        PfProps p = props("", "k");
        var chat = new ChatService(p, new AssistenteTempoReal(null), new EnderecoGenai(p));
        long antiga = chat.geracaoAtual();
        chat.fecharCircuito(); // novo endereço registrado
        chat.abrirCircuito(antiga); // chamada ao túnel antigo termina em erro depois da troca
        assertThat(chat.circuitoAberto()).isFalse();
        chat.abrirCircuito(chat.geracaoAtual());
        assertThat(chat.circuitoAberto()).isTrue();
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

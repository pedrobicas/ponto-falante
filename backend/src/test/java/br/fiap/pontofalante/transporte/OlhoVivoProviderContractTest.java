package br.fiap.pontofalante.transporte;

import br.fiap.pontofalante.sistema.PfProps;
import com.fasterxml.jackson.databind.ObjectMapper;
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

class OlhoVivoProviderContractTest {
    HttpServer server;
    OlhoVivoProvider provider;
    AtomicInteger logins = new AtomicInteger();
    AtomicInteger consultas = new AtomicInteger();
    boolean recusar;
    boolean semCookie;
    boolean expirar;
    boolean falharConsulta;
    int loginStatus = 200;
    int consultaStatus = 200;
    volatile String userAgentLogin;
    volatile long atrasoLoginMs;

    @BeforeEach void iniciar() throws Exception {
        server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.createContext("/v2.1/Login/Autenticar", ex -> {
            logins.incrementAndGet();
            userAgentLogin = ex.getRequestHeaders().getFirst("User-Agent");
            if (atrasoLoginMs > 0) { try { Thread.sleep(atrasoLoginMs); } catch (InterruptedException e) { Thread.currentThread().interrupt(); } }
            if (!semCookie) ex.getResponseHeaders().add("Set-Cookie", "apiCredentials=local; Path=/; HttpOnly");
            byte[] body = (recusar ? "false" : "true").getBytes(StandardCharsets.UTF_8);
            ex.sendResponseHeaders(loginStatus, body.length);
            ex.getResponseBody().write(body);
            ex.close();
        });
        server.createContext("/v2.1/Linha/Buscar", ex -> {
            int chamada = consultas.incrementAndGet();
            int status = falharConsulta ? 500 : expirar && chamada == 1 ? 401 : consultaStatus;
            if (!"apiCredentials=local".equals(ex.getRequestHeaders().getFirst("Cookie"))) status = 401;
            byte[] body = "[{\"cl\":1273,\"lt\":\"8000\",\"tl\":10,\"sl\":1,\"tp\":\"RAMOS\",\"ts\":\"LAPA\",\"lc\":false}]".getBytes(StandardCharsets.UTF_8);
            ex.sendResponseHeaders(status, body.length);
            ex.getResponseBody().write(body);
            ex.close();
        });
        server.start();
        PfProps props = new Binder(new MapConfigurationPropertySource(Map.of(
                "pf.sptrans-token", "token-local",
                "pf.sptrans-base-url", "http://127.0.0.1:" + server.getAddress().getPort() + "/v2.1",
                "pf.salt", "salt-teste"))).bind("pf", Bindable.of(PfProps.class)).get();
        provider = new OlhoVivoProvider(props, new HashVeiculo(props), new ObjectMapper());
    }

    @AfterEach void parar() { server.stop(0); }

    @Test void autenticaConsultaCookieECache() {
        var linhas = provider.buscarLinhas("8000");
        assertThat(linhas).hasSize(1);
        assertThat(linhas.getFirst().letreiro()).isEqualTo("8000-10");
        provider.buscarLinhas("8000");
        assertThat(logins.get()).isEqualTo(1);
        assertThat(consultas.get()).isEqualTo(1);
    }

    @Test void enviaUserAgentProprioParaNaoSerBarradoPeloCloudflare() {
        provider.buscarLinhas("8000");
        assertThat(userAgentLogin).isEqualTo(OlhoVivoProvider.USER_AGENT);
    }

    @Test void renovaSessaoUmaVezApos401() {
        expirar = true;
        assertThat(provider.buscarLinhas("8000")).hasSize(1);
        assertThat(logins.get()).isEqualTo(2);
        assertThat(consultas.get()).isEqualTo(2);
    }

    @Test void tokenRecusadoIndicaIndisponibilidade() {
        recusar = true;
        assertThat(provider.disponivel()).isFalse();
        assertThatThrownBy(() -> provider.buscarLinhas("8000")).isInstanceOf(TransporteIndisponivelException.class);
        assertThat(consultas.get()).isZero();
    }

    @Test void loginsConcorrentesCompartilhamUmaTentativaEAFalha() throws Exception {
        recusar = true;
        atrasoLoginMs = 150;
        var pool = java.util.concurrent.Executors.newFixedThreadPool(6);
        try {
            var tarefas = new java.util.ArrayList<java.util.concurrent.Future<?>>();
            for (int i = 0; i < 6; i++) {
                final String termo = "linha" + i;   // termos diferentes: sem ajuda do cache
                tarefas.add(pool.submit(() -> provider.buscarLinhas(termo)));
            }
            for (var f : tarefas) {
                assertThatThrownBy(f::get).hasCauseInstanceOf(TransporteIndisponivelException.class);
            }
        } finally {
            pool.shutdownNow();
        }
        assertThat(logins.get()).isEqualTo(1);
        // Falha recente é reaproveitada: nova consulta não chama o login de novo durante a espera.
        assertThatThrownBy(() -> provider.buscarLinhas("outra")).isInstanceOf(TransporteIndisponivelException.class);
        assertThat(logins.get()).isEqualTo(1);
    }

    @Test void loginSemCookieNaoSimulaSucesso() {
        semCookie = true;
        assertThatThrownBy(() -> provider.buscarLinhas("8000")).isInstanceOf(TransporteIndisponivelException.class);
        assertThat(consultas.get()).isZero();
    }

    @Test void falhaDaApiNaoViraListaSimulada() {
        falharConsulta = true;
        assertThatThrownBy(() -> provider.buscarLinhas("8000")).isInstanceOf(TransporteIndisponivelException.class);
    }

    @Test void login403NaoInsisteNemConsultaLinhas() {
        loginStatus = 403;
        assertThatThrownBy(() -> provider.buscarLinhas("8000")).isInstanceOf(TransporteIndisponivelException.class);
        assertThat(logins.get()).isEqualTo(1);
        assertThat(consultas.get()).isZero();
    }

    @Test void consulta403NaoRepeteLogin() {
        consultaStatus = 403;
        assertThatThrownBy(() -> provider.buscarLinhas("8000")).isInstanceOf(TransporteIndisponivelException.class);
        assertThat(logins.get()).isEqualTo(1);
        assertThat(consultas.get()).isEqualTo(1);
    }
}

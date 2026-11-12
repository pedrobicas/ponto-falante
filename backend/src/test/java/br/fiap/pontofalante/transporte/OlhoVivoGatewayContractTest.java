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
import java.util.Base64;
import java.util.Map;
import java.util.concurrent.atomic.AtomicInteger;

import static org.assertj.core.api.Assertions.*;

/** Contrato do gateway da Prefeitura (WSO2): OAuth2 client_credentials em /token e Bearer nas consultas. */
class OlhoVivoGatewayContractTest {
    HttpServer server;
    OlhoVivoProvider provider;
    AtomicInteger tokens = new AtomicInteger();
    AtomicInteger consultas = new AtomicInteger();
    AtomicInteger loginsDiretos = new AtomicInteger();
    volatile String grantRecebido;
    boolean recusarCliente;
    boolean expirarPrimeiro;
    int falhas500;

    @BeforeEach void iniciar() throws Exception {
        server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        String basicEsperado = "Basic " + Base64.getEncoder().encodeToString(
                "chave-gw:segredo-gw".getBytes(StandardCharsets.UTF_8));
        server.createContext("/token", ex -> {
            int n = tokens.incrementAndGet();
            grantRecebido = new String(ex.getRequestBody().readAllBytes(), StandardCharsets.UTF_8);
            boolean ok = !recusarCliente && basicEsperado.equals(ex.getRequestHeaders().getFirst("Authorization"))
                    && "POST".equals(ex.getRequestMethod());
            byte[] body = (ok ? "{\"access_token\":\"tok-" + n + "\",\"token_type\":\"Bearer\",\"expires_in\":3600}"
                    : "{\"error\":\"invalid_client\"}").getBytes(StandardCharsets.UTF_8);
            ex.getResponseHeaders().add("Content-Type", "application/json");
            ex.sendResponseHeaders(ok ? 200 : 401, body.length);
            ex.getResponseBody().write(body);
            ex.close();
        });
        server.createContext("/olhovivo/v2.1/Login/Autenticar", ex -> {
            loginsDiretos.incrementAndGet();
            ex.sendResponseHeaders(500, -1);
            ex.close();
        });
        server.createContext("/olhovivo/v2.1/Linha/Buscar", ex -> {
            int n = consultas.incrementAndGet();
            if (n <= falhas500) {
                byte[] f = "<am:fault><am:code>411</am:code></am:fault>".getBytes(StandardCharsets.UTF_8);
                ex.sendResponseHeaders(500, f.length);
                ex.getResponseBody().write(f);
                ex.close();
                return;
            }
            String auth = ex.getRequestHeaders().getFirst("Authorization");
            boolean valido = auth != null && auth.startsWith("Bearer tok-")
                    && !(expirarPrimeiro && "Bearer tok-1".equals(auth));
            byte[] body = (valido ? "[{\"cl\":1273,\"lt\":\"8000\",\"tl\":10,\"sl\":1,\"tp\":\"RAMOS\",\"ts\":\"LAPA\",\"lc\":false}]"
                    : "<ams:fault>Invalid Credentials</ams:fault>").getBytes(StandardCharsets.UTF_8);
            ex.sendResponseHeaders(valido ? 200 : 401, body.length);
            ex.getResponseBody().write(body);
            ex.close();
        });
        server.start();
        String raiz = "http://127.0.0.1:" + server.getAddress().getPort();
        PfProps props = new Binder(new MapConfigurationPropertySource(Map.of(
                "pf.sptrans-gateway-chave", "chave-gw",
                "pf.sptrans-gateway-segredo", "segredo-gw",
                "pf.sptrans-gateway-url", raiz + "/olhovivo/v2.1",
                "pf.sptrans-gateway-token-url", raiz + "/token",
                "pf.salt", "salt-teste"))).bind("pf", Bindable.of(PfProps.class)).get();
        assertThat(props.temTokenSptrans()).isTrue();
        provider = new OlhoVivoProvider(props, new HashVeiculo(props), new ObjectMapper());
    }

    @AfterEach void parar() { server.stop(0); }

    @Test void obtemTokenUmaVezEConsultaComBearerSemLoginDireto() {
        assertThat(provider.buscarLinhas("8000")).singleElement()
                .satisfies(l -> assertThat(l.letreiro()).isEqualTo("8000-10"));
        provider.buscarLinhas("lapa");
        assertThat(tokens.get()).isEqualTo(1);
        assertThat(consultas.get()).isEqualTo(2);
        assertThat(loginsDiretos.get()).isZero();
        assertThat(grantRecebido).isEqualTo("grant_type=client_credentials");
    }

    @Test void credencialRecusadaNaoConsultaEIndicaIndisponibilidade() {
        recusarCliente = true;
        assertThat(provider.disponivel()).isFalse();
        assertThatThrownBy(() -> provider.buscarLinhas("8000")).isInstanceOf(TransporteIndisponivelException.class);
        assertThat(consultas.get()).isZero();
    }

    @Test void erro500IntermitenteDoGatewayERepetido() {
        falhas500 = 2;
        assertThat(provider.buscarLinhas("8000")).hasSize(1);
        assertThat(consultas.get()).isEqualTo(3);
        assertThat(tokens.get()).isEqualTo(1);
    }

    @Test void erro500PersistenteViraIndisponibilidadeSemLaco() {
        falhas500 = 99;
        assertThatThrownBy(() -> provider.buscarLinhas("8000")).isInstanceOf(TransporteIndisponivelException.class);
        assertThat(consultas.get()).isEqualTo(OlhoVivoProvider.TENTATIVAS_5XX);
    }

    @Test void tokenRevogadoGeraNovoTokenUmaVez() {
        expirarPrimeiro = true;
        assertThat(provider.buscarLinhas("8000")).hasSize(1);
        assertThat(tokens.get()).isEqualTo(2);
        assertThat(consultas.get()).isEqualTo(2);
    }
}

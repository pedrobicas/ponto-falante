package br.fiap.pontofalante.embarque;

import br.fiap.pontofalante.sistema.ErroApi;
import br.fiap.pontofalante.sistema.PfProps;
import com.sun.net.httpserver.HttpServer;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.boot.context.properties.bind.Bindable;
import org.springframework.boot.context.properties.bind.Binder;
import org.springframework.boot.context.properties.source.MapConfigurationPropertySource;

import java.net.InetSocketAddress;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.atomic.AtomicReference;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/** Endereço do serviço de visão informado pelo PC da equipe: só HTTPS em host permitido e com prova de identidade. */
class EnderecoVisaoTest {
    static PfProps props(String url, String chave) {
        Map<String, String> m = new HashMap<>(Map.of("pf.salt", "salt-teste"));
        m.put("pf.visao-url", url);
        m.put("pf.visao-servico-chave", chave);
        return new Binder(new MapConfigurationPropertySource(m)).bind("pf", Bindable.of(PfProps.class)).get();
    }

    @Test
    void aceitaTunelRapidoEHostConfigurado() {
        var e = new EnderecoVisao(props("https://visao.exemplo.org/", "k"));
        assertThat(e.validar("https://tres-palavras-aqui.trycloudflare.com/")).isEqualTo("https://tres-palavras-aqui.trycloudflare.com");
        assertThat(e.validar("https://VISAO.exemplo.org")).isEqualTo("https://visao.exemplo.org");
        assertThat(e.base()).contains("https://visao.exemplo.org");
        assertThat(e.origem()).isEqualTo("configuracao");
    }

    @ParameterizedTest
    @ValueSource(strings = {"http://abc.trycloudflare.com", "https://abc.trycloudflare.com/v1/letreiro",
            "https://abc.trycloudflare.com?x=1", "https://u:p@abc.trycloudflare.com", "https://evil.com",
            "https://abc.trycloudflare.com.evil.com", "https://127.0.0.1:8090", "https://169.254.169.254", "", "nao e url"})
    void recusaEnderecoForaDaRegra(String url) {
        var e = new EnderecoVisao(props("", "k"));
        assertThatThrownBy(() -> e.validar(url)).isInstanceOf(ErroApi.class);
    }

    @Test
    void semConfiguracaoNemRegistroNaoHaVisao() {
        var e = new EnderecoVisao(props("", "k"));
        assertThat(e.base()).isEmpty();
        assertThat(e.origem()).isEqualTo("nenhum");
        assertThat(new ReconhecedorLetreiro(props("", "k"), e).conectado()).isFalse();
    }

    @Test
    void provaDeIdentidadeIgualAoServicoPython() {
        // Mesmo vetor de visao/tests/test_servico.py::test_prova_identidade_igual_ao_backend
        assertThat(EnderecoVisaoController.prova("k".repeat(16), "00".repeat(8)))
                .isEqualTo("15e824b3f92d100986132704c3b77fc10c24f1d93b940d7eb2384f5a1ae11c73");
    }

    /** Serviço falso no contrato do visao/servico: /health e /identidade. */
    static HttpServer servico(String chave, AtomicReference<String> saude) throws Exception {
        HttpServer s = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        s.createContext("/health", t -> {
            byte[] r = ("{\"status\":\"" + saude.get() + "\"}").getBytes(StandardCharsets.UTF_8);
            t.getResponseHeaders().add("Content-Type", "application/json");
            t.sendResponseHeaders("ok".equals(saude.get()) ? 200 : 503, r.length);
            t.getResponseBody().write(r);
            t.close();
        });
        s.createContext("/identidade", t -> {
            String desafio = URI.create("http://x" + t.getRequestURI()).getQuery().replace("desafio=", "");
            byte[] r = ("{\"prova\":\"" + EnderecoVisaoController.prova(chave, desafio) + "\"}").getBytes(StandardCharsets.UTF_8);
            t.getResponseHeaders().add("Content-Type", "application/json");
            t.sendResponseHeaders(200, r.length);
            t.getResponseBody().write(r);
            t.close();
        });
        s.start();
        return s;
    }

    @Test
    void verificaSaudeEIdentidadeAntesDeAceitar() throws Exception {
        var saude = new AtomicReference<>("ok");
        HttpServer certo = servico("chave-certa-123456", saude);
        HttpServer impostor = servico("outra-chave-99999", saude);
        try {
            var p = props("", "chave-certa-123456");
            var e = new EnderecoVisao(p);
            var c = new EnderecoVisaoController(p, e, new ReconhecedorLetreiro(p, e));
            String urlCerta = "http://127.0.0.1:" + certo.getAddress().getPort();
            String urlImpostor = "http://127.0.0.1:" + impostor.getAddress().getPort();
            assertThat(c.saudavel(urlCerta)).isTrue();
            assertThat(c.provaIdentidade(urlCerta)).isTrue();
            assertThat(c.provaIdentidade(urlImpostor)).isFalse();
            saude.set("carregando");
            assertThat(c.saudavel(urlCerta)).isFalse();
            assertThat(c.saudavel("http://127.0.0.1:1")).isFalse();
        } finally {
            certo.stop(0);
            impostor.stop(0);
        }
    }

    @Test
    void disponivelSoComHealthOk() throws Exception {
        var saude = new AtomicReference<>("ok");
        HttpServer s = servico("k", saude);
        try {
            var p = props("http://127.0.0.1:" + s.getAddress().getPort(), "k");
            var r = new ReconhecedorLetreiro(p, new EnderecoVisao(p));
            assertThat(r.conectado()).isTrue();
            assertThat(r.disponivel()).isTrue();
            saude.set("carregando");
            r.esquecerSaude();
            assertThat(r.disponivel()).isFalse();
        } finally {
            s.stop(0);
        }
        var p = props("http://127.0.0.1:1", "k");
        assertThat(new ReconhecedorLetreiro(p, new EnderecoVisao(p)).disponivel()).isFalse();
    }
}

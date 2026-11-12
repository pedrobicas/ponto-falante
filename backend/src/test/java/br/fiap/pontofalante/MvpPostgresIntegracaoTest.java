package br.fiap.pontofalante;

import io.zonky.test.db.postgres.embedded.EmbeddedPostgres;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import java.net.URI;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.junit.jupiter.api.condition.EnabledIfSystemProperty;
import org.junit.jupiter.api.io.TempDir;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.TimeUnit;
import static org.assertj.core.api.Assertions.assertThat;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT,
        properties = {"PF_SPTRANS_MODO=demo", "pf.sptrans-token=token-local-nao-enviar",
                "pf.sptrans-base-url=http://127.0.0.1:1/v2.1", "pf.genai-url=", "pf.rpa-api-key=chave-local"})
@AutoConfigureMockMvc
class MvpPostgresIntegracaoTest {
    static final EmbeddedPostgres POSTGRES = iniciarPostgres();
    static EmbeddedPostgres iniciarPostgres() {
        try { return EmbeddedPostgres.start(); }
        catch (java.io.IOException e) { throw new IllegalStateException("PostgreSQL de teste nao iniciou", e); }
    }
    @DynamicPropertySource static void banco(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", () -> POSTGRES.getJdbcUrl("postgres", "postgres"));
        registry.add("spring.datasource.username", () -> "postgres");
        registry.add("spring.datasource.password", () -> "");
    }
    @Autowired MockMvc mvc;
    @LocalServerPort int porta;
    @TempDir Path artefatos;

    @Test void statusDeclaraDemonstracaoEGenaiIndisponivel() throws Exception {
        mvc.perform(get("/api/status")).andExpect(status().isOk())
                .andExpect(jsonPath("$.sptrans").value("DEMO"))
                .andExpect(jsonPath("$.assistente").value("INDISPONIVEL"));
    }

    @Test void pontosEPrevisoesSeguemContratoAngular() throws Exception {
        mvc.perform(get("/api/pontos").param("busca", "paulista").param("modo", "demo"))
                .andExpect(status().isOk()).andExpect(jsonPath("$.fonte").value("SIMULADO"))
                .andExpect(jsonPath("$.pontos").isArray());
    }

    @Test void genaiAusenteDegradaComRespostaPublicaValida() throws Exception {
        mvc.perform(post("/api/chat").contentType("application/json").content("{\"pergunta\":\"Como consultar meu onibus?\"}"))
                .andExpect(status().isOk()).andExpect(jsonPath("$.disponivel").value(false))
                .andExpect(jsonPath("$.nao_consta").value(true)).andExpect(jsonPath("$.fontes").isEmpty());
    }

    @Test void boletimExigeChaveAntesDeLerCorpo() throws Exception {
        mvc.perform(post("/api/boletim").contentType("application/json").content("{}"))
                .andExpect(status().isUnauthorized()).andExpect(jsonPath("$.codigo").value("CHAVE_INVALIDA"));
    }

    @ParameterizedTest
    @ValueSource(strings = {"/api/boletim;verificacao", "/api/%62oletim"})
    void caminhoNormalizadoTambemExigeChaveRpa(String rota) throws Exception {
        mvc.perform(post(URI.create(rota)).contentType("application/json").content("{}"))
                .andExpect(status().isUnauthorized());
    }

    @ParameterizedTest
    @ValueSource(strings = {"/api/integracoes/dados/passagens;verificacao", "/api/integracoes/dados/%70assagens"})
    void exportacaoCodificadaContinuaDesativadaSemChave(String rota) throws Exception {
        mvc.perform(get(URI.create(rota + "?de=2000-01-02&ate=2000-01-01")))
                .andExpect(status().isServiceUnavailable());
    }

    @ParameterizedTest
    @ValueSource(strings = {"/api/integracoes/visao/deteccoes;verificacao", "/api/integracoes/visao/%64eteccoes",
            "/api/integracoes/dispositivos/eventos;verificacao", "/api/integracoes/dispositivos/%65ventos"})
    void integracoesCodificadasContinuamDesativadasSemChave(String rota) throws Exception {
        mvc.perform(post(URI.create(rota)).contentType("application/json").content("{}"))
                .andExpect(status().isServiceUnavailable());
    }

    @Test void contextoDaAplicacaoNaoIgnoraAutenticacao() throws Exception {
        mvc.perform(post("/pf/api/boletim").contextPath("/pf").contentType("application/json").content("{}"))
                .andExpect(status().isUnauthorized());
    }

    @ParameterizedTest
    @ValueSource(strings = {
            "\"fonte_dados\":{\"olhovivo\":0,\"simulador\":100}",
            "\"dados_simulados\":null,\"fonte_dados\":{\"olhovivo\":0,\"simulador\":100}",
            "\"dados_simulados\":false,\"fonte_dados\":{\"olhovivo\":0,\"simulador\":100}",
            "\"dados_simulados\":true,\"fonte_dados\":{\"olhovivo\":10,\"simulador\":0}",
            "\"dados_simulados\":false"})
    @Test void boletimComLinhaCitandoFonteSemRegistrosERejeitado() throws Exception {
        String body = "{\"data_referencia\":\"2026-11-09\",\"gerado_em\":\"2026-11-10T06:00:00-03:00\","
                + "\"desatualizado\":false,\"resumo_falado\":\"x\",\"dados_simulados\":true,"
                + "\"fonte_dados\":{\"olhovivo\":0,\"simulador\":5},"
                + "\"linhas\":[{\"linha\":\"875A-10\",\"fontes\":[\"olhovivo\"]}]}";
        mvc.perform(post("/api/boletim").header("X-API-Key", "chave-local")
                .contentType("application/json").content(body)).andExpect(status().isBadRequest());
    }

    void boletimSemProvenienciaCoerenteERejeitado(String proveniencia) throws Exception {
        String body = "{\"data_referencia\":\"2026-11-09\",\"gerado_em\":\"2026-11-10T06:00:00-03:00\","
                + "\"desatualizado\":false,\"linhas\":[],\"resumo_falado\":\"x\"," + proveniencia + "}";
        mvc.perform(post("/api/boletim").header("X-API-Key", "chave-local")
                .contentType("application/json").content(body)).andExpect(status().isBadRequest());
    }

    @Test void chatIgnoraXForwardedForEmConexaoDireta() throws Exception {
        int limite = 10;
        for (int i = 0; i < limite; i++) {
            final int n = i;
            mvc.perform(post("/api/chat").with(r -> { r.setRemoteAddr("203.0.113.77"); return r; })
                    .header("X-Forwarded-For", "198.51.100." + n)
                    .contentType("application/json").content("{\"pergunta\":\"Teste de limite\"}"))
                    .andExpect(status().isOk());
        }
        mvc.perform(post("/api/chat").with(r -> { r.setRemoteAddr("203.0.113.77"); return r; })
                .header("X-Forwarded-For", "198.51.100.200")
                .contentType("application/json").content("{\"pergunta\":\"Teste de limite\"}"))
                .andExpect(status().isTooManyRequests());
    }

    @Test void publicaELeBoletimNoPostgres() throws Exception {
        String body = """
                {"data_referencia":"2026-11-10","gerado_em":"2026-11-11T06:00:00-03:00",
                 "desatualizado":false,"dados_simulados":true,"fonte_dados":{"olhovivo":0,"simulador":5},
                 "linhas":[],"resumo_falado":"Boletim de teste."}
                """;
        mvc.perform(post("/api/boletim").header("X-API-Key", "chave-local")
                .contentType("application/json").content(body)).andExpect(status().isCreated());
        mvc.perform(get("/api/boletim/2026-11-10")).andExpect(status().isOk())
                .andExpect(jsonPath("$.resumo_falado").value("Boletim de teste."))
                .andExpect(jsonPath("$.recebido_em").isString());
    }

    @Test void navegacaoHtmlNaoReutilizaBuildAntigoPorDataFixaDoJar() throws Exception {
        mvc.perform(get("/sobre").header("If-Modified-Since", "Fri, 01 Feb 1980 00:00:00 GMT"))
                .andExpect(status().isOk())
                .andExpect(header().string("Cache-Control", org.hamcrest.Matchers.containsString("no-store")));
    }

    @Test
    @EnabledIfSystemProperty(named = "pf.integration.root", matches = ".+")
    void scriptsHttpERpaContraServidorReal() throws Exception {
        Path raiz = Path.of(System.getProperty("pf.integration.root"));
        String python = System.getProperty("pf.integration.python", "python");
        for (String script : List.of("testar_mvp.py", "testar_rpa_local.py")) {
            List<String> comando = new ArrayList<>(List.of(python,
                    raiz.resolve("scripts/integracao/" + script).toString(),
                    "--url", "http://127.0.0.1:" + porta));
            if (script.equals("testar_mvp.py") && !Boolean.getBoolean("pf.integration.angular")) {
                comando.add("--api-only");
            }
            Path log = artefatos.resolve(script + ".log");
            ProcessBuilder builder = new ProcessBuilder(comando) // nosemgrep -- teste: comando fixo do próprio repositório
                   .redirectErrorStream(true).redirectOutput(log.toFile());
            builder.environment().put("RPA_API_KEY", "chave-local");
            builder.environment().put("PYTHONUTF8", "1");
            Process processo = builder.start();
            boolean terminou = processo.waitFor(90, TimeUnit.SECONDS);
            if (!terminou) processo.destroyForcibly();
            assertThat(terminou).as("Tempo limite do script %s", script).isTrue();
            assertThat(processo.exitValue()).as("%s: %s", script, Files.readString(log)).isZero();
            System.out.println(Files.readString(log));
        }
    }
}

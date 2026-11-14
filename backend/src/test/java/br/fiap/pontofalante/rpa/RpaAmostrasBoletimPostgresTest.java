package br.fiap.pontofalante.rpa;

import io.zonky.test.db.postgres.embedded.EmbeddedPostgres;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.servlet.MockMvc;

import java.net.URI;
import java.time.OffsetDateTime;
import java.time.ZoneId;
import java.time.temporal.ChronoUnit;

import static org.hamcrest.Matchers.hasItem;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/** Coletor de amostras reais (POST/GET /api/rpa/amostras) e categorias de honestidade do boletim. */
@SpringBootTest(properties = {"PF_SPTRANS_MODO=demo", "pf.sptrans-token=", "pf.genai-url=",
        "pf.rpa-api-key=chave-rpa-teste"})
@AutoConfigureMockMvc
class RpaAmostrasBoletimPostgresTest {
    static final EmbeddedPostgres POSTGRES = iniciar();
    static final ZoneId SP = ZoneId.of("America/Sao_Paulo");
    static final String CHAVE = "chave-rpa-teste";

    static EmbeddedPostgres iniciar() {
        try {
            return EmbeddedPostgres.start();
        } catch (java.io.IOException e) {
            throw new IllegalStateException("PostgreSQL de teste nao iniciou", e);
        }
    }

    @DynamicPropertySource
    static void banco(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", () -> POSTGRES.getJdbcUrl("postgres", "postgres"));
        registry.add("spring.datasource.username", () -> "postgres");
        registry.add("spring.datasource.password", () -> "");
    }

    @Autowired
    MockMvc mvc;

    static String amostra(String ponto, OffsetDateTime quando, String fonte, String onibus) {
        return "{\"ponto\":\"" + ponto + "\",\"consultado_em\":\"" + quando + "\",\"horario_referencia\":\""
                + String.format("%02d:%02d", quando.getHour(), quando.getMinute()) + "\",\"fonte\":\"" + fonte
                + "\",\"tipo\":\"PREVISAO\",\"onibus\":" + onibus + "}";
    }

    static final String ONIBUS = "[{\"letreiro\":\"8700-10\",\"destino\":\"PCA. RAMOS\",\"sentido\":1,"
            + "\"previsto_em\":\"10:06\",\"minutos\":2,\"acessivel\":true,\"veiculo\":\"0ce80ed88d\"}]";

    @Test
    void envioSemChaveOuComChaveErradaERecusadoAntesDeLerCorpo() throws Exception {
        mvc.perform(post("/api/rpa/amostras").contentType("application/json").content("{}"))
                .andExpect(status().isUnauthorized()).andExpect(jsonPath("$.codigo").value("CHAVE_INVALIDA"));
        mvc.perform(post("/api/rpa/amostras").header("X-API-Key", "errada").contentType("application/json")
                .content("{}")).andExpect(status().isUnauthorized());
    }

    @ParameterizedTest
    @ValueSource(strings = {"/api/rpa/amostras;verificacao", "/api/rpa/%61mostras"})
    void caminhoNormalizadoTambemExigeChave(String rota) throws Exception {
        mvc.perform(post(URI.create(rota)).contentType("application/json").content("{}"))
                .andExpect(status().isUnauthorized());
    }

    @Test
    void amostraRealGravaRelEIgnoraDuplicada() throws Exception {
        OffsetDateTime agora = OffsetDateTime.now(SP).truncatedTo(ChronoUnit.SECONDS).minusMinutes(1);
        String corpo = "{\"execucao_id\":\"teste-1\",\"amostras\":[" + amostra("260015039", agora, "OLHO_VIVO", ONIBUS) + "]}";
        mvc.perform(post("/api/rpa/amostras").header("X-API-Key", CHAVE).contentType("application/json").content(corpo))
                .andExpect(status().isOk()).andExpect(jsonPath("$.gravadas").value(1))
                .andExpect(jsonPath("$.duplicadas").value(0));
        mvc.perform(post("/api/rpa/amostras").header("X-API-Key", CHAVE).contentType("application/json").content(corpo))
                .andExpect(status().isOk()).andExpect(jsonPath("$.gravadas").value(0))
                .andExpect(jsonPath("$.duplicadas").value(1));
        mvc.perform(get("/api/rpa/amostras").param("data", agora.toLocalDate().toString()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$[?(@.ponto == '260015039')].fonte", hasItem("olhovivo")))
                .andExpect(jsonPath("$[?(@.ponto == '260015039')].tipo_registro", hasItem("AMOSTRA_PREVISAO")))
                .andExpect(jsonPath("$[?(@.ponto == '260015039')].onibus[0].linha", hasItem("8700-10")));
    }

    @Test
    void loteParcialGravaValidasERecusaSimuladaAntigaEInvalida() throws Exception {
        OffsetDateTime agora = OffsetDateTime.now(SP).truncatedTo(ChronoUnit.SECONDS).minusMinutes(2);
        String corpo = "{\"amostras\":["
                + amostra("260016855", agora, "OLHO_VIVO", ONIBUS) + ","
                + amostra("260016855", agora.minusMinutes(1), "SIMULADO", ONIBUS) + ","
                + amostra("260016855", agora.minusDays(3), "OLHO_VIVO", ONIBUS) + ","
                + amostra("260016855", agora.minusMinutes(3), "OLHO_VIVO",
                "[{\"letreiro\":\"8700-10\",\"previsto_em\":\"25:99\",\"minutos\":2}]") + ","
                + amostra("ponto com espaço", agora.minusMinutes(4), "OLHO_VIVO", "[]") + "]}";
        mvc.perform(post("/api/rpa/amostras").header("X-API-Key", CHAVE).contentType("application/json").content(corpo))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.recebidas").value(5))
                .andExpect(jsonPath("$.gravadas").value(1))
                .andExpect(jsonPath("$.rejeitadas[0].motivo").value("fonte_simulada"))
                .andExpect(jsonPath("$.rejeitadas[1].motivo").value("fora_da_janela"))
                .andExpect(jsonPath("$.rejeitadas[2].motivo").value("onibus_invalido"))
                .andExpect(jsonPath("$.rejeitadas[3].motivo").value("ponto_invalido"));
    }

    @Test
    void corpoSemListaDeAmostrasE400() throws Exception {
        mvc.perform(post("/api/rpa/amostras").header("X-API-Key", CHAVE).contentType("application/json")
                .content("{\"amostras\":[]}")).andExpect(status().isBadRequest());
        mvc.perform(post("/api/rpa/amostras").header("X-API-Key", CHAVE).contentType("application/json")
                .content("[1,2]")).andExpect(status().isBadRequest());
    }

    @ParameterizedTest
    @ValueSource(strings = {"CHEGADA", "SIMULACAO", ""})
    void tipoIncorretoNaoViraPrevisao(String tipo) throws Exception {
        String a = amostra("tipo-teste", OffsetDateTime.now(SP), "OLHO_VIVO", ONIBUS)
                .replace("\"tipo\":\"PREVISAO\"", "\"tipo\":\"" + tipo + "\"");
        mvc.perform(post("/api/rpa/amostras").header("X-API-Key", CHAVE).contentType("application/json")
                .content("{\"amostras\":[" + a + "]}"))
                .andExpect(status().isOk()).andExpect(jsonPath("$.gravadas").value(0))
                .andExpect(jsonPath("$.rejeitadas[0].motivo").value("tipo_inesperado"));
    }

    @Test
    void minutosComOverflowNaoViraramPrevisaoCurta() throws Exception {
        String a = amostra("overflow-teste", OffsetDateTime.now(SP), "OLHO_VIVO",
                ONIBUS.replace("\"minutos\":2", "\"minutos\":4294967298"));
        mvc.perform(post("/api/rpa/amostras").header("X-API-Key", CHAVE).contentType("application/json")
                .content("{\"amostras\":[" + a + "]}"))
                .andExpect(status().isOk()).andExpect(jsonPath("$.gravadas").value(0))
                .andExpect(jsonPath("$.rejeitadas[0].motivo").value("onibus_invalido"));
    }

    @Test
    void duplicadaDentroDoMesmoLoteNaoAbortaTransacao() throws Exception {
        String a = amostra("duplicada-no-lote", OffsetDateTime.now(SP), "OLHO_VIVO", ONIBUS);
        mvc.perform(post("/api/rpa/amostras").header("X-API-Key", CHAVE).contentType("application/json")
                .content("{\"amostras\":[" + a + "," + a + "]}"))
                .andExpect(status().isOk()).andExpect(jsonPath("$.gravadas").value(1))
                .andExpect(jsonPath("$.duplicadas").value(1));
    }

    static String boletim(String data, String natureza, String fontes, String linhas) {
        return "{\"data_referencia\":\"" + data + "\",\"gerado_em\":\"2026-11-12T06:00:00-03:00\","
                + "\"desatualizado\":false,\"resumo_falado\":\"x\",\"dados_simulados\":false,"
                + "\"natureza_dados\":\"" + natureza + "\",\"fonte_dados\":" + fontes + ",\"linhas\":" + linhas + "}";
    }

    @Test
    void boletimEstimadoCoerenteEAceitoEApareceNaLista() throws Exception {
        String linhas = "[{\"linha\":\"8700-10\",\"status\":\"ATENCAO\",\"classificacao\":\"ESTIMADO\","
                + "\"fontes\":[\"olhovivo\"],\"atraso_medio_min\":null},"
                + "{\"linha\":\"702U-10\",\"status\":\"SEM_DADOS\",\"classificacao\":\"INDISPONIVEL\",\"fontes\":[]}]";
        mvc.perform(post("/api/boletim").header("X-API-Key", CHAVE).contentType("application/json")
                        .content(boletim("2026-10-01", "ESTIMADO", "{\"olhovivo\":40,\"simulador\":0}", linhas)))
                .andExpect(status().isCreated());
        mvc.perform(get("/api/boletins")).andExpect(status().isOk())
                .andExpect(jsonPath("$[?(@.data_referencia == '2026-10-01')].natureza_dados", hasItem("ESTIMADO")));
    }

    @ParameterizedTest
    @ValueSource(strings = {
            // previsão não é atraso medido
            "ESTIMADO|{\"olhovivo\":40,\"simulador\":0}|[{\"linha\":\"8700-10\",\"status\":\"CRITICA\",\"classificacao\":\"ESTIMADO\",\"atraso_medio_min\":12.0}]",
            // ESTIMADO não se mistura com simulação
            "ESTIMADO|{\"olhovivo\":40,\"simulador\":5}|[]",
            // INDISPONIVEL não pode afirmar situação normal, mesmo com consultas reais
            "INDISPONIVEL|{\"olhovivo\":40,\"simulador\":0}|[{\"linha\":\"8700-10\",\"status\":\"OK\"}]",
            // linha sem dados não pode ter decisão
            "ESTIMADO|{\"olhovivo\":40,\"simulador\":0}|[{\"linha\":\"8700-10\",\"status\":\"CRITICA\",\"classificacao\":\"INDISPONIVEL\"}]",
            // linha ESTIMADO citando simulador
            "ESTIMADO|{\"olhovivo\":40,\"simulador\":0}|[{\"linha\":\"8700-10\",\"status\":\"OK\",\"classificacao\":\"ESTIMADO\",\"fontes\":[\"simulador\"]}]",
            // categoria desconhecida
            "VERIFICADO|{\"olhovivo\":40,\"simulador\":0}|[]"})
    void boletimComCategoriaIncoerenteERejeitado(String caso) throws Exception {
        String[] p = caso.split("\\|");
        mvc.perform(post("/api/boletim").header("X-API-Key", CHAVE).contentType("application/json")
                .content(boletim("2026-10-02", p[0], p[1], p[2]))).andExpect(status().isBadRequest());
    }

    @Test void consultasReaisPodemSerInsuficientesParaClassificarOperacao() throws Exception {
        mvc.perform(post("/api/boletim").header("X-API-Key", CHAVE).contentType("application/json")
                .content(boletim("2026-10-03", "INDISPONIVEL", "{\"olhovivo\":1,\"simulador\":0}",
                        "[{\"linha\":\"8700-10\",\"status\":\"SEM_DADOS\",\"classificacao\":\"INDISPONIVEL\",\"fontes\":[\"olhovivo\"]}]")))
                .andExpect(status().isCreated());
    }
}

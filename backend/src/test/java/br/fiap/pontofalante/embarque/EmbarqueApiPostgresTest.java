package br.fiap.pontofalante.embarque;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.zonky.test.db.postgres.embedded.EmbeddedPostgres;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.servlet.MockMvc;

import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

/** Embarque Assistido de ponta a ponta contra PostgreSQL real (embutido), com a SPTrans em demonstração. */
@SpringBootTest(properties = {"PF_SPTRANS_MODO=demo", "pf.sptrans-token=", "pf.genai-url=", "pf.rpa-api-key=chave-local",
        "pf.visao-url="})
@AutoConfigureMockMvc
class EmbarqueApiPostgresTest {
    static final EmbeddedPostgres POSTGRES = iniciar();
    static final String A = "a".repeat(32);
    static final String B = "b".repeat(32);

    static EmbeddedPostgres iniciar() {
        try { return EmbeddedPostgres.start(); }
        catch (java.io.IOException e) { throw new IllegalStateException("PostgreSQL de teste nao iniciou", e); }
    }

    @DynamicPropertySource
    static void banco(DynamicPropertyRegistry r) {
        r.add("spring.datasource.url", () -> POSTGRES.getJdbcUrl("postgres", "postgres"));
        r.add("spring.datasource.username", () -> "postgres");
        r.add("spring.datasource.password", () -> "");
    }

    @Autowired MockMvc mvc;
    @Autowired JdbcTemplate jdbc;
    final ObjectMapper json = new ObjectMapper();

    private JsonNode ler(org.springframework.test.web.servlet.ResultActions r) throws Exception {
        return json.readTree(r.andReturn().getResponse().getContentAsString(java.nio.charset.StandardCharsets.UTF_8));
    }

    /** Primeira linha prevista no ponto de demonstração, para não depender do horário em que o teste roda. */
    private JsonNode primeiraPrevista(long ponto) throws Exception {
        JsonNode p = ler(mvc.perform(get("/api/pontos/" + ponto + "/previsoes").param("modo", "demo")).andExpect(status().isOk()));
        return p.path("onibus").get(0);
    }

    @Test
    void favoritosSaoPorAparelhoIdempotentesEApagaveis() throws Exception {
        String corpo = "{\"ponto\":990001,\"ponto_nome\":\"Paulista - Museu de Arte\",\"linha\":\"8000-10\",\"sentido\":1,"
                + "\"destino\":\"Lapa\",\"apelido\":\"Trabalho\",\"simulado\":true}";
        JsonNode f = ler(mvc.perform(post("/api/embarque/favoritos").header("X-PF-Dispositivo", A)
                .contentType("application/json").content(corpo)).andExpect(status().isCreated()));
        assertThat(f.path("apelido").asText()).isEqualTo("Trabalho");
        // Mesmo trajeto de novo: não duplica (a voz pode repetir o comando).
        mvc.perform(post("/api/embarque/favoritos").header("X-PF-Dispositivo", A).contentType("application/json")
                .content(corpo.replace("Trabalho", "Serviço"))).andExpect(status().isCreated())
                .andExpect(jsonPath("$.id").value(f.path("id").asLong())).andExpect(jsonPath("$.apelido").value("Serviço"));
        mvc.perform(get("/api/embarque/favoritos").header("X-PF-Dispositivo", A))
                .andExpect(status().isOk()).andExpect(jsonPath("$.length()").value(1));
        // Outro aparelho não vê nem remove.
        mvc.perform(get("/api/embarque/favoritos").header("X-PF-Dispositivo", B)).andExpect(jsonPath("$.length()").value(0));
        mvc.perform(delete("/api/embarque/favoritos/" + f.path("id").asLong()).header("X-PF-Dispositivo", B))
                .andExpect(status().isNotFound());
        mvc.perform(patch("/api/embarque/favoritos/" + f.path("id").asLong()).header("X-PF-Dispositivo", A)
                .contentType("application/json").content("{\"apelido\":\"<b>Casa</b>\"}"))
                .andExpect(jsonPath("$.apelido").value("bCasa/b"));
        // O banco guarda só o hash do identificador, nunca o identificador.
        assertThat(jdbc.queryForObject("select count(*) from embarque_favorito where dispositivo = ?", Long.class, A)).isZero();
        mvc.perform(delete("/api/embarque/favoritos/" + f.path("id").asLong()).header("X-PF-Dispositivo", A))
                .andExpect(status().isNoContent());
    }

    @Test
    void validaAparelhoELinha() throws Exception {
        mvc.perform(get("/api/embarque/favoritos")).andExpect(status().isBadRequest());
        mvc.perform(get("/api/embarque/favoritos").header("X-PF-Dispositivo", "nao-hex")).andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.codigo").value("DISPOSITIVO_INVALIDO"));
        mvc.perform(post("/api/embarque/favoritos").header("X-PF-Dispositivo", A).contentType("application/json")
                .content("{\"ponto\":1,\"ponto_nome\":\"x\",\"linha\":\"'; drop table x\"}"))
                .andExpect(status().isBadRequest());
        mvc.perform(post("/api/embarque/sessoes").header("X-PF-Dispositivo", A).contentType("application/json")
                .content("{\"ponto\":990001,\"ponto_nome\":\"x\",\"linhas\":[],\"modo\":\"demo\"}"))
                .andExpect(status().isBadRequest());
    }

    @Test
    void acompanhamentoFiltraAsLinhasEscolhidasERegistraODesfecho() throws Exception {
        JsonNode alvo = primeiraPrevista(990002);
        String letreiro = alvo.path("letreiro").asText();
        JsonNode s = ler(mvc.perform(post("/api/embarque/sessoes").header("X-PF-Dispositivo", A).contentType("application/json")
                .content("{\"ponto\":990002,\"ponto_nome\":\"Paulista - Trianon\",\"modo\":\"demo\",\"linhas\":[{\"letreiro\":\""
                        + letreiro.toLowerCase() + "\"}]}")).andExpect(status().isCreated()));
        String id = s.path("id").asText();
        assertThat(s.path("simulado").asBoolean()).isTrue();
        assertThat(s.path("linhas").get(0).path("letreiro").asText()).isEqualTo(letreiro);

        JsonNode sit = ler(mvc.perform(get("/api/embarque/sessoes/" + id + "/situacao").header("X-PF-Dispositivo", A))
                .andExpect(status().isOk()));
        assertThat(sit.path("fonte").asText()).isEqualTo("SIMULADO");
        assertThat(sit.path("onibus").size()).isPositive();
        for (JsonNode o : sit.path("onibus")) assertThat(o.path("letreiro").asText()).isEqualTo(letreiro);
        assertThat(sit.path("proximo").path("letreiro").asText()).isEqualTo(letreiro);
        assertThat(sit.path("frase_falada").asText()).startsWith("Demonstração.");
        assertThat(sit.path("outras_linhas_previstas").toString()).doesNotContain("\"" + letreiro + "\"");

        mvc.perform(get("/api/embarque/sessoes/atual").header("X-PF-Dispositivo", A)).andExpect(jsonPath("$.id").value(id));
        mvc.perform(get("/api/embarque/sessoes/" + id + "/situacao").header("X-PF-Dispositivo", B)).andExpect(status().isNotFound());

        mvc.perform(post("/api/embarque/sessoes/" + id + "/encerrar").header("X-PF-Dispositivo", A)
                .contentType("application/json").content("{\"desfecho\":\"EMBARQUEI\"}"))
                .andExpect(status().isOk()).andExpect(jsonPath("$.desfecho").value("EMBARQUEI"));
        mvc.perform(get("/api/embarque/sessoes/" + id + "/situacao").header("X-PF-Dispositivo", A))
                .andExpect(status().isConflict()).andExpect(jsonPath("$.codigo").value("ACOMPANHAMENTO_ENCERRADO"));
        mvc.perform(get("/api/embarque/sessoes/atual").header("X-PF-Dispositivo", A)).andExpect(status().isNoContent());

        Integer consultas = jdbc.queryForObject("select consultas from embarque_sessao where id = ?", Integer.class, UUID.fromString(id));
        assertThat(consultas).isEqualTo(1);
    }

    @Test
    void novoAcompanhamentoSubstituiOAnteriorEDadosPodemSerApagados() throws Exception {
        String corpo = "{\"ponto\":990003,\"ponto_nome\":\"Brigadeiro\",\"modo\":\"demo\",\"linhas\":[{\"letreiro\":\"6200-10\",\"sentido\":1}]}";
        String primeira = ler(mvc.perform(post("/api/embarque/sessoes").header("X-PF-Dispositivo", B)
                .contentType("application/json").content(corpo))).path("id").asText();
        mvc.perform(post("/api/embarque/sessoes").header("X-PF-Dispositivo", B).contentType("application/json").content(corpo))
                .andExpect(status().isCreated());
        assertThat(jdbc.queryForObject("select desfecho from embarque_sessao where id = ?", String.class, UUID.fromString(primeira)))
                .isEqualTo("SUBSTITUIDA");
        mvc.perform(delete("/api/embarque/dados").header("X-PF-Dispositivo", B)).andExpect(status().isNoContent());
        mvc.perform(get("/api/embarque/sessoes/atual").header("X-PF-Dispositivo", B)).andExpect(status().isNoContent());
        assertThat(jdbc.queryForObject("select count(*) from embarque_sessao where id = ?", Long.class, UUID.fromString(primeira))).isZero();
    }

    @Test
    void visaoSemModeloRespondeQueNaoEstaConectadaSemInventarResultado() throws Exception {
        mvc.perform(get("/api/status")).andExpect(jsonPath("$.visao").value("NAO_CONECTADA"));
        mvc.perform(get("/api/embarque/visao")).andExpect(jsonPath("$.conectada").value(false));
        var foto = new MockMultipartFile("imagem", "q.jpg", "image/jpeg", new byte[]{(byte) 0xFF, (byte) 0xD8, (byte) 0xFF, 0, 0, 0, 0, 0, 0});
        mvc.perform(multipart("/api/embarque/visao/conferir").file(foto).param("linha_esperada", "875A-10")
                        .header("X-PF-Dispositivo", A))
                .andExpect(status().isServiceUnavailable()).andExpect(jsonPath("$.codigo").value("VISAO_NAO_CONECTADA"));
        assertThat(jdbc.queryForObject("select count(*) from embarque_conferencia_visao", Long.class)).isZero();
    }

    @Test
    void indicadoresSaoAgregadosEIgnoramADemonstracao() throws Exception {
        mvc.perform(get("/api/embarque/indicadores")).andExpect(status().isOk())
                .andExpect(jsonPath("$.acompanhamentos30_dias").value(0))
                .andExpect(jsonPath("$.observacao").isNotEmpty());
    }

    @Test
    void chatOfereceAcompanharDepoisDeUmaPrevisao() throws Exception {
        mvc.perform(post("/api/chat").contentType("application/json")
                        .content("{\"pergunta\":\"e o próximo?\",\"contexto\":{\"ponto\":990007,\"linha\":\"8000-10\"}}"))
                .andExpect(status().isOk()).andExpect(jsonPath("$.origem").value("TEMPO_REAL"))
                .andExpect(jsonPath("$.acoes[0].rota").value(org.hamcrest.Matchers.startsWith("/embarque?ponto=990007&linha=8000-10")));
    }
}

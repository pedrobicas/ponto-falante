package br.fiap.pontofalante.embarque;

import com.sun.net.httpserver.HttpServer;
import io.zonky.test.db.postgres.embedded.EmbeddedPostgres;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.servlet.MockMvc;

import java.io.IOException;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.atomic.AtomicReference;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

/**
 * Teste de CONTRATO da integração com o modelo de visão (contratos/openapi-visao-letreiro.yaml). Um servidor HTTP de
 * teste faz o papel do serviço que a equipe de Computer Vision vai entregar, devolvendo leituras fixas. Isto prova que
 * o backend envia a imagem no formato combinado e interpreta a resposta; não é um resultado do modelo real.
 */
@SpringBootTest(properties = {"PF_SPTRANS_MODO=demo", "pf.sptrans-token=", "pf.genai-url=", "pf.rpa-api-key=chave-local",
        "pf.visao-servico-chave=chave-visao-teste", "pf.visao-api-key=chave-camera-teste"})
@AutoConfigureMockMvc
class VisaoContratoPostgresTest {
    static final EmbeddedPostgres POSTGRES = iniciar();
    static final AtomicReference<String> RESPOSTA = new AtomicReference<>();
    static final AtomicReference<String> RECEBIDO = new AtomicReference<>();
    static final HttpServer MODELO = servidor();

    static EmbeddedPostgres iniciar() {
        try { return EmbeddedPostgres.start(); }
        catch (IOException e) { throw new IllegalStateException(e); }
    }

    static HttpServer servidor() {
        try {
            HttpServer s = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
            s.createContext("/health", troca -> {
                byte[] r = "{\"status\":\"ok\"}".getBytes(StandardCharsets.UTF_8);
                troca.getResponseHeaders().add("Content-Type", "application/json");
                troca.sendResponseHeaders(200, r.length);
                troca.getResponseBody().write(r);
                troca.close();
            });
            s.createContext("/v1/letreiro", troca -> {
                String tipo = String.valueOf(troca.getRequestHeaders().getFirst("Content-Type"));
                String chave = String.valueOf(troca.getRequestHeaders().getFirst("X-API-Key"));
                String corpo = new String(troca.getRequestBody().readAllBytes(), StandardCharsets.ISO_8859_1);
                RECEBIDO.set(tipo + "|" + chave + "|" + corpo.contains("name=\"imagem\""));
                byte[] r = RESPOSTA.get().getBytes(StandardCharsets.UTF_8);
                troca.getResponseHeaders().add("Content-Type", "application/json");
                troca.sendResponseHeaders(200, r.length);
                troca.getResponseBody().write(r);
                troca.close();
            });
            s.start();
            return s;
        } catch (IOException e) {
            throw new IllegalStateException(e);
        }
    }

    @AfterAll
    static void parar() {
        MODELO.stop(0);
    }

    @DynamicPropertySource
    static void props(DynamicPropertyRegistry r) {
        r.add("spring.datasource.url", () -> POSTGRES.getJdbcUrl("postgres", "postgres"));
        r.add("spring.datasource.username", () -> "postgres");
        r.add("spring.datasource.password", () -> "");
        r.add("pf.visao-url", () -> "http://127.0.0.1:" + MODELO.getAddress().getPort() + "/");
    }

    @Autowired MockMvc mvc;
    @Autowired JdbcTemplate jdbc;

    static final MockMultipartFile JPEG = new MockMultipartFile("imagem", "q.jpg", "image/jpeg",
            new byte[]{(byte) 0xFF, (byte) 0xD8, (byte) 0xFF, (byte) 0xE0, 1, 2, 3, 4, 5});

    @Test
    void enviaAImagemNoFormatoCombinadoEComparaComALinhaEsperada() throws Exception {
        RESPOSTA.set("{\"modelo\":\"letreiro-teste@0\",\"latencia_ms\":42,\"leituras\":[{\"texto\":\"875A-10\",\"confianca\":0.91}]}");
        mvc.perform(get("/api/status")).andExpect(jsonPath("$.visao").value("CONECTADA"));
        mvc.perform(multipart("/api/embarque/visao/conferir").file(JPEG).param("linha_esperada", "875A-10")
                        .header("X-PF-Dispositivo", "c".repeat(32)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.resultado").value("CONFERE"))
                .andExpect(jsonPath("$.linha_lida").value("875A-10"))
                .andExpect(jsonPath("$.modelo").value("letreiro-teste@0"))
                .andExpect(jsonPath("$.frase_falada").value(org.hamcrest.Matchers.containsString("motorista")));
        assertThat(RECEBIDO.get()).startsWith("multipart/form-data").contains("|chave-visao-teste|true");
        // Grava o resultado, nunca a imagem.
        assertThat(jdbc.queryForObject("select resultado from embarque_conferencia_visao order by id desc limit 1", String.class))
                .isEqualTo("CONFERE");
    }

    @Test
    void outraLinhaNoLetreiroGeraAlerta() throws Exception {
        RESPOSTA.set("{\"modelo\":\"letreiro-teste@0\",\"leituras\":[{\"texto\":\"6450-10\",\"confianca\":0.88}]}");
        mvc.perform(multipart("/api/embarque/visao/conferir").file(JPEG).param("linha_esperada", "875A-10")
                        .header("X-PF-Dispositivo", "c".repeat(32)))
                .andExpect(status().isOk()).andExpect(jsonPath("$.resultado").value("NAO_CONFERE"));
    }

    @Test
    void cameraFixaPodeAvisarOnibusSemLinhaLida() throws Exception {
        String corpo = "{\"ponto\":70016916,\"linha_reconhecida\":null,\"confianca\":0.7,"
                + "\"capturado_em\":\"2026-11-17T12:00:00Z\",\"dispositivo\":\"camera-ponto\"}";
        mvc.perform(post("/api/integracoes/visao/deteccoes").header("X-API-Key", "chave-camera-teste")
                        .contentType("application/json").content(corpo))
                .andExpect(status().isAccepted())
                .andExpect(jsonPath("$.frase_falada").value(org.hamcrest.Matchers.containsString("Não consegui ler a linha")));
        mvc.perform(get("/api/integracoes/visao/deteccoes").param("ponto", "70016916"))
                .andExpect(jsonPath("$[0].linha_reconhecida").doesNotExist());
    }

    @Test
    void registroDoTunelExigeAChaveDoServicoEEnderecoPermitido() throws Exception {
        mvc.perform(put("/api/visao/endereco").contentType("application/json").content("{\"url\":\"https://a-b.trycloudflare.com\"}"))
                .andExpect(status().isUnauthorized());
        mvc.perform(put("/api/visao/endereco").header("X-API-Key", "chave-visao-teste").contentType("application/json")
                .content("{\"url\":\"https://evil.com\"}")).andExpect(status().isBadRequest());
    }

    @Test
    void semLeituraOrientaAApontarParaOLetreiro() throws Exception {
        RESPOSTA.set("{\"modelo\":\"pf-visao 1.0.0\",\"leituras\":[],\"deteccoes\":{\"onibus\":1,\"letreiros\":0}}");
        mvc.perform(get("/api/embarque/visao")).andExpect(jsonPath("$.conectada").value(true));
        mvc.perform(multipart("/api/embarque/visao/conferir").file(JPEG).param("linha_esperada", "875A-10")
                        .header("X-PF-Dispositivo", "c".repeat(32)))
                .andExpect(status().isOk()).andExpect(jsonPath("$.resultado").value("INCONCLUSIVO"))
                .andExpect(jsonPath("$.frase_falada").value(org.hamcrest.Matchers.containsString("mais para cima")));
    }

    @Test
    void recusaArquivoQueNaoEImagemERespostaForaDoContrato() throws Exception {
        var texto = new MockMultipartFile("imagem", "x.jpg", "image/jpeg", "nao sou imagem".getBytes(StandardCharsets.UTF_8));
        mvc.perform(multipart("/api/embarque/visao/conferir").file(texto).param("linha_esperada", "875A-10")
                .header("X-PF-Dispositivo", "c".repeat(32))).andExpect(status().isUnsupportedMediaType());
        RESPOSTA.set("{\"resultado\":\"CONFERE\"}");
        mvc.perform(multipart("/api/embarque/visao/conferir").file(JPEG).param("linha_esperada", "875A-10")
                .header("X-PF-Dispositivo", "c".repeat(32))).andExpect(status().isBadGateway())
                .andExpect(jsonPath("$.codigo").value("VISAO_RESPOSTA_INVALIDA"));
    }
}

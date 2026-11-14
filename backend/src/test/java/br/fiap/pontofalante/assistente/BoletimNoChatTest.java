package br.fiap.pontofalante.assistente;

import br.fiap.pontofalante.rpa.BoletimService;
import br.fiap.pontofalante.sistema.ErroApi;
import br.fiap.pontofalante.sistema.PfProps;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.boot.context.properties.bind.Bindable;
import org.springframework.boot.context.properties.bind.Binder;
import org.springframework.boot.context.properties.source.MapConfigurationPropertySource;

import java.time.Clock;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

/** "Tem algum problema no transporte hoje?" sai do boletim do robô, com data e natureza do dado, sem LLM. */
class BoletimNoChatTest {
    static ChatService chat(ObjectNode boletim) {
        PfProps props = new Binder(new MapConfigurationPropertySource(Map.of("pf.salt", "salt-teste")))
                .bind("pf", Bindable.of(PfProps.class)).get();
        ChatService chat = new ChatService(props, new AssistenteTempoReal(null));
        chat.setBoletim(new BoletimService(null, new ObjectMapper(), Clock.systemUTC()) {
            @Override public ObjectNode ultimo() {
                if (boletim == null) {
                    throw ErroApi.naoEncontrado("Ainda não há boletim publicado.");
                }
                return boletim;
            }
        });
        return chat;
    }

    static ObjectNode boletim(String natureza) {
        return new ObjectMapper().createObjectNode().put("data_referencia", "2026-11-13").put("desatualizado", false)
                .put("natureza_dados", natureza).put("resumo_falado", "Duas linhas com espera longa prevista.");
    }

    @ParameterizedTest
    @ValueSource(strings = {"Existe algum problema ou ocorrência no transporte hoje?", "Como estão as linhas hoje?",
            "tem linha com atraso?", "o que diz o boletim?"})
    void perguntaDeOcorrenciaUsaOBoletimEDizQueEEstimativa(String pergunta) {
        var r = chat(boletim("ESTIMADO")).respostaDoBoletim(pergunta).orElseThrow();
        assertThat(r.origem()).isEqualTo("BOLETIM");
        assertThat(r.resposta()).contains("2026-11-13").contains("estimativa").contains("não atrasos medidos")
                .contains("Duas linhas com espera longa prevista.").contains("não registra acidentes");
        assertThat(r.acoes()).singleElement().satisfies(a -> assertThat(a.rota()).isEqualTo("/boletim"));
    }

    @Test void boletimSimuladoOuIndisponivelEDitoComoTal() {
        assertThat(chat(boletim("SIMULADO")).respostaDoBoletim("o que diz o boletim?").orElseThrow().resposta())
                .contains("dados simulados");
        var indisponivel = chat(boletim("INDISPONIVEL")).respostaDoBoletim("o que diz o boletim?").orElseThrow();
        assertThat(indisponivel.resposta()).contains("sem dados suficientes");
        assertThat(indisponivel.confianca()).isEqualTo("baixa");
        assertThat(chat(null).respostaDoBoletim("o que diz o boletim?").orElseThrow().resposta())
                .contains("Ainda não há boletim");
    }

    @Test void legadoSemClassificacaoNaoAfirmaPrevisoesReais() {
        var b = boletim("ESTIMADO"); b.remove("natureza_dados");
        var r = chat(b).respostaDoBoletim("boletim de hoje").orElseThrow();
        assertThat(r.resposta()).contains("classificação não informada").doesNotContain("previsões reais");
        assertThat(r.confianca()).isEqualTo("baixa");
    }

    @Test void boletimInterrompePendenciaDePontoEPreservaClassificacao() {
        var r = chat(boletim("SIMULADO")).perguntar("O que diz o boletim?", null,
                new Chat.Contexto(null, "5317-10", 2, "PONTO_PREVISAO", null));
        assertThat(r.origem()).isEqualTo("BOLETIM");
        assertThat(r.naturezaDados()).isEqualTo("SIMULADO");
        assertThat(r.contexto().linha()).isNull();
    }

    @Test void boletimDeOutroDiaNaoConfirmaSituacaoDeHoje() {
        var b = boletim("ESTIMADO");
        b.put("data_referencia", java.time.LocalDate.now(java.time.ZoneId.of("America/Sao_Paulo")).minusDays(1).toString());
        assertThat(chat(b).respostaDoBoletim("boletim de hoje").orElseThrow().resposta())
                .contains("não confirma a situação de hoje");
    }

    @ParameterizedTest
    @ValueSource(strings = {"Estou com problema no meu Bilhete Único", "Tenho 66 anos, posso andar gratuitamente?",
            "Quanto falta para a 5317-10?", "problema na recarga do cartão no ônibus"})
    void perguntasDeRegraOuPrevisaoNaoViramBoletim(String pergunta) {
        assertThat(chat(boletim("ESTIMADO")).respostaDoBoletim(pergunta)).isEmpty();
    }
}

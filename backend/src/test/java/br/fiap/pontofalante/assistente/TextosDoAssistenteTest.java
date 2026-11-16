package br.fiap.pontofalante.assistente;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

/** Regressões de concordância nas frases que o assistente lê em voz alta. */
class TextosDoAssistenteTest {

    @Test void maisPrevistosConcordaComAQuantidade() {
        assertThat(AssistenteTempoReal.maisPrevistos(1)).isEqualTo("Há mais 1 ônibus previsto na tela do ponto. ");
        assertThat(AssistenteTempoReal.maisPrevistos(3)).isEqualTo("Há mais 3 ônibus previstos na tela do ponto. ");
    }

    @Test void foraDaAreaUsaOArtigoDoLugar() {
        String rio = ForaDaArea.responder("Qual o telefone do metrô do Rio de Janeiro?").orElseThrow().resposta();
        assertThat(rio).contains("sobre o Rio de Janeiro").contains("transporte público do Rio de Janeiro")
                .doesNotContain("de Rio de Janeiro");
        String curitiba = ForaDaArea.responder("Posso levar meu cachorro no ônibus em Curitiba?").orElseThrow().resposta();
        assertThat(curitiba).contains("sobre Curitiba").contains("transporte público de Curitiba");
        String baixada = ForaDaArea.responder("Tem ônibus na Baixada Santista de madrugada?").orElseThrow().resposta();
        assertThat(baixada).contains("sobre a Baixada Santista").contains("transporte público da Baixada Santista");
    }
}

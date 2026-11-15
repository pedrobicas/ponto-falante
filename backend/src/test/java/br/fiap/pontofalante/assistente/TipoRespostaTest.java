package br.fiap.pontofalante.assistente;

import br.fiap.pontofalante.assistente.Chat.FonteCitada;
import br.fiap.pontofalante.assistente.Chat.RespostaChat;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.JsonNode;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Regressão da auditoria de 15/11: uma recusa não pode aparecer como "confiança alta", e uma pergunta sobre outra
 * cidade não pode ser encaminhada ao 156 ou à SPTrans de São Paulo.
 */
class TipoRespostaTest {

    @Test
    void recusaDaGenaiComConfiancaAltaEhRecusaNaoFundamentada() throws Exception {
        JsonNode genai = new ObjectMapper().readTree("""
                {"resposta":"Não encontrei essa informação nas fontes oficiais.","fontes":[],
                 "confianca":"alta","nao_consta":true}""");
        RespostaChat r = ChatService.converter(genai, 10);
        assertThat(r.tipoResposta()).isEqualTo("RECUSA");
    }

    @Test
    void respostaComFontesEConfiancaAltaEhFundamentada() {
        var r = new RespostaChat("Sim.", List.of(new FonteCitada("Lei 10.741", "lei-1")), "alta", false, true, 5, "BASE_OFICIAL");
        assertThat(r.tipoResposta()).isEqualTo("FUNDAMENTADA");
    }

    @Test
    void respostaSemFontesOuComConfiancaBaixaEhInsuficiente() {
        assertThat(new RespostaChat("Talvez.", List.of(), "alta", false, true, 5, "BASE_OFICIAL").tipoResposta())
                .isEqualTo("INSUFICIENTE");
        assertThat(new RespostaChat("Talvez.", List.of(new FonteCitada("X", "x-1")), "baixa", false, true, 5, "BASE_OFICIAL")
                .tipoResposta()).isEqualTo("INSUFICIENTE");
    }

    @Test
    void consultasDeterministicasEIndisponibilidade() {
        assertThat(new RespostaChat("Em 5 min.", List.of(), "alta", false, true, 5, "TEMPO_REAL").tipoResposta()).isEqualTo("CONSULTA");
        assertThat(new RespostaChat("Boletim.", List.of(), "media", false, true, 5, "BOLETIM").tipoResposta()).isEqualTo("CONSULTA");
        assertThat(ChatService.indisponivel().tipoResposta()).isEqualTo("INDISPONIVEL");
    }

    @Test
    void tipoRespostaVaiNoJson() throws Exception {
        var json = new ObjectMapper().setPropertyNamingStrategy(PropertyNamingStrategies.SNAKE_CASE)
                .readTree(new ObjectMapper().setPropertyNamingStrategy(PropertyNamingStrategies.SNAKE_CASE)
                        .writeValueAsString(ChatService.indisponivel()));
        assertThat(json.path("tipo_resposta").asText()).isEqualTo("INDISPONIVEL");
    }

    @Test
    void curitibaRecebeLimitacaoDeAreaSemContatosDeSaoPaulo() {
        RespostaChat r = BoletimNoChatTest.chat(null).perguntar("Posso levar meu cachorro no ônibus em Curitiba?");
        assertThat(r.origem()).isEqualTo("FORA_DA_AREA");
        assertThat(r.tipoResposta()).isEqualTo("FORA_DA_AREA");
        assertThat(r.resposta()).contains("São Paulo", "Curitiba", "órgão ou a empresa responsável")
                .doesNotContain("156").doesNotContain("SPTrans");
        assertThat(r.fontes()).isEmpty();
        assertThat(r.confianca()).isEqualTo("baixa");
    }

    @ParameterizedTest
    @ValueSource(strings = {"Quanto custa a passagem no Rio de Janeiro?", "Idoso paga ônibus em Belo Horizonte?",
            "Tem ônibus noturno em Porto Alegre?", "como funciona o bilhete em Campinas",
            "Quanto custa o ônibus para o Rio de Janeiro?", "Idoso paga ônibus em Guarulhos?",
            "Como é o ônibus na cidade de Santos?", "Tem gratuidade em Belém do Pará?", "Passagem em Rio Branco, Acre",
            "Posso usar meu bilhete de São Paulo em Curitiba?"})
    void outrasCidadesSaoReconhecidas(String pergunta) {
        assertThat(ForaDaArea.cidade(pergunta)).isPresent();
    }

    @ParameterizedTest
    @ValueSource(strings = {"Ônibus na Rio Branco para o Centro", "Ponto na Av. Santos Dumont", "Linha que passa no Belém",
            "Quanto falta para a 875A-10?", "Ponto na Rua Curitiba", "Ônibus na São Luís", "Tenho 66 anos, posso andar de graça?",
            "Ônibus em São Paulo para Pinheiros", "Quais ônibus passam na Campinas, em São Paulo?",
            "Sou de Curitiba; quais linhas passam no ponto 70016916?", "Ônibus em Santos", "Ponto em Vitória"})
    void enderecosDeSaoPauloNaoViramForaDaArea(String pergunta) {
        assertThat(ForaDaArea.cidade(pergunta)).isEmpty();
    }
}

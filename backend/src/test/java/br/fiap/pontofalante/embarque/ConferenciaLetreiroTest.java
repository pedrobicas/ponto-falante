package br.fiap.pontofalante.embarque;

import br.fiap.pontofalante.embarque.EmbarqueDtos.LeituraLetreiro;
import br.fiap.pontofalante.embarque.EmbarqueDtos.ResultadoConferencia;
import br.fiap.pontofalante.sistema.ErroApi;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/** Regras da conferência do letreiro (independem do modelo de visão que vier a ser conectado). */
class ConferenciaLetreiroTest {
    private static List<LeituraLetreiro> leu(String texto, double conf) {
        return List.of(new LeituraLetreiro(texto, conf, null));
    }

    @Test
    void letreiroCompletoIgualConfere() {
        var r = ConferenciaLetreiro.comparar("875A-10", leu("875A-10 METRÔ BUTANTÃ", 0.93));
        assertThat(r.resultado()).isEqualTo(ResultadoConferencia.CONFERE);
        assertThat(r.linhaLida()).isEqualTo("875A-10");
        assertThat(r.frase()).contains("Confirme com o motorista");
    }

    @Test
    void soONumeroNoLetreiroNaoBastaParaConfirmar() {
        var r = ConferenciaLetreiro.comparar("875A-10", leu("875A", 0.95));
        assertThat(r.resultado()).isEqualTo(ResultadoConferencia.NUMERO_CONFERE);
        assertThat(r.frase()).contains("Confira o destino");
    }

    @Test
    void outraLinhaOuOutraVariacaoNaoConfere() {
        assertThat(ConferenciaLetreiro.comparar("875A-10", leu("6450-10", 0.9)).resultado())
                .isEqualTo(ResultadoConferencia.NAO_CONFERE);
        var variacao = ConferenciaLetreiro.comparar("875A-10", leu("875A-21", 0.9));
        assertThat(variacao.resultado()).isEqualTo(ResultadoConferencia.NAO_CONFERE);
        assertThat(variacao.frase()).contains("variação diferente");
    }

    @Test
    void confiancaBaixaOuSemLeituraEInconclusivo() {
        assertThat(ConferenciaLetreiro.comparar("875A-10", leu("875A-10", 0.4)).resultado())
                .isEqualTo(ResultadoConferencia.INCONCLUSIVO);
        assertThat(ConferenciaLetreiro.comparar("875A-10", List.of()).resultado())
                .isEqualTo(ResultadoConferencia.INCONCLUSIVO);
        assertThat(ConferenciaLetreiro.comparar("875A-10", leu("LOTAÇÃO", 0.99)).resultado())
                .isEqualTo(ResultadoConferencia.INCONCLUSIVO);
    }

    @Test
    void usaALeituraMaisConfiavelENormalizaCaixaETraco() {
        var r = ConferenciaLetreiro.comparar("n137-11", List.of(new LeituraLetreiro("6450-10", 0.61, null),
                new LeituraLetreiro("N137 – 11", 0.88, List.of(1, 2, 3, 4))));
        assertThat(r.resultado()).isEqualTo(ResultadoConferencia.CONFERE);
        assertThat(r.linhaLida()).isEqualTo("N137-11");
    }

    @Test
    void respostaForaDoContratoDoModeloViraErroNuncaResultado() throws Exception {
        var mapper = new ObjectMapper();
        assertThatThrownBy(() -> ReconhecedorLetreiro.converter(mapper.readTree("{\"leituras\":[]}")))
                .isInstanceOf(ErroApi.class);
        var ok = ReconhecedorLetreiro.converter(mapper.readTree(
                "{\"modelo\":\"m@1\",\"latencia_ms\":80,\"leituras\":[{\"texto\":\"875A-10\",\"confianca\":0.9,\"caixa\":[1,2,3,4]},"
                        + "{\"texto\":\"x\",\"confianca\":7},{\"texto\":\"\",\"confianca\":0.5}]}"));
        assertThat(ok.leituras()).hasSize(1);
        assertThat(ok.leituras().get(0).caixa()).containsExactly(1, 2, 3, 4);
        assertThat(ok.latenciaMs()).isEqualTo(80);
    }
}

package br.fiap.pontofalante.transporte;

import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;

import static org.assertj.core.api.Assertions.assertThat;

class FraseFaladaTest {
    @ParameterizedTest
    @CsvSource(delimiter = '|', value = {
            "JD. JOÃO XXIII|Jd. João XXIII",
            "TERM. PQ. D. PEDRO II|Term. Pq. D. Pedro II",
            "PÇA. RAMOS DE AZEVEDO|Pça. Ramos de Azevedo",
            "METRÔ BELÉM|Metrô Belém",
            "PAULISTA B/C|Paulista B/C",
            "VILA DI GIORGIO|Vila di Giorgio",
            "Já em caixa normal|Já em caixa normal"})
    void nomesDaSptransFicamLegiveisParaAVoz(String entrada, String esperado) {
        assertThat(FraseFalada.legivel(entrada)).isEqualTo(esperado);
    }
}

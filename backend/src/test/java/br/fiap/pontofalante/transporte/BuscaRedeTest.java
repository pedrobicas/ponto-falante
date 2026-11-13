package br.fiap.pontofalante.transporte;

import br.fiap.pontofalante.sistema.ErroApi;
import br.fiap.pontofalante.sistema.PfProps;
import br.fiap.pontofalante.transporte.Modelos.DadosPrevisao;
import br.fiap.pontofalante.transporte.Modelos.Fonte;
import br.fiap.pontofalante.transporte.Modelos.Ponto;
import br.fiap.pontofalante.transporte.Modelos.RespostaPontos;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.boot.context.properties.bind.Bindable;
import org.springframework.boot.context.properties.bind.Binder;
import org.springframework.boot.context.properties.source.MapConfigurationPropertySource;
import org.springframework.http.HttpStatus;

import java.time.Clock;
import java.time.ZoneId;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * Regressão da busca com o cadastro oficial (GTFS de 12/11/2026 empacotado no JAR). Casos reais relatados em 13/11:
 * "Rua Augusta, 1000" não achava nada e o código 160015580 trazia cerca de 360 pontos sem relação.
 */
class BuscaRedeTest {
    static final long Paulista_1711 = 160015580L;
    static RedeGtfs rede;
    static TransporteService servico;

    @BeforeAll static void iniciar() {
        PfProps props = new Binder(new MapConfigurationPropertySource(
                Map.of("pf.salt", "salt-teste", "pf.sptrans-token", "token-de-teste")))
                .bind("pf", Bindable.of(PfProps.class)).get();
        Clock relogio = Clock.system(ZoneId.of("America/Sao_Paulo"));
        HashVeiculo hash = new HashVeiculo(props);
        // Olho Vivo de teste: nenhum código existe além do cadastro, e nenhuma chamada de rede é feita.
        OlhoVivoProvider semRede = new OlhoVivoProvider(props, hash, new ObjectMapper()) {
            @Override public DadosPrevisao previsoes(long codigoPonto) {
                throw new ErroApi(HttpStatus.NOT_FOUND, "PONTO_NAO_ENCONTRADO", "Ponto não encontrado.");
            }

            @Override public List<Ponto> buscarPontos(String termo) {
                throw new AssertionError("a busca de paradas da Olho Vivo não deve ser usada no modo real");
            }

            @Override public List<Modelos.Linha> buscarLinhas(String termo) {
                return List.of();
            }
        };
        rede = new RedeGtfs();
        servico = new TransporteService(props, semRede, new DemoProvider(relogio, hash), relogio, rede);
    }

    @ParameterizedTest
    @ValueSource(strings = {"Rua Augusta, 1000", "Rua da Consolação, 1000", "Paulista, 1000",
            "Rua Augusta, 1000", "nossa senhora do sabra, 1711", "Avenida Paulista, 1000"})
    void enderecoComAbreviacaoAcentoOuErroAchaOPontoCerto(String termo) {
        RespostaPontos r = servico.buscarPontos(termo, null);
        assertThat(r.pontos()).isNotEmpty();
        assertThat(r.pontos().get(0).codigo()).as(termo).isEqualTo(Paulista_1711);
        assertThat(r.pontos().get(0).fonte()).isEqualTo(Fonte.GTFS_SPTRANS);
        assertThat(r.pontos().get(0).linhas()).isNotEmpty();
        assertThat(r.aviso()).isNull();
    }

    @Test void codigoDevolveSoOPontoDoCodigo() {
        RespostaPontos r = servico.buscarPontos("160015580", null);
        assertThat(r.pontos()).singleElement().satisfies(p -> {
            assertThat(p.codigo()).isEqualTo(Paulista_1711);
            assertThat(p.nome()).contains("Paulista, 1000");
        });
    }

    @Test void codigoInexistenteNaoTrazListaSemRelacao() {
        RespostaPontos r = servico.buscarPontos("999999999", null);
        assertThat(r.pontos()).isEmpty();
        assertThat(r.aviso()).contains("Não existe ponto com o código 999999999");
        assertThat(servico.buscarPontos("1711", null).pontos()).isEmpty();
    }

    @Test void codigoIncompletoSugereOsQueComecamIgual() {
        RespostaPontos r = servico.buscarPontos("1600155", null);
        assertThat(r.pontos()).isNotEmpty().allSatisfy(p -> assertThat(String.valueOf(p.codigo())).startsWith("1600155"));
        assertThat(r.aviso()).contains("começam com os mesmos números");
    }

    @Test void numeroSemPontoExatoOrdenaPelaNumeracaoMaisProximaEAvisa() {
        RespostaPontos r = servico.buscarPontos("Rua Augusta, 1000", null);
        assertThat(r.pontos().get(0).codigo()).isEqualTo(Paulista_1711);
        assertThat(r.aviso()).contains("numeração mais próxima");
        assertThat(r.pontos()).hasSizeLessThanOrEqualTo(TransporteService.LIMITE_RESULTADOS);
    }

    @Test void buscaSemCorrespondenciaExplicaEOfereceAlternativa() {
        RespostaPontos r = servico.buscarPontos("xyzqw kkkj", null);
        assertThat(r.pontos()).isEmpty();
        assertThat(r.aviso()).contains("código da placa").contains("localização");
    }

    @Test void pontosProximosVemOrdenadosPorDistancia() {
        RespostaPontos r = servico.pontosProximos(-23.669878, -46.688667, 400, null);
        assertThat(r.pontos().get(0).codigo()).isEqualTo(Paulista_1711);
        assertThat(r.pontos().get(0).distanciaMetros()).isZero();
        assertThat(r.pontos()).extracting(Ponto::distanciaMetros).isSorted();
        assertThat(servico.pontosProximos(-22.9, -43.2, 400, null).aviso()).contains("fora da área");
    }

    @Test void linhaPorNumeroTemDoisSentidosComParadasEmOrdem() {
        var it = servico.itinerario("5317-10", null);
        assertThat(it.sentidos()).hasSize(2);
        assertThat(it.sentidos().get(0).paradas()).hasSizeGreaterThan(10);
        assertThat(it.sentidos()).extracting(Modelos.SentidoLinha::destino).doesNotHaveDuplicates();
        assertThatThrownBy(() -> servico.itinerario("0000-00", null)).isInstanceOf(ErroApi.class);
    }

    @Test void linhaPorNomeOuDestinoVemDoCadastro() {
        var r = servico.buscarLinhas("sesc orion", null);
        assertThat(r.linhas()).isNotEmpty();
        assertThat(r.linhas()).anySatisfy(l -> assertThat(l.letreiro()).isEqualTo("5317-10"));
    }

    @Test void linhasDoPontoListamLetreiroESentido() {
        var r = servico.linhasDoPonto(Paulista_1711, null);
        assertThat(r.linhas()).isNotEmpty().allSatisfy(l -> assertThat(l.destino()).isNotBlank());
        assertThat(servico.linhasDoPonto(1L, null).aviso()).contains("não aparece");
    }

    @Test void modoDemonstracaoContinuaComARedeFicticia() {
        RespostaPontos r = servico.buscarPontos("paulista", "demo");
        assertThat(r.fonte()).isEqualTo(Fonte.SIMULADO);
        assertThat(r.pontos()).isNotEmpty().allSatisfy(p -> assertThat(p.fonte()).isEqualTo(Fonte.SIMULADO));
    }

    @Test void normalizacaoExpandeAbreviacoes() {
        assertThat(RedeGtfs.tokens("Rua da Consolação, 1000"))
                .containsExactly("avenida", "nossa", "senhora", "Paulista", "1711");
        assertThat(RedeGtfs.distancia("sabra", "Paulista", 1)).isEqualTo(1);
    }
}

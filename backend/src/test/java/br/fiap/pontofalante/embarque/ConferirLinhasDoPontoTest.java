package br.fiap.pontofalante.embarque;

import br.fiap.pontofalante.embarque.EmbarqueDtos.LeituraLetreiro;
import br.fiap.pontofalante.embarque.EmbarqueDtos.LinhaEscolhida;
import br.fiap.pontofalante.embarque.EmbarqueDtos.ResultadoConferencia;
import br.fiap.pontofalante.embarque.EmbarqueRepositorios.ConferenciaVisaoRepository;
import br.fiap.pontofalante.embarque.EmbarqueRepositorios.FavoritoEmbarqueRepository;
import br.fiap.pontofalante.embarque.EmbarqueRepositorios.SessaoEmbarqueRepository;
import br.fiap.pontofalante.embarque.Entidades.SessaoEmbarque;
import br.fiap.pontofalante.transporte.RedeGtfs;
import br.fiap.pontofalante.transporte.RedeGtfs.Viagem;
import br.fiap.pontofalante.transporte.TransporteService;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;

import java.time.Clock;
import java.time.OffsetDateTime;
import java.util.Collection;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/** Que linhas o backend manda para o modelo validar a leitura do letreiro. */
class ConferirLinhasDoPontoTest {
    final SessaoEmbarqueRepository sessoes = mock(SessaoEmbarqueRepository.class);
    final TransporteService transporte = mock(TransporteService.class);
    final ReconhecedorLetreiro visao = mock(ReconhecedorLetreiro.class);
    final EmbarqueService service = new EmbarqueService(mock(FavoritoEmbarqueRepository.class), sessoes,
            mock(ConferenciaVisaoRepository.class), transporte, visao, Clock.systemUTC());
    final UUID id = UUID.randomUUID();

    @SuppressWarnings("unchecked")
    Collection<String> linhasEnviadas() {
        ArgumentCaptor<Collection<String>> c = ArgumentCaptor.forClass(Collection.class);
        verify(visao).ler(any(), eq("image/jpeg"), c.capture());
        return c.getValue();
    }

    void sessaoCom(String... linhas) {
        var escolhas = java.util.Arrays.stream(linhas).map(l -> new LinhaEscolhida(l, null, null)).toList();
        when(sessoes.findByIdAndDispositivo(id, "disp")).thenReturn(Optional.of(
                new SessaoEmbarque(id, "disp", 70016916L, "Av. Paulista, 1374", escolhas, false, OffsetDateTime.now())));
    }

    void modeloLe(String texto, double conf) {
        when(visao.ler(any(), any(), any())).thenReturn(new ReconhecedorLetreiro.Leitura("m", List.of(
                new LeituraLetreiro(texto, conf, null)), 10, 1, 1, true));
    }

    @Test
    void enviaAsLinhasAcompanhadasEDepoisAsDoPonto() {
        sessaoCom("875A-10", "875C-10");
        RedeGtfs rede = mock(RedeGtfs.class);
        when(transporte.rede()).thenReturn(rede);
        when(rede.disponivel()).thenReturn(true);
        when(rede.viagensDaParada(70016916L)).thenReturn(List.of(new Viagem("6450-10", 1, "X", "X", new long[0]),
                new Viagem("875A-10", 1, "Y", "Y", new long[0]), new Viagem("875c-10", 2, "Z", "Z", new long[0])));
        modeloLe("875C-10", 0.7);
        var r = service.conferir("disp", new byte[]{1}, "image/jpeg", "875A-10", id);
        assertThat(linhasEnviadas()).containsExactly("875A-10", "875C-10", "6450-10");
        assertThat(r.resultado()).isEqualTo(ResultadoConferencia.CONFERE);   // 875C-10 também serve para a pessoa
    }

    @Test
    void semCadastroDoPontoNaoEnviaListaParcial() {
        sessaoCom("875A-10");
        RedeGtfs rede = mock(RedeGtfs.class);
        when(transporte.rede()).thenReturn(rede);
        when(rede.disponivel()).thenReturn(false);
        modeloLe("875A-10", 0.5);
        service.conferir("disp", new byte[]{1}, "image/jpeg", "875A-10", id);
        assertThat(linhasEnviadas()).isEmpty();
    }

    @Test
    void semAcompanhamentoNaoConsultaOPonto() {
        modeloLe("875A-10", 0.5);
        service.conferir("disp", new byte[]{1}, "image/jpeg", "875A-10", null);
        assertThat(linhasEnviadas()).isEmpty();
    }
}

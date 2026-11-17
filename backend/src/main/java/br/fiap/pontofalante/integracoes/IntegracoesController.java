package br.fiap.pontofalante.integracoes;

import br.fiap.pontofalante.integracoes.Dtos.DeteccaoVisaoDto;
import br.fiap.pontofalante.integracoes.Dtos.EventoDispositivoDto;
import br.fiap.pontofalante.integracoes.Dtos.RespostaDeteccao;
import br.fiap.pontofalante.integracoes.Dtos.RespostaEvento;
import br.fiap.pontofalante.integracoes.Dtos.TipoEvento;
import br.fiap.pontofalante.integracoes.Repositorios.DeteccaoVisaoRepository;
import br.fiap.pontofalante.integracoes.Repositorios.EventoDispositivoRepository;
import br.fiap.pontofalante.rpa.HistoricoService;
import br.fiap.pontofalante.rpa.Passagem;
import br.fiap.pontofalante.sistema.ConfigWeb;
import br.fiap.pontofalante.sistema.ErroApi;
import br.fiap.pontofalante.transporte.Modelos.PrevisoesPonto;
import br.fiap.pontofalante.transporte.TransporteService;
import jakarta.validation.Valid;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

import java.nio.charset.StandardCharsets;
import java.time.Clock;
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.List;

/** Contratos para as outras disciplinas: visão computacional, dispositivo ESP32 e exportação para Big Data. */
@RestController
@RequestMapping("/api/integracoes")
public class IntegracoesController {
    static final int MAX_DIAS_EXPORTACAO = 31;
    static final String CABECALHO_CSV = "data,ponto,linha,sentido,veiculo,programado_em,previsto_em,acessivel,fonte,tipo_registro";

    private final DeteccaoVisaoRepository deteccoes;
    private final EventoDispositivoRepository eventos;
    private final TransporteService transporte;
    private final HistoricoService historico;
    private final Clock relogio;

    public IntegracoesController(DeteccaoVisaoRepository deteccoes, EventoDispositivoRepository eventos,
                                 TransporteService transporte, HistoricoService historico, Clock relogio) {
        this.deteccoes = deteccoes;
        this.eventos = eventos;
        this.transporte = transporte;
        this.historico = historico;
        this.relogio = relogio;
    }

    // ---------- visão computacional ----------

    @PostMapping("/visao/deteccoes")
    @ResponseStatus(HttpStatus.ACCEPTED)
    public RespostaDeteccao registrarDeteccao(@Valid @RequestBody DeteccaoVisaoDto d) {
        String linha = d.linhaReconhecida() == null || d.linhaReconhecida().isBlank() ? null : d.linhaReconhecida().strip();
        DeteccaoVisao salvo = deteccoes.save(new DeteccaoVisao(d.ponto(), linha, d.confianca(),
                d.capturadoEm(), d.dispositivo().strip(), OffsetDateTime.now(relogio)));
        return new RespostaDeteccao(salvo.id, linha == null
                ? "Ônibus chegando. Não consegui ler a linha; confirme com o motorista."
                : "Ônibus " + linha + ", chegando.");
    }

    @GetMapping("/visao/deteccoes")
    public List<DeteccaoVisaoDto> listarDeteccoes(@RequestParam long ponto) {
        return deteccoes.findTop50ByPontoOrderByCapturadoEmDesc(ponto).stream()
                .map(x -> new DeteccaoVisaoDto(x.ponto, x.linhaReconhecida, x.confianca, x.capturadoEm, x.dispositivo))
                .toList();
    }

    // ---------- dispositivo (ESP32) ----------

    @PostMapping("/dispositivos/eventos")
    @ResponseStatus(HttpStatus.ACCEPTED)
    public RespostaEvento registrarEvento(@Valid @RequestBody EventoDispositivoDto e) {
        eventos.save(new EventoDispositivo(e.dispositivoId().strip(), e.ponto(), e.tipo().name(), e.ocorridoEm(),
                e.bateriaPct(), OffsetDateTime.now(relogio)));
        if (e.tipo() != TipoEvento.BOTAO_PRESSIONADO) {
            return new RespostaEvento(null, null);
        }
        try {
            PrevisoesPonto p = transporte.previsoes(e.ponto(), "auto");
            return new RespostaEvento(p.fraseFalada(), p.fonte());
        } catch (ErroApi falha) {
            return new RespostaEvento("Não consegui consultar os ônibus deste ponto agora. Tente de novo em instantes.", null);
        }
    }

    // ---------- Big Data ----------

    @GetMapping("/dados/passagens")
    public ResponseEntity<byte[]> exportarPassagens(
            @RequestParam @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate de,
            @RequestParam @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate ate) {
        if (ate.isBefore(de)) {
            throw ErroApi.requisicaoInvalida("A data final não pode ser antes da inicial.");
        }
        if (ChronoUnit.DAYS.between(de, ate) + 1 > MAX_DIAS_EXPORTACAO) {
            throw ErroApi.requisicaoInvalida("O período pode ter no máximo " + MAX_DIAS_EXPORTACAO + " dias.");
        }
        StringBuilder csv = new StringBuilder(CABECALHO_CSV).append("\r\n");
        for (LocalDate dia = de; !dia.isAfter(ate); dia = dia.plusDays(1)) {
            for (Passagem p : historico.passagensDoDia(dia)) {
                List<String> campos = new ArrayList<>(List.of(dia.toString(), nulo(p.ponto), nulo(p.linha),
                        nulo(p.sentido), nulo(p.veiculo), nulo(p.programadoEm), nulo(p.previstoEm),
                        p.acessivel == null ? "" : p.acessivel.toString(), nulo(p.fonte), nulo(p.tipoRegistro)));
                csv.append(String.join(",", campos.stream().map(IntegracoesController::escapar).toList())).append("\r\n");
            }
        }
        return ResponseEntity.ok()
                .contentType(new MediaType("text", "csv", StandardCharsets.UTF_8))
                .header(HttpHeaders.CONTENT_DISPOSITION, "attachment; filename=\"passagens_" + de + "_" + ate + ".csv\"")
                .body(csv.toString().getBytes(StandardCharsets.UTF_8));
    }

    private static String nulo(String s) {
        return s == null ? "" : s;
    }

    static String escapar(String s) {
        if (s.contains(",") || s.contains("\"") || s.contains("\n") || s.contains("\r")) {
            return "\"" + s.replace("\"", "\"\"") + "\"";
        }
        return s;
    }
}

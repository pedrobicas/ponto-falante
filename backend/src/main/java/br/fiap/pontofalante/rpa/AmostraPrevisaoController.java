package br.fiap.pontofalante.rpa;

import com.fasterxml.jackson.databind.JsonNode;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.time.LocalDate;
import java.util.List;
import java.util.Map;

/**
 * Amostras reais de previsão do coletor do robô RPA. O POST exige X-API-Key igual a RPA_API_KEY, conferida antes da
 * leitura do corpo (ChaveRpaAmostrasInterceptor). O GET é público, como /api/historico: dado público da SPTrans com o
 * veículo anonimizado.
 */
@RestController
@RequestMapping("/api/rpa")
public class AmostraPrevisaoController {
    private final AmostraPrevisaoService service;

    public AmostraPrevisaoController(AmostraPrevisaoService service) {
        this.service = service;
    }

    @PostMapping("/amostras")
    public AmostraPrevisaoService.ResultadoEnvio receber(@RequestBody JsonNode corpo) {
        return service.receber(corpo);
    }

    @GetMapping("/amostras")
    public List<Map<String, Object>> doDia(@RequestParam @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate data) {
        return service.doDia(data);
    }
}

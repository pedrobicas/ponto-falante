package br.fiap.pontofalante.rpa;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

import java.time.LocalDate;
import java.util.List;
import java.util.Map;

/** A chave X-API-Key do POST é conferida antes, em ChavesApiInterceptor. */
@RestController
@RequestMapping("/api")
public class BoletimController {
    private final BoletimService service;

    public BoletimController(BoletimService service) {
        this.service = service;
    }

    @PostMapping("/boletim")
    @ResponseStatus(HttpStatus.CREATED)
    public Map<String, Object> publicar(@RequestBody JsonNode corpo) {
        Boletim b = service.publicar(corpo);
        return Map.of("recebido", true, "data_referencia", b.dataReferencia.toString());
    }

    @GetMapping("/boletim")
    public ObjectNode ultimo() {
        return service.ultimo();
    }

    @GetMapping("/boletim/{data}")
    public ObjectNode porData(@PathVariable @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate data) {
        return service.porData(data);
    }

    @GetMapping("/boletins")
    public List<BoletimService.Resumo> lista() {
        return service.resumos();
    }
}

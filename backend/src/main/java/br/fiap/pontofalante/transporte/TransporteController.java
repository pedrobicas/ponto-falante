package br.fiap.pontofalante.transporte;

import br.fiap.pontofalante.sistema.ErroApi;
import br.fiap.pontofalante.transporte.Modelos.PrevisoesPonto;
import br.fiap.pontofalante.transporte.Modelos.RespostaLinhas;
import br.fiap.pontofalante.transporte.Modelos.RespostaPontos;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api")
public class TransporteController {
    private final TransporteService service;

    public TransporteController(TransporteService service) {
        this.service = service;
    }

    @GetMapping("/pontos")
    public RespostaPontos pontos(@RequestParam(required = false) String busca,
                                 @RequestParam(required = false) String modo) {
        String termo = busca == null ? "" : busca.trim();
        if (termo.length() < 2 || termo.length() > 80) {
            throw ErroApi.requisicaoInvalida("Digite de 2 a 80 letras para buscar um ponto.");
        }
        ProvedorTransporte p = service.escolher(modo);
        return new RespostaPontos(p.fonte(), p.buscarPontos(termo));
    }

    @GetMapping("/pontos/{codigo}/previsoes")
    public PrevisoesPonto previsoes(@PathVariable long codigo, @RequestParam(required = false) String modo) {
        return service.previsoes(codigo, modo);
    }

    @GetMapping("/linhas")
    public RespostaLinhas linhas(@RequestParam(required = false) String busca,
                                 @RequestParam(required = false) String modo) {
        String termo = busca == null ? "" : busca.trim();
        if (termo.isEmpty() || termo.length() > 80) {
            throw ErroApi.requisicaoInvalida("Digite de 1 a 80 letras para buscar uma linha.");
        }
        ProvedorTransporte p = service.escolher(modo);
        return new RespostaLinhas(p.fonte(), p.buscarLinhas(termo));
    }
}

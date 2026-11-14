package br.fiap.pontofalante.transporte;

import br.fiap.pontofalante.sistema.ErroApi;
import br.fiap.pontofalante.transporte.Modelos.PrevisoesPonto;
import br.fiap.pontofalante.transporte.Modelos.RespostaItinerario;
import br.fiap.pontofalante.transporte.Modelos.RespostaLinhas;
import br.fiap.pontofalante.transporte.Modelos.RespostaLinhasDoPonto;
import br.fiap.pontofalante.transporte.Modelos.RespostaPontos;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
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
        return service.buscarPontos(termo, modo);
    }

    public record PedidoProximos(Double lat, Double lon, Integer raio, String modo) {
    }

    /**
     * Pontos perto de uma coordenada. POST com corpo JSON para a localização não ficar em URL, histórico ou log de
     * acesso; nada é gravado.
     */
    @PostMapping("/pontos/proximos")
    public RespostaPontos proximos(@RequestBody PedidoProximos pedido) {
        if (pedido == null || pedido.lat() == null || pedido.lon() == null || pedido.lat().isNaN() || pedido.lon().isNaN()
                || Math.abs(pedido.lat()) > 90 || Math.abs(pedido.lon()) > 180) {
            throw ErroApi.requisicaoInvalida("Localização inválida.");
        }
        int raio = pedido.raio() == null ? 400 : Math.max(100, Math.min(pedido.raio(), 1500));
        return service.pontosProximos(pedido.lat(), pedido.lon(), raio, pedido.modo());
    }

    @GetMapping("/pontos/{codigo}/previsoes")
    public PrevisoesPonto previsoes(@PathVariable long codigo, @RequestParam(required = false) String modo) {
        return service.previsoes(codigo, modo);
    }

    @GetMapping("/pontos/{codigo}/linhas")
    public RespostaLinhasDoPonto linhasDoPonto(@PathVariable long codigo, @RequestParam(required = false) String modo) {
        return service.linhasDoPonto(codigo, modo);
    }

    @GetMapping("/linhas")
    public RespostaLinhas linhas(@RequestParam(required = false) String busca,
                                 @RequestParam(required = false) String modo) {
        String termo = busca == null ? "" : busca.trim();
        if (termo.isEmpty() || termo.length() > 80) {
            throw ErroApi.requisicaoInvalida("Digite de 1 a 80 letras para buscar uma linha.");
        }
        return service.buscarLinhas(termo, modo);
    }

    /** Paradas da linha, em ordem, nos dois sentidos (cadastro GTFS). */
    @GetMapping("/linhas/{letreiro}/paradas")
    public RespostaItinerario itinerario(@PathVariable String letreiro, @RequestParam(required = false) String modo) {
        if (!letreiro.matches("[0-9A-Za-z\\-]{2,12}")) {
            throw ErroApi.requisicaoInvalida("Informe a linha como aparece no letreiro, por exemplo 875A-10.");
        }
        return service.itinerario(letreiro, modo);
    }
}

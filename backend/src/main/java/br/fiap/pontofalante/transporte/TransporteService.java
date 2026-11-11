package br.fiap.pontofalante.transporte;

import br.fiap.pontofalante.sistema.ErroApi;
import br.fiap.pontofalante.sistema.PfProps;
import br.fiap.pontofalante.transporte.Modelos.DadosPrevisao;
import br.fiap.pontofalante.transporte.Modelos.Fonte;
import br.fiap.pontofalante.transporte.Modelos.PrevisoesPonto;
import org.springframework.stereotype.Service;

import java.time.Clock;
import java.time.OffsetDateTime;

/** Escolhe a origem dos dados (real ou demonstração) e monta as respostas públicas. */
@Service
public class TransporteService {
    private final PfProps props;
    private final OlhoVivoProvider olhoVivo;
    private final DemoProvider demo;
    private final Clock relogio;

    public TransporteService(PfProps props, OlhoVivoProvider olhoVivo, DemoProvider demo, Clock relogio) {
        this.props = props;
        this.olhoVivo = olhoVivo;
        this.demo = demo;
        this.relogio = relogio;
    }

    /** modo=demo força a demonstração; sem token configurado, auto também é demonstração. */
    public ProvedorTransporte escolher(String modo) {
        if (modo != null && !modo.isBlank() && !modo.equalsIgnoreCase("auto") && !modo.equalsIgnoreCase("demo")) {
            throw ErroApi.requisicaoInvalida("O modo deve ser auto ou demo.");
        }
        boolean forcaDemo = "demo".equalsIgnoreCase(modo);
        return forcaDemo || !props.temTokenSptrans() ? demo : olhoVivo;
    }

    public PrevisoesPonto previsoes(long codigo, String modo) {
        ProvedorTransporte provedor = escolher(modo);
        DadosPrevisao d = provedor.previsoes(codigo);
        boolean simulado = provedor.fonte() == Fonte.SIMULADO;
        String frase = FraseFalada.montar(d.ponto().nome(), d.onibus(), simulado);
        return new PrevisoesPonto(d.ponto(), provedor.fonte(), "PREVISAO", d.horarioReferencia(),
                OffsetDateTime.now(relogio), d.onibus(), frase);
    }
}

package br.fiap.pontofalante.assistente;

import br.fiap.pontofalante.sistema.PfProps;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

import java.time.Duration;

/** Consulta {GENAI_URL}/health com timeout de 2 s e guarda o resultado por 30 s. Nunca bloqueia por muito tempo. */
@Component
public class SaudeGenai {
    private static final long VALIDADE_NANOS = Duration.ofSeconds(30).toNanos();

    private final PfProps props;
    private final RestClient rest;
    private volatile boolean ultimoResultado;
    private volatile long verificadoEmNanos;
    private volatile boolean jaVerificou;

    public SaudeGenai(PfProps props) {
        this.props = props;
        this.rest = ClienteGenai.criar(props, 2000, 2000);
    }

    public boolean disponivel() {
        if (!props.temGenai()) {
            return false;
        }
        long agora = System.nanoTime();
        if (jaVerificou && agora - verificadoEmNanos < VALIDADE_NANOS) {
            return ultimoResultado;
        }
        boolean ok;
        try {
            rest.get().uri("/health").retrieve().toBodilessEntity();
            ok = true;
        } catch (Exception e) {
            ok = false;
        }
        ultimoResultado = ok;
        verificadoEmNanos = System.nanoTime();
        jaVerificou = true;
        return ok;
    }
}

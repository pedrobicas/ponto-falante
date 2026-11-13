package br.fiap.pontofalante.assistente;

import br.fiap.pontofalante.sistema.PfProps;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

import java.time.Duration;

/** Consulta {GENAI_URL}/health com timeout de 2 s e guarda o resultado por 30 s. Nunca bloqueia por muito tempo. */
@Component
public class SaudeGenai {
    private static final long VALIDADE_NANOS = Duration.ofSeconds(30).toNanos();

    private final EnderecoGenai endereco;
    private final RestClient rest;
    private volatile boolean ultimoResultado;
    private volatile long verificadoEmNanos;
    private volatile boolean jaVerificou;

    public SaudeGenai(PfProps props, EnderecoGenai endereco) {
        this.endereco = endereco;
        this.rest = ClienteGenai.criar(props, 2000, 2000);
    }

    public boolean disponivel() {
        var base = endereco.base();
        if (base.isEmpty()) {
            return false;
        }
        long agora = System.nanoTime();
        if (jaVerificou && agora - verificadoEmNanos < VALIDADE_NANOS) {
            return ultimoResultado;
        }
        boolean ok;
        try {
            rest.get().uri(base.get() + "/health").retrieve().toBodilessEntity();
            ok = true;
        } catch (Exception e) {
            ok = false;
        }
        ultimoResultado = ok;
        verificadoEmNanos = System.nanoTime();
        jaVerificou = true;
        return ok;
    }

    /** Endereço trocado: a próxima consulta de status volta a medir em vez de usar o cache. */
    public void esquecer() {
        jaVerificou = false;
    }
}

package br.fiap.pontofalante.sistema;

import br.fiap.pontofalante.assistente.SaudeGenai;
import br.fiap.pontofalante.rpa.BoletimService;
import br.fiap.pontofalante.transporte.OlhoVivoProvider;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.boot.info.BuildProperties;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.time.Clock;
import java.time.LocalDate;
import java.time.OffsetDateTime;

@RestController
@RequestMapping("/api")
public class StatusController {
    private static final Logger log = LoggerFactory.getLogger(StatusController.class);

    public record Status(String versao, String sptrans, String assistente, LocalDate ultimoBoletim,
                         OffsetDateTime horarioServidor) {
    }

    private final PfProps props;
    private final OlhoVivoProvider olhoVivo;
    private final SaudeGenai saudeGenai;
    private final BoletimService boletins;
    private final Clock relogio;
    private final String versao;

    public StatusController(PfProps props, OlhoVivoProvider olhoVivo, SaudeGenai saudeGenai, BoletimService boletins,
                            Clock relogio, ObjectProvider<BuildProperties> build) {
        this.props = props;
        this.olhoVivo = olhoVivo;
        this.saudeGenai = saudeGenai;
        this.boletins = boletins;
        this.relogio = relogio;
        BuildProperties b = build.getIfAvailable();
        this.versao = b == null ? "dev" : b.getVersion();
    }

    @GetMapping("/status")
    public Status status() {
        String sptrans = !props.temTokenSptrans() ? "DEMO" : olhoVivo.disponivel() ? "REAL" : "INDISPONIVEL";
        LocalDate ultimo = null;
        try {
            ultimo = boletins.dataDoUltimo();
        } catch (RuntimeException e) {
            log.warn("Status: banco indisponível ao consultar o último boletim");
        }
        return new Status(versao, sptrans, saudeGenai.disponivel() ? "DISPONIVEL" : "INDISPONIVEL", ultimo,
                OffsetDateTime.now(relogio));
    }
}

package br.fiap.pontofalante;

import br.fiap.pontofalante.sistema.PfProps;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.EnableConfigurationProperties;

@SpringBootApplication
@EnableConfigurationProperties(PfProps.class)
public class PontoFalanteApplication {
    public static void main(String[] args) {
        SpringApplication.run(PontoFalanteApplication.class, args);
    }
}

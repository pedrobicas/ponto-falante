package br.fiap.pontofalante.sistema;

import org.springframework.context.annotation.Configuration;
import org.springframework.data.jpa.repository.config.EnableJpaRepositories;

/** Inclui os repositorios de visao e dispositivos declarados dentro de Repositorios. */
@Configuration(proxyBeanMethods = false)
@EnableJpaRepositories(basePackages = "br.fiap.pontofalante", considerNestedRepositories = true)
public class ConfigRepositorios {
}

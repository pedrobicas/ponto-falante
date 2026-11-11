package br.fiap.pontofalante.sistema;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.env.EnvironmentPostProcessor;
import org.springframework.core.env.ConfigurableEnvironment;
import org.springframework.core.env.MapPropertySource;

import java.net.URI;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Aceita o DATABASE_URL no formato do Render (postgres://usuario:senha@host:porta/banco) e o converte para
 * as propriedades JDBC. SPRING_DATASOURCE_URL, se existir, tem prioridade e nada é alterado.
 */
public class ConversorDatabaseUrl implements EnvironmentPostProcessor {

    @Override
    public void postProcessEnvironment(ConfigurableEnvironment env, SpringApplication app) {
        String explicita = env.getProperty("SPRING_DATASOURCE_URL");
        if (explicita != null && !explicita.isBlank()) {
            return;
        }
        Map<String, Object> props = converter(env.getProperty("DATABASE_URL"));
        if (!props.isEmpty()) {
            env.getPropertySources().addFirst(new MapPropertySource("databaseUrlConvertida", props));
        }
    }

    /** Devolve as propriedades spring.datasource.* equivalentes, ou mapa vazio se não houver o que converter. */
    public static Map<String, Object> converter(String url) {
        Map<String, Object> saida = new LinkedHashMap<>();
        if (url == null || url.isBlank()) {
            return saida;
        }
        url = url.trim();
        if (url.startsWith("jdbc:")) {
            saida.put("spring.datasource.url", url);
            return saida;
        }
        if (!url.startsWith("postgres://") && !url.startsWith("postgresql://")) {
            return saida;
        }
        URI uri = URI.create(url);
        int porta = uri.getPort() > 0 ? uri.getPort() : 5432;
        String banco = uri.getPath() == null ? "" : uri.getPath();
        String consulta = uri.getRawQuery() == null ? "" : "?" + uri.getRawQuery();
        saida.put("spring.datasource.url", "jdbc:postgresql://" + uri.getHost() + ":" + porta + banco + consulta);
        String info = uri.getUserInfo();
        if (info != null) {
            int i = info.indexOf(':');
            saida.put("spring.datasource.username", i < 0 ? info : info.substring(0, i));
            if (i >= 0) {
                saida.put("spring.datasource.password", info.substring(i + 1));
            }
        }
        return saida;
    }
}

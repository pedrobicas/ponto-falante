package br.fiap.pontofalante.sistema;

import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Bean;
import org.springframework.beans.factory.config.BeanFactoryPostProcessor;
import org.springframework.core.env.ConfigurableEnvironment;
import org.springframework.core.env.MapPropertySource;

import java.net.URI;
import java.util.Locale;
import java.util.Map;

/** Configuracao de integracao SPTrans, isolada das fontes em andamento do backend. */
@Configuration(proxyBeanMethods = false)
public class ConfigSptrans {
    static final String HTTPS = "https://api.olhovivo.sptrans.com.br/v2.1";
    static final String GATEWAY = "https://gateway.apilib.prefeitura.sp.gov.br/sptrans/olhovivo/v2.1";
    static final String GATEWAY_TOKEN = "https://gateway.apilib.prefeitura.sp.gov.br/token";

    /** Executa antes da vinculacao de PfProps, sem editar o cliente original da equipe. */
    @Bean
    static BeanFactoryPostProcessor configurarSptrans(ConfigurableEnvironment env) {
        return beanFactory -> {
            String modo = env.getProperty("PF_SPTRANS_MODO", "auto").strip().toLowerCase(Locale.ROOT);
            if (!modo.equals("auto") && !modo.equals("demo")) {
                throw new IllegalArgumentException("PF_SPTRANS_MODO deve ser auto ou demo.");
            }
            String token = modo.equals("demo") ? "" : env.getProperty("pf.sptrans-token",
                    env.getProperty("SPTRANS_TOKEN", "")).strip();
            if (token.codePoints().anyMatch(c -> Character.isWhitespace(c) || Character.isSpaceChar(c)
                    || Character.isISOControl(c) || c == 0xfeff)) {
                throw new IllegalArgumentException("SPTRANS_TOKEN contem espacos internos ou caracteres de controle.");
            }
            String chaveGw = modo.equals("demo") ? "" : env.getProperty("pf.sptrans-gateway-chave", "").strip();
            String segredoGw = modo.equals("demo") ? "" : env.getProperty("pf.sptrans-gateway-segredo", "").strip();
            for (String c : new String[] {chaveGw, segredoGw}) {
                if (c.codePoints().anyMatch(x -> Character.isWhitespace(x) || Character.isISOControl(x) || x == 0xfeff)) {
                    throw new IllegalArgumentException("Credencial do gateway SPTrans contem espacos ou caracteres de controle.");
                }
            }
            String urlGw = validarUrl(env.getProperty("pf.sptrans-gateway-url", GATEWAY).strip(), "SPTRANS_GATEWAY_URL");
            String tokenGw = validarUrl(env.getProperty("pf.sptrans-gateway-token-url", GATEWAY_TOKEN).strip(),
                    "SPTRANS_GATEWAY_TOKEN_URL");
            String base = env.getProperty("pf.sptrans-base-url", env.getProperty("SPTRANS_BASE_URL", HTTPS)).strip();
            while (base.endsWith("/")) base = base.substring(0, base.length() - 1);
            // Corrige o default legado em memoria, antes de qualquer requisicao HTTP.
            if (base.equals("http://api.olhovivo.sptrans.com.br/v2.1")) base = HTTPS;
            URI uri;
            try {
                uri = URI.create(base);
            } catch (IllegalArgumentException e) {
                throw new IllegalArgumentException("SPTRANS_BASE_URL invalida.");
            }
            boolean local = "127.0.0.1".equals(uri.getHost()) || "localhost".equals(uri.getHost())
                    || "[::1]".equals(uri.getHost()) || "::1".equals(uri.getHost());
            if (uri.getHost() == null || uri.getUserInfo() != null || uri.getRawQuery() != null
                    || uri.getRawFragment() != null
                    || !("https".equals(uri.getScheme()) || (local && "http".equals(uri.getScheme())))) {
                throw new IllegalArgumentException("SPTRANS_BASE_URL deve usar HTTPS e nao conter credenciais ou parametros.");
            }
            env.getPropertySources().addFirst(new MapPropertySource("sptransConfigSegura", Map.of(
                    "pf.sptrans-token", token, "pf.sptrans-base-url", base,
                    "pf.sptrans-gateway-chave", chaveGw, "pf.sptrans-gateway-segredo", segredoGw,
                    "pf.sptrans-gateway-url", urlGw, "pf.sptrans-gateway-token-url", tokenGw)));
        };
    }

    /** HTTPS obrigatório (http só em loopback, para testes), sem credenciais, parâmetros ou fragmento. */
    static String validarUrl(String url, String nome) {
        while (url.endsWith("/")) url = url.substring(0, url.length() - 1);
        URI uri;
        try {
            uri = URI.create(url);
        } catch (IllegalArgumentException e) {
            throw new IllegalArgumentException(nome + " invalida.");
        }
        boolean local = "127.0.0.1".equals(uri.getHost()) || "localhost".equals(uri.getHost());
        if (uri.getHost() == null || uri.getUserInfo() != null || uri.getRawQuery() != null
                || uri.getRawFragment() != null
                || !("https".equals(uri.getScheme()) || (local && "http".equals(uri.getScheme())))) {
            throw new IllegalArgumentException(nome + " deve usar HTTPS e nao conter credenciais ou parametros.");
        }
        return url;
    }
}

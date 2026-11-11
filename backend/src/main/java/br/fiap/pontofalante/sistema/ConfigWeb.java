package br.fiap.pontofalante.sistema;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Profile;
import org.springframework.core.io.ClassPathResource;
import org.springframework.core.io.Resource;
import org.springframework.http.CacheControl;
import org.springframework.web.servlet.config.annotation.CorsRegistry;
import org.springframework.web.servlet.config.annotation.InterceptorRegistry;
import org.springframework.web.servlet.config.annotation.ResourceHandlerRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;
import org.springframework.web.servlet.resource.PathResourceResolver;

import java.io.IOException;
import java.time.Clock;
import java.time.ZoneId;

/** Arquivos estáticos do Angular (classpath:/static), fallback de SPA, chaves de API e relógio. */
@Configuration
public class ConfigWeb implements WebMvcConfigurer {
    public static final ZoneId SAO_PAULO = ZoneId.of("America/Sao_Paulo");

    @Autowired
    private ChavesApiInterceptor chaves;

    @Bean
    Clock relogio() {
        return Clock.system(SAO_PAULO);
    }

    @Override
    public void addInterceptors(InterceptorRegistry registry) {
        registry.addInterceptor(chaves).addPathPatterns("/api/**");
    }

    @Override
    public void addResourceHandlers(ResourceHandlerRegistry registry) {
        registry.addResourceHandler("/**")
                .addResourceLocations("classpath:/static/")
                .setUseLastModified(false)
                .setCacheControl(CacheControl.noStore())
                .resourceChain(false)
                .addResolver(new SpaResolver());
    }

    /** Devolve o arquivo pedido; para rotas do Angular (sem ponto, fora de /api e /actuator) devolve o index.html. */
    static class SpaResolver extends PathResourceResolver {
        @Override
        protected Resource getResource(String resourcePath, Resource location) throws IOException {
            if (!resourcePath.isEmpty() && !resourcePath.endsWith("/")) {
                Resource pedido = location.createRelative(resourcePath);
                if (pedido.exists() && pedido.isReadable()) {
                    return pedido;
                }
            }
            boolean reservado = resourcePath.equals("api") || resourcePath.startsWith("api/")
                    || resourcePath.equals("actuator") || resourcePath.startsWith("actuator/");
            String ultimoSegmento = resourcePath.substring(resourcePath.lastIndexOf('/') + 1);
            if (!reservado && !ultimoSegmento.contains(".")) {
                Resource index = new ClassPathResource("static/index.html");
                return index.exists() ? index : null;
            }
            return null;
        }
    }

    /** CORS só para o servidor de desenvolvimento do Angular (perfil dev). Em produção é mesma origem. */
    @Configuration
    @Profile("dev")
    static class CorsDev implements WebMvcConfigurer {
        private final PfProps props;

        CorsDev(PfProps props) {
            this.props = props;
        }

        @Override
        public void addCorsMappings(CorsRegistry registry) {
            registry.addMapping("/api/**")
                    .allowedOrigins(props.devOrigin())
                    .allowedMethods("GET", "POST", "OPTIONS")
                    .allowedHeaders("*");
        }
    }
}

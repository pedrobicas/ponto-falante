package br.fiap.pontofalante.rpa;

import br.fiap.pontofalante.sistema.Erro;
import br.fiap.pontofalante.sistema.PfProps;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.servlet.HandlerInterceptor;
import org.springframework.web.servlet.HandlerMapping;
import org.springframework.web.servlet.config.annotation.InterceptorRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;

/**
 * Chave do coletor de amostras (POST /api/rpa/amostras): mesma RPA_API_KEY do boletim e mesma política do
 * ChavesApiInterceptor. Roda antes de ler o corpo, usa o padrão resolvido pelo Spring (vale para URL codificada e
 * parâmetros de matriz) e compara em tempo constante. Chave não configurada = 503; ausente ou errada = 401.
 */
@Component
public class ChaveRpaAmostrasInterceptor implements HandlerInterceptor {
    static final String ROTA = "/api/rpa/amostras";
    private final PfProps props;
    private final ObjectMapper mapper;

    public ChaveRpaAmostrasInterceptor(PfProps props, ObjectMapper mapper) {
        this.props = props;
        this.mapper = mapper;
    }

    @Override
    public boolean preHandle(HttpServletRequest req, HttpServletResponse res, Object handler) throws Exception {
        String caminho = String.valueOf(req.getAttribute(HandlerMapping.BEST_MATCHING_PATTERN_ATTRIBUTE));
        if (!"POST".equals(req.getMethod()) || !ROTA.equals(caminho)) {
            return true;
        }
        String esperada = props.rpaApiKey();
        if (esperada == null || esperada.isBlank()) {
            return negar(res, HttpStatus.SERVICE_UNAVAILABLE, "CHAVE_NAO_CONFIGURADA",
                    "Este recurso está desativado no servidor.");
        }
        String recebida = req.getHeader("X-API-Key");
        if (recebida == null || !MessageDigest.isEqual(esperada.getBytes(StandardCharsets.UTF_8),
                recebida.getBytes(StandardCharsets.UTF_8))) {
            return negar(res, HttpStatus.UNAUTHORIZED, "CHAVE_INVALIDA", "Chave de acesso ausente ou inválida.");
        }
        return true;
    }

    private boolean negar(HttpServletResponse res, HttpStatus status, String codigo, String mensagem) throws Exception {
        res.setStatus(status.value());
        res.setContentType(MediaType.APPLICATION_JSON_VALUE);
        res.setCharacterEncoding("UTF-8");
        res.getWriter().write(mapper.writeValueAsString(new Erro(mensagem, codigo)));
        return false;
    }

    @Configuration
    static class Registro implements WebMvcConfigurer {
        private final ChaveRpaAmostrasInterceptor chave;

        Registro(ChaveRpaAmostrasInterceptor chave) {
            this.chave = chave;
        }

        @Override
        public void addInterceptors(InterceptorRegistry registry) {
            registry.addInterceptor(chave).addPathPatterns("/api/**");
        }
    }
}

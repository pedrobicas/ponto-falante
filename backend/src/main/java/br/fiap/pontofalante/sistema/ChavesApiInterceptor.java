package br.fiap.pontofalante.sistema;

import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.servlet.HandlerInterceptor;
import org.springframework.web.servlet.HandlerMapping;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;

/**
 * Autenticação por chave de API das rotas de integração. Roda antes de ler o corpo.
 * Chave não configurada no servidor = 503 (fail-closed); chave ausente/errada = 401.
 */
@Component
public class ChavesApiInterceptor implements HandlerInterceptor {
    private final PfProps props;
    private final ObjectMapper mapper;

    public ChavesApiInterceptor(PfProps props, ObjectMapper mapper) {
        this.props = props;
        this.mapper = mapper;
    }

    @Override
    public boolean preHandle(HttpServletRequest req, HttpServletResponse res, Object handler) throws Exception {
        String metodo = req.getMethod();
        // Usa o mapping resolvido pelo Spring, incluindo URLs codificadas e parametros de matriz.
        String caminho = String.valueOf(req.getAttribute(HandlerMapping.BEST_MATCHING_PATTERN_ATTRIBUTE));
        String cabecalho;
        String esperada;
        if ("POST".equals(metodo) && caminho.equals("/api/boletim")) {
            cabecalho = "X-API-Key";
            esperada = props.rpaApiKey();
        } else if ("POST".equals(metodo) && caminho.equals("/api/integracoes/visao/deteccoes")) {
            cabecalho = "X-API-Key";
            esperada = props.visaoApiKey();
        } else if ("POST".equals(metodo) && caminho.equals("/api/integracoes/dispositivos/eventos")) {
            cabecalho = "X-Device-Key";
            esperada = props.dispositivoApiKey();
        } else if ("PUT".equals(metodo) && caminho.equals("/api/genai/endereco")) {
            cabecalho = "X-API-Key";
            esperada = props.genaiApiKey();
        } else if ("GET".equals(metodo) && caminho.equals("/api/integracoes/dados/passagens")) {
            cabecalho = "X-API-Key";
            esperada = props.dadosApiKey();
        } else {
            return true;
        }
        if (esperada == null || esperada.isBlank()) {
            return negar(res, HttpStatus.SERVICE_UNAVAILABLE, "CHAVE_NAO_CONFIGURADA",
                    "Este recurso está desativado no servidor.");
        }
        String recebida = req.getHeader(cabecalho);
        if (recebida == null || !iguais(esperada, recebida)) {
            return negar(res, HttpStatus.UNAUTHORIZED, "CHAVE_INVALIDA", "Chave de acesso ausente ou inválida.");
        }
        return true;
    }

    static boolean iguais(String esperada, String recebida) {
        return MessageDigest.isEqual(esperada.getBytes(StandardCharsets.UTF_8), recebida.getBytes(StandardCharsets.UTF_8));
    }

    private boolean negar(HttpServletResponse res, HttpStatus status, String codigo, String mensagem) throws Exception {
        res.setStatus(status.value());
        res.setContentType(MediaType.APPLICATION_JSON_VALUE);
        res.setCharacterEncoding("UTF-8");
        res.getWriter().write(mapper.writeValueAsString(new Erro(mensagem, codigo)));
        return false;
    }
}

package br.fiap.pontofalante.sistema;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;

/** Cabeçalhos de segurança em todas as respostas (inclusive erros). O microfone é liberado só para a própria origem.
 *  img-src aceita blob: para a prévia local da foto do letreiro (URL.createObjectURL); a foto não sai do navegador por aí. */
@Component
@Order(Ordered.HIGHEST_PRECEDENCE)
public class CabecalhosSeguranca extends OncePerRequestFilter {
    static final String CSP = "default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; "
            + "script-src 'self'; connect-src 'self'; frame-ancestors 'none'";

    @Override
    protected void doFilterInternal(HttpServletRequest req, HttpServletResponse res, FilterChain chain)
            throws ServletException, IOException {
        res.setHeader("Content-Security-Policy", CSP);
        res.setHeader("X-Content-Type-Options", "nosniff");
        res.setHeader("Referrer-Policy", "no-referrer");
        res.setHeader("Permissions-Policy", "microphone=(self)");
        res.setHeader("X-Frame-Options", "DENY");
        chain.doFilter(req, res);
    }
}

package br.fiap.pontofalante.embarque;

import br.fiap.pontofalante.sistema.ErroApi;
import br.fiap.pontofalante.sistema.PfProps;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;

import java.net.URI;
import java.time.Instant;
import java.util.Locale;
import java.util.Optional;
import java.util.concurrent.atomic.AtomicReference;
import java.util.regex.Pattern;

/**
 * Endereço efetivo do serviço de visão (leitura do letreiro). Começa em PF_VISAO_URL e pode ser trocado pelo PC que
 * roda o modelo (PUT /api/visao/endereco), porque o modelo precisa de ~1,5 GB de memória e não cabe no plano gratuito
 * do Render: ele roda no computador da equipe, publicado por um Quick Tunnel da Cloudflare cuja URL muda a cada
 * reinício. Mesma regra da GenAI: só HTTPS em *.trycloudflare.com ou no host já configurado em PF_VISAO_URL, e o
 * registro fica só em memória (o script do PC o renova periodicamente).
 */
@Component
public class EnderecoVisao {
    private static final Pattern TUNEL_RAPIDO = Pattern.compile("^[a-z0-9]+(-[a-z0-9]+)*\\.trycloudflare\\.com$");

    private final String configurada;
    private final AtomicReference<String> registrado = new AtomicReference<>();
    private volatile Instant registradoEm;

    public EnderecoVisao(PfProps props) {
        String url = props.visaoUrl() == null ? "" : props.visaoUrl().strip();
        this.configurada = url.replaceAll("/+$", "");
    }

    /** URL base sem barra final, ou vazio se não houver serviço configurado nem registrado. */
    public Optional<String> base() {
        String r = registrado.get();
        if (r != null) return Optional.of(r);
        if (configurada.startsWith("http://") || configurada.startsWith("https://")) return Optional.of(configurada);
        return Optional.empty();
    }

    /** "registro" (túnel informado pelo PC), "configuracao" (PF_VISAO_URL) ou "nenhum". */
    public String origem() {
        return registrado.get() != null ? "registro" : base().isPresent() ? "configuracao" : "nenhum";
    }

    public Instant registradoEm() {
        return registradoEm;
    }

    void registrar(String urlValidada) {
        registrado.set(urlValidada);
        registradoEm = Instant.now();
    }

    /** Normaliza para "https://host[:porta]" ou recusa com 400. Caminho, usuário, query e fragmento são recusados. */
    String validar(String bruto) {
        URI u;
        try {
            u = URI.create(bruto == null ? "" : bruto.trim());
        } catch (IllegalArgumentException e) {
            throw invalida();
        }
        String host = u.getHost() == null ? "" : u.getHost().toLowerCase(Locale.ROOT);
        boolean semExtras = u.getRawUserInfo() == null && u.getRawQuery() == null && u.getRawFragment() == null
                && (u.getRawPath() == null || u.getRawPath().isEmpty() || u.getRawPath().equals("/"));
        if (!"https".equalsIgnoreCase(u.getScheme()) || host.isEmpty() || !semExtras || !hostPermitido(host)) {
            throw invalida();
        }
        return "https://" + host + (u.getPort() > 0 ? ":" + u.getPort() : "");
    }

    private boolean hostPermitido(String host) {
        if (TUNEL_RAPIDO.matcher(host).matches()) return true;
        try {
            URI c = URI.create(configurada);
            return "https".equalsIgnoreCase(c.getScheme()) && host.equalsIgnoreCase(c.getHost());
        } catch (IllegalArgumentException e) {
            return false;
        }
    }

    private static ErroApi invalida() {
        return new ErroApi(HttpStatus.BAD_REQUEST, "ENDERECO_INVALIDO",
                "Use https://<nome>.trycloudflare.com ou o host configurado em PF_VISAO_URL, sem caminho nem parâmetros.");
    }
}

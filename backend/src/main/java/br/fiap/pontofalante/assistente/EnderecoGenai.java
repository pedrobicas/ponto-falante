package br.fiap.pontofalante.assistente;

import br.fiap.pontofalante.sistema.ErroApi;
import br.fiap.pontofalante.sistema.PfProps;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;

import java.net.URI;
import java.time.Instant;
import java.util.Locale;
import java.util.Optional;
import java.util.concurrent.atomic.AtomicReference;
import java.util.regex.Pattern;

/**
 * Endereço efetivo do serviço GenAI. Começa em GENAI_URL e pode ser trocado pelo próprio PC que roda a GenAI
 * (PUT /api/genai/endereco, com a mesma GENAI_API_KEY), porque o Quick Tunnel gratuito da Cloudflare muda de URL a
 * cada reinício. Só aceita HTTPS em *.trycloudflare.com ou no host já configurado em GENAI_URL: o backend nunca
 * passa a chamar um endereço arbitrário. O registro fica só em memória; o script do PC o renova periodicamente.
 */
@Component
public class EnderecoGenai {
    private static final Pattern TUNEL_RAPIDO = Pattern.compile("^[a-z0-9]+(-[a-z0-9]+)*\\.trycloudflare\\.com$");

    private final PfProps props;
    private final AtomicReference<String> registrado = new AtomicReference<>();
    private volatile Instant registradoEm;

    @Autowired
    public EnderecoGenai(PfProps props) {
        this.props = props;
    }

    /** URL base sem barra final, ou vazio se não houver GenAI configurada nem registrada. */
    public Optional<String> base() {
        String r = registrado.get();
        if (r != null) {
            return Optional.of(r);
        }
        if (!props.temGenai()) {
            return Optional.empty();
        }
        String url = props.genaiUrl().trim();
        return Optional.of(url.endsWith("/") ? url.substring(0, url.length() - 1) : url);
    }

    public boolean configurado() {
        return base().isPresent();
    }

    /** "registro" (túnel informado pelo PC), "configuracao" (GENAI_URL) ou "nenhum". */
    public String origem() {
        return registrado.get() != null ? "registro" : props.temGenai() ? "configuracao" : "nenhum";
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
        if (TUNEL_RAPIDO.matcher(host).matches()) {
            return true;
        }
        if (!props.temGenai()) {
            return false;
        }
        try {
            URI configurado = URI.create(props.genaiUrl().trim());
            return "https".equalsIgnoreCase(configurado.getScheme()) && host.equalsIgnoreCase(configurado.getHost());
        } catch (IllegalArgumentException e) {
            return false;
        }
    }

    private static ErroApi invalida() {
        return new ErroApi(HttpStatus.BAD_REQUEST, "ENDERECO_INVALIDO",
                "Use https://<nome>.trycloudflare.com ou o host configurado em GENAI_URL, sem caminho nem parâmetros.");
    }
}

package br.fiap.pontofalante.transporte;

import br.fiap.pontofalante.sistema.ErroApi;
import br.fiap.pontofalante.sistema.PfProps;
import br.fiap.pontofalante.transporte.Modelos.DadosPrevisao;
import br.fiap.pontofalante.transporte.Modelos.Fonte;
import br.fiap.pontofalante.transporte.Modelos.Linha;
import br.fiap.pontofalante.transporte.Modelos.OnibusPrevisto;
import br.fiap.pontofalante.transporte.Modelos.Ponto;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.client.HttpClientErrorException;
import org.springframework.web.client.HttpServerErrorException;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;

import java.net.URI;
import java.net.http.HttpClient;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.ArrayList;
import java.util.Base64;
import java.util.Comparator;
import java.util.List;
import java.util.Locale;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.locks.ReentrantLock;

/**
 * Cliente da API Olho Vivo v2.1 (cache curto, prefixo do veículo anonimizado). Dois modos de acesso:
 * direto na SPTrans (POST /Login/Autenticar com a chave, sessão por cookie) ou pelo gateway oficial da
 * Prefeitura (apilib), com token OAuth2 client_credentials enviado como Bearer. Os caminhos e o JSON são os mesmos.
 */
@Component
public class OlhoVivoProvider implements ProvedorTransporte {
    private static final Logger log = LoggerFactory.getLogger(OlhoVivoProvider.class);
    static final Duration VALIDADE_SESSAO = Duration.ofMinutes(30);
    /** Depois de um login recusado ou com falha, novas tentativas esperam este intervalo (falha compartilhada). */
    static final Duration ESPERA_APOS_FALHA = Duration.ofSeconds(30);
    static final int TENTATIVAS_5XX = 3;
    static final String USER_AGENT = "PontoFalante/1.0 (+https://github.com/pedrobicas/ponto-falante)";

    private final PfProps props;
    private final HashVeiculo hasher;
    private final ObjectMapper mapper;
    private final RestClient rest;
    private final ReentrantLock lockAuth = new ReentrantLock();

    private final CacheTtl<List<Ponto>> cachePontos = new CacheTtl<>(Duration.ofMinutes(10), 500);
    private final CacheTtl<List<Linha>> cacheLinhas = new CacheTtl<>(Duration.ofMinutes(10), 500);
    private final CacheTtl<DadosPrevisao> cachePrevisoes = new CacheTtl<>(Duration.ofSeconds(20), 500);

    private final boolean viaGateway;
    /** Credencial atual: pares de cookie (modo direto) ou "Bearer ..." (gateway). */
    private volatile String cookie;
    private volatile long autenticadoEmNanos;
    private volatile long validadeNanos = VALIDADE_SESSAO.toNanos();
    private volatile boolean ultimaChamadaOk = true;
    private volatile long verificadoEmNanos;
    private volatile long falhaLoginEmNanos;

    public OlhoVivoProvider(PfProps props, HashVeiculo hasher, ObjectMapper mapper) {
        this.props = props;
        this.hasher = hasher;
        this.mapper = mapper;
        HttpClient http = HttpClient.newBuilder()
                .version(HttpClient.Version.HTTP_1_1)
                .connectTimeout(Duration.ofMillis(props.sptransConnectTimeoutMs()))
                .build();
        JdkClientHttpRequestFactory fabrica = new JdkClientHttpRequestFactory(http);
        fabrica.setReadTimeout(Duration.ofMillis(props.sptransReadTimeoutMs()));
        // User-Agent próprio: o Cloudflare da SPTrans barra clientes genéricos (erro 1010, browser_signature_banned).
        this.viaGateway = props.usaGatewaySptrans();
        this.rest = RestClient.builder().baseUrl(viaGateway ? props.sptransGatewayUrl() : props.sptransBaseUrl())
                .requestFactory(fabrica)
                .defaultHeader(HttpHeaders.USER_AGENT, USER_AGENT).build();
    }

    @Override
    public Fonte fonte() {
        return Fonte.OLHO_VIVO;
    }

    // ---------- autenticação ----------

    private boolean sessaoValida() {
        return cookie != null && System.nanoTime() - autenticadoEmNanos < validadeNanos;
    }

    /**
     * Uma única tentativa de login por vez, com espera limitada. Quem esperou reaproveita o resultado:
     * sessão renovada por outra thread ou falha recente (sem nova chamada à SPTrans durante ESPERA_APOS_FALHA).
     * @param cookieRecusado cookie que recebeu 401 (null quando a sessão apenas não existe ou expirou)
     */
    private void autenticar(String cookieRecusado) {
        if (falhaRecente()) {
            throw new TransporteIndisponivelException();
        }
        long esperaMs = props.sptransConnectTimeoutMs() + props.sptransReadTimeoutMs() + 1000L;
        boolean obtido;
        try {
            obtido = lockAuth.tryLock(esperaMs, TimeUnit.MILLISECONDS);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new TransporteIndisponivelException();
        }
        if (!obtido) {
            throw new TransporteIndisponivelException();
        }
        try {
            if (falhaRecente()) {
                throw new TransporteIndisponivelException();
            }
            if (sessaoValida() && (cookieRecusado == null || !cookieRecusado.equals(cookie))) {
                return; // outra thread já autenticou enquanto esta esperava
            }
            if (viaGateway) {
                autenticarGateway();
                return;
            }
            ResponseEntity<String> r = rest.post()
                    .uri(b -> b.path("/Login/Autenticar").queryParam("token", props.sptransToken()).build())
                    .retrieve().toEntity(String.class);
            if (!"true".equalsIgnoreCase(String.valueOf(r.getBody()).trim())) {
                cookie = null;
                log.warn("SPTrans recusou a chave no login (resposta false): confira o token no portal do desenvolvedor.");
                falhaLoginEmNanos = System.nanoTime();
                throw new TransporteIndisponivelException();
            }
            List<String> cookies = r.getHeaders().get(HttpHeaders.SET_COOKIE);
            if (cookies == null || cookies.isEmpty()) {
                cookie = null;
                falhaLoginEmNanos = System.nanoTime();
                throw new TransporteIndisponivelException();
            }
            List<String> pares = new ArrayList<>();
            for (String c : cookies) {
                pares.add(c.split(";", 2)[0].trim());
            }
            cookie = String.join("; ", pares);
            autenticadoEmNanos = System.nanoTime();
            falhaLoginEmNanos = 0;
        } catch (RestClientException e) {
            cookie = null;
            falhaLoginEmNanos = System.nanoTime();
            log.warn("Falha ao autenticar na SPTrans: {}", e.getClass().getSimpleName());
            throw new TransporteIndisponivelException();
        } finally {
            lockAuth.unlock();
        }
    }

    /** client_credentials no /token do gateway; o access_token vale até expires_in (com margem de 60 s). */
    private void autenticarGateway() {
        String basic = Base64.getEncoder().encodeToString(
                (props.sptransGatewayChave() + ":" + props.sptransGatewaySegredo()).getBytes(StandardCharsets.UTF_8));
        String corpo;
        try {
            corpo = rest.post().uri(URI.create(props.sptransGatewayTokenUrl()))
                    .header(HttpHeaders.AUTHORIZATION, "Basic " + basic)
                    .contentType(MediaType.APPLICATION_FORM_URLENCODED)
                    .body("grant_type=client_credentials")
                    .retrieve().body(String.class);
        } catch (HttpClientErrorException e) {
            cookie = null;
            falhaLoginEmNanos = System.nanoTime();
            log.warn("Gateway da Prefeitura recusou as credenciais OAuth (HTTP {}): confira Consumer Key/Secret no apilib.",
                    e.getStatusCode().value());
            throw new TransporteIndisponivelException();
        }
        JsonNode json;
        try {
            json = mapper.readTree(corpo == null ? "" : corpo);
        } catch (Exception e) {
            json = null;
        }
        String acesso = json == null ? "" : json.path("access_token").asText("");
        if (acesso.isBlank()) {
            cookie = null;
            falhaLoginEmNanos = System.nanoTime();
            log.warn("Gateway da Prefeitura respondeu sem access_token.");
            throw new TransporteIndisponivelException();
        }
        long expiraSeg = json.path("expires_in").asLong(3600);
        validadeNanos = Duration.ofSeconds(Math.max(30, expiraSeg - 60)).toNanos();
        cookie = "Bearer " + acesso;
        autenticadoEmNanos = System.nanoTime();
        falhaLoginEmNanos = 0;
    }

    private boolean falhaRecente() {
        long falha = falhaLoginEmNanos;
        return falha != 0 && System.nanoTime() - falha < ESPERA_APOS_FALHA.toNanos();
    }

    /** GET autenticado; reautentica uma vez se a sessão expirou (401). */
    private JsonNode obterJson(String caminho, String parametro, String valor) {
        try {
            if (!sessaoValida()) {
                autenticar(null);
            }
            JsonNode resultado;
            String cookieUsado = cookie;
            try {
                resultado = executarGet(caminho, parametro, valor);
            } catch (HttpClientErrorException.Unauthorized e) {
                autenticar(cookieUsado);
                resultado = executarGet(caminho, parametro, valor);
            }
            ultimaChamadaOk = true;
            return resultado;
        } catch (TransporteIndisponivelException e) {
            ultimaChamadaOk = false;
            throw e;
        } catch (RestClientException e) {
            ultimaChamadaOk = false;
            log.warn("Falha ao consultar a SPTrans ({}): {}", caminho, e.getClass().getSimpleName());
            throw new TransporteIndisponivelException();
        }
    }

    /**
     * GET idempotente com até duas novas tentativas em 5xx: o gateway da Prefeitura devolve 500 intermitente
     * ("Transport error: 411 Length Required" na chamada interna à SPTrans), medido em cerca de 20% das requisições.
     */
    private JsonNode executarGet(String caminho, String parametro, String valor) {
        for (int tentativa = 1; ; tentativa++) {
            try {
                return executarGetUmaVez(caminho, parametro, valor);
            } catch (HttpServerErrorException e) {
                if (tentativa >= TENTATIVAS_5XX) {
                    throw e;
                }
                try {
                    Thread.sleep(150L * tentativa);
                } catch (InterruptedException ie) {
                    Thread.currentThread().interrupt();
                    throw e;
                }
            }
        }
    }

    private JsonNode executarGetUmaVez(String caminho, String parametro, String valor) {
        String corpo = rest.get()
                .uri(b -> b.path(caminho).queryParam(parametro, valor).build())
                .header(viaGateway ? HttpHeaders.AUTHORIZATION : HttpHeaders.COOKIE, cookie)
                .retrieve().body(String.class);
        try {
            return mapper.readTree(corpo == null || corpo.isBlank() ? "null" : corpo);
        } catch (Exception e) {
            throw new RestClientException("JSON inválido da SPTrans");
        }
    }

    /** Para o /api/status: true se há token e a SPTrans respondeu/autenticou na última verificação (cache de 60 s). */
    public boolean disponivel() {
        long agora = System.nanoTime();
        if (verificadoEmNanos != 0 && agora - verificadoEmNanos < Duration.ofSeconds(60).toNanos()) {
            return ultimaChamadaOk && cookie != null;
        }
        verificadoEmNanos = agora;
        try {
            if (!sessaoValida()) {
                autenticar(null);
            }
            ultimaChamadaOk = true;
        } catch (ErroApi e) {
            ultimaChamadaOk = false;
        }
        return ultimaChamadaOk;
    }

    // ---------- consultas ----------

    @Override
    public List<Ponto> buscarPontos(String termo) {
        String chave = termo.trim().toLowerCase(Locale.ROOT);
        return cachePontos.obter(chave, () -> {
            JsonNode raiz = obterJson("/Parada/Buscar", "termosBusca", termo.trim());
            List<Ponto> pontos = new ArrayList<>();
            if (raiz.isArray()) {
                for (JsonNode n : raiz) {
                    pontos.add(new Ponto(n.path("cp").asLong(), n.path("np").asText(""),
                            textoOuNulo(n, "ed"), numeroOuNulo(n, "py"), numeroOuNulo(n, "px"), Fonte.OLHO_VIVO));
                }
            }
            return pontos;
        });
    }

    @Override
    public List<Linha> buscarLinhas(String termo) {
        String chave = termo.trim().toLowerCase(Locale.ROOT);
        return cacheLinhas.obter(chave, () -> {
            JsonNode raiz = obterJson("/Linha/Buscar", "termosBusca", termo.trim());
            List<Linha> linhas = new ArrayList<>();
            if (raiz.isArray()) {
                for (JsonNode n : raiz) {
                    int sentido = n.path("sl").asInt(1);
                    String tp = n.path("tp").asText("");
                    String ts = n.path("ts").asText("");
                    linhas.add(new Linha(n.path("cl").asLong(), n.path("lt").asText("") + "-" + n.path("tl").asText(""),
                            sentido, tp, ts, sentido == 1 ? ts : tp, n.path("lc").asBoolean(false)));
                }
            }
            return linhas;
        });
    }

    @Override
    public DadosPrevisao previsoes(long codigoPonto) {
        return cachePrevisoes.obter(String.valueOf(codigoPonto), () -> {
            JsonNode raiz = obterJson("/Previsao/Parada", "codigoParada", String.valueOf(codigoPonto));
            JsonNode p = raiz.path("p");
            if (p.isMissingNode() || p.isNull() || !p.isObject()) {
                throw ErroApi.naoEncontrado("Não encontramos esse ponto de ônibus.");
            }
            String hr = raiz.path("hr").asText("");
            Ponto ponto = new Ponto(p.path("cp").asLong(codigoPonto), p.path("np").asText(""), null,
                    numeroOuNulo(p, "py"), numeroOuNulo(p, "px"), Fonte.OLHO_VIVO);
            List<OnibusPrevisto> onibus = new ArrayList<>();
            for (JsonNode linha : p.path("l")) {
                int sentido = linha.path("sl").asInt(1);
                String destino = linha.path(sentido == 1 ? "lt0" : "lt1").asText("");
                for (JsonNode v : linha.path("vs")) {
                    String t = v.path("t").asText("");
                    onibus.add(new OnibusPrevisto(linha.path("c").asText(""), destino, sentido, t,
                            minutosEntre(hr, t), v.path("a").asBoolean(false),
                            hasher.hash(v.path("p").asText(""))));
                }
            }
            onibus.sort(Comparator.comparingInt(OnibusPrevisto::minutos));
            return new DadosPrevisao(ponto, hr, onibus);
        });
    }

    // ---------- utilidades ----------

    /** Minutos de hr até t ("HH:MM"), tratando a virada da meia-noite. Valores inválidos viram 0. */
    static int minutosEntre(String hr, String t) {
        try {
            int d = minutosDoDia(t) - minutosDoDia(hr);
            if (d < -720) {
                d += 1440;
            }
            return Math.max(d, 0);
        } catch (RuntimeException e) {
            return 0;
        }
    }

    private static int minutosDoDia(String hhmm) {
        String[] p = hhmm.split(":");
        return Integer.parseInt(p[0].trim()) * 60 + Integer.parseInt(p[1].trim());
    }

    private static String textoOuNulo(JsonNode n, String campo) {
        JsonNode v = n.get(campo);
        return v == null || v.isNull() || v.asText().isBlank() ? null : v.asText();
    }

    private static Double numeroOuNulo(JsonNode n, String campo) {
        JsonNode v = n.get(campo);
        return v == null || !v.isNumber() ? null : v.asDouble();
    }
}

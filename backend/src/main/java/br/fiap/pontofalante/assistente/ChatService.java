package br.fiap.pontofalante.assistente;

import br.fiap.pontofalante.assistente.Chat.FonteCitada;
import br.fiap.pontofalante.assistente.Chat.RespostaChat;
import br.fiap.pontofalante.sistema.PfProps;
import com.fasterxml.jackson.databind.JsonNode;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import br.fiap.pontofalante.sistema.ErroApi;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.client.HttpClientErrorException;
import org.springframework.web.client.RestClient;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;

import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * Perguntas de tempo real são respondidas pelo backend (AssistenteTempoReal); as demais vão ao serviço GenAI. Se ele estiver fora (PC desligado, túnel caído, timeout, 4xx/5xx),
 * devolve um aviso amigável com disponivel=false e abre um "disjuntor" simples que evita novas tentativas por 30 s.
 * O texto da pergunta nunca é gravado nem registrado em log.
 */
@Service
public class ChatService {
    private static final Logger log = LoggerFactory.getLogger(ChatService.class);
    static final String MSG_INDISPONIVEL = "O assistente está indisponível agora. Tente de novo em alguns minutos.";

    private final PfProps props;
    private final RestClient rest;
    private final AssistenteTempoReal tempoReal;
    private final EnderecoGenai endereco;
    private volatile long circuitoAbertoAteNanos;
    /** Muda a cada endereço registrado: falha de uma chamada ao túnel antigo não reabre o disjuntor do novo. */
    private final java.util.concurrent.atomic.AtomicLong geracao = new java.util.concurrent.atomic.AtomicLong();

    public ChatService(PfProps props, AssistenteTempoReal tempoReal) {
        this(props, tempoReal, new EnderecoGenai(props));
    }

    @org.springframework.beans.factory.annotation.Autowired
    public ChatService(PfProps props, AssistenteTempoReal tempoReal, EnderecoGenai endereco) {
        this.props = props;
        this.tempoReal = tempoReal;
        this.endereco = endereco;
        this.rest = ClienteGenai.criar(props, props.genaiConnectTimeoutMs(), props.genaiReadTimeoutMs());
    }

    private static final java.util.regex.Pattern OCORRENCIAS = java.util.regex.Pattern.compile(
            // "problema" sozinho não basta ("problema no meu bilhete" é pergunta de regra): precisa falar do transporte.
            "\\b(ocorrencias?|problemas?)\\b(?!.*\\b(bilhete|cartao|recarga|credito|cadastro)\\b).*\\b(transporte|onibus|linhas?|transito)\\b"
                    + "|\\bboletim\\b|\\bsituacao d[aeo]s? (linhas?|onibus|transporte)\\b|\\bcomo esta[o]? (o transporte|os onibus|as linhas)\\b"
                    + "|\\blinhas? (com|em) (atraso|atencao|problema)\\b|\\batrasos? hoje\\b");
    private br.fiap.pontofalante.rpa.BoletimService boletim;

    /** Opcional: sem o serviço do boletim (testes unitários), a pergunta segue o fluxo normal. */
    @org.springframework.beans.factory.annotation.Autowired(required = false)
    void setBoletim(br.fiap.pontofalante.rpa.BoletimService boletim) {
        this.boletim = boletim;
    }

    /**
     * "Tem algum problema no transporte hoje?": responde com o último boletim do robô, dizendo a data e a natureza do
     * dado (estimado, simulado ou indisponível). O boletim não registra acidentes nem interdições, e a resposta diz isso.
     */
    java.util.Optional<RespostaChat> respostaDoBoletim(String pergunta) {
        if (boletim == null || !OCORRENCIAS.matcher(AssistenteTempoReal.normalizar(pergunta)).find()) {
            return java.util.Optional.empty();
        }
        var fonte = List.of(new FonteCitada("Boletim diário do Ponto Falante (robô sobre previsões da SPTrans)", ""));
        var acoes = List.of(new Chat.Acao("Abrir o boletim", null, "/boletim"));
        try {
            var b = boletim.ultimo();
            String natureza = b.path("dados_simulados").asBoolean(false) ? "SIMULADO" : b.path("natureza_dados").asText("");
            String rotulo = switch (natureza) {
                case "SIMULADO" -> "dados simulados de demonstração";
                case "INDISPONIVEL" -> "sem dados suficientes";
                case "ESTIMADO" -> "estimativa a partir de previsões reais da SPTrans, não atrasos medidos";
                default -> "classificação não informada; não é possível confirmar a natureza dos dados";
            };
            String texto = "Boletim de " + b.path("data_referencia").asText("data não informada") + " (" + rotulo + "): "
                    + b.path("resumo_falado").asText("sem resumo.")
                    + (b.path("desatualizado").asBoolean(false) ? " Atenção: este boletim está desatualizado." : "")
                    + (!java.time.LocalDate.now(java.time.ZoneId.of("America/Sao_Paulo")).toString().equals(b.path("data_referencia").asText())
                        ? " Este boletim não confirma a situação de hoje." : "")
                    + " O boletim não registra acidentes, greves nem interdições; para isso, consulte a SPTrans ou o 156.";
            return java.util.Optional.of(new RespostaChat(texto, fonte, java.util.Set.of("ESTIMADO", "SIMULADO").contains(natureza) ? "media" : "baixa",
                    false, true, null, "BOLETIM", Chat.Contexto.vazio(), acoes).comNatureza(natureza));
        } catch (ErroApi e) {
            return java.util.Optional.of(new RespostaChat("Ainda não há boletim publicado, então não tenho um resumo das linhas. "
                    + "Para ocorrências do dia, consulte a SPTrans ou o 156.", fonte, "baixa", false, true, null, "BOLETIM",
                    Chat.Contexto.vazio(), List.of()));
        }
    }

    /** Identificador pseudônimo do usuário para a cota individual na GenAI: hash salgado do IP, nunca o IP. */
    public String idCliente(String ip) {
        try {
            MessageDigest md = MessageDigest.getInstance("SHA-256");
            md.update(props.salt().getBytes(StandardCharsets.UTF_8));
            md.update((byte) 0);
            md.update(String.valueOf(ip).getBytes(StandardCharsets.UTF_8));
            return HexFormat.of().formatHex(md.digest()).substring(0, 32);
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException(e);
        }
    }

    public RespostaChat perguntar(String pergunta) {
        return perguntar(pergunta, null);
    }

    public RespostaChat perguntar(String pergunta, String idCliente) {
        return perguntar(pergunta, idCliente, null);
    }

    public RespostaChat perguntar(String pergunta, String idCliente, Chat.Contexto contexto) {
        // Outra cidade: explica a limitação antes de qualquer consulta, sem mandar ao 156/SPTrans de São Paulo.
        var foraDaArea = ForaDaArea.responder(pergunta);
        if (foraDaArea.isPresent()) {
            return foraDaArea.get().comContexto(contexto == null ? Chat.Contexto.vazio() : contexto, List.of());
        }
        var doBoletim = respostaDoBoletim(pergunta);
        if (doBoletim.isPresent()) {
            return doBoletim.get();
        }
        // Horários e previsões vêm só do backend (SPTrans ou demonstração identificada), nunca do modelo.
        long inicioTempoReal = System.nanoTime();
        var direta = contexto == null ? tempoReal.responder(pergunta) : tempoReal.responder(pergunta, contexto);
        if (direta.isPresent()) {
            RespostaChat r = direta.get();
            return new RespostaChat(r.resposta(), r.fontes(), r.confianca(), r.naoConsta(), r.disponivel(),
                    (int) ((System.nanoTime() - inicioTempoReal) / 1_000_000), r.origem(), r.contexto(),
                    comAcompanhamento(r.origem(), r.contexto(), r.acoes()));
        }
        Chat.Contexto memoria = contextoRegra(pergunta, contexto);
        String consulta = pergunta;
        if (memoria.tema() != null && contexto != null && memoria.tema().equals(contexto.tema())
                && AssistenteTempoReal.normalizar(pergunta).matches("^(e |nesse |nessa |isso |ele |ela ).*")) {
            consulta = "Sobre " + switch (memoria.tema()) {
                case "BILHETE" -> "Bilhete Único";
                case "GRATUIDADE" -> "gratuidade no ônibus municipal de São Paulo";
                default -> "acessibilidade no ônibus municipal de São Paulo";
            } + (memoria.publico() == null ? "" : switch (memoria.publico()) {
                case "IDOSO" -> " para pessoa idosa";
                case "PCD" -> " para pessoa com deficiência";
                default -> " para estudante";
            }) + (memoria.idade() == null ? "" : " de " + memoria.idade() + " anos") + ": " + pergunta;
        }
        long geracaoDaChamada = geracao.get();
        var base = endereco.base();
        if (base.isEmpty()) {
            return indisponivel().comContexto(memoria, List.of());
        }
        if (System.nanoTime() - circuitoAbertoAteNanos < 0) {
            return indisponivel().comContexto(memoria, List.of());
        }
        long inicio = System.nanoTime();
        try {
            JsonNode r = rest.post().uri(base.get() + "/chat")
                    .header("X-API-Key", props.genaiApiKey() == null ? "" : props.genaiApiKey())
                    .headers(h -> { if (idCliente != null) h.set("X-PF-Cliente", idCliente); })
                    .body(Map.of("pergunta", consulta.length() <= 500 ? consulta : pergunta))
                    .retrieve().body(JsonNode.class);
            RespostaChat resposta = converter(r, (System.nanoTime() - inicio) / 1_000_000);
            if (resposta == null) {
                throw new IllegalStateException("resposta sem texto");
            }
            return resposta.comContexto(memoria, List.of());
        } catch (HttpClientErrorException.TooManyRequests e) {
            // Limite da GenAI (individual ou de capacidade): avisa o usuário sem derrubar o assistente para todos.
            throw new ErroApi(HttpStatus.TOO_MANY_REQUESTS, "MUITAS_PERGUNTAS",
                    "O assistente está recebendo muitas perguntas agora. Espere um minuto e tente de novo.");
        } catch (Exception e) {
            // Só o tipo da falha vai para o log; nunca a pergunta.
            log.warn("Assistente (GenAI) indisponível: {}", e.getClass().getSimpleName());
            abrirCircuito(geracaoDaChamada);
            return indisponivel().comContexto(memoria, List.of());
        }
    }

    /**
     * Depois de uma previsão em tempo real com ponto e linha conhecidos, oferece levar a conversa ao Embarque
     * Assistido, que continua acompanhando e avisa por voz. Só monta o link; nada é iniciado sem a pessoa tocar.
     */
    static List<Chat.Acao> comAcompanhamento(String origem, Chat.Contexto c, List<Chat.Acao> acoes) {
        List<Chat.Acao> lista = new ArrayList<>(acoes == null ? List.of() : acoes);
        if (!"TEMPO_REAL".equals(origem) || c == null || c.ponto() == null || c.linha() == null
                || lista.stream().anyMatch(a -> a.rota() != null && a.rota().startsWith("/embarque"))) {
            return lista;
        }
        String rota = "/embarque?ponto=" + c.ponto() + "&linha=" + c.linha() + (c.sentido() == null ? "" : "&sentido=" + c.sentido());
        lista.add(0, new Chat.Acao("Acompanhar e avisar por voz", null, rota));
        return lista;
    }

    static RespostaChat converter(JsonNode r, long msTotal) {
        if (r == null || !r.hasNonNull("resposta") || r.get("resposta").asText().isBlank()) {
            return null;
        }
        List<FonteCitada> fontes = new ArrayList<>();
        for (JsonNode f : r.path("fontes")) {
            String url = f.path("url").asText("");
            fontes.add(new FonteCitada(f.path("documento").asText(""), f.path("trecho_id").asText(""),
                    url.matches("https://[a-zA-Z0-9.-]+/[^\\s]*") ? url : null));
        }
        String confianca = r.path("confianca").asText("baixa");
        if (!List.of("alta", "media", "baixa").contains(confianca)) {
            confianca = "baixa";
        }
        Integer ms = r.hasNonNull("latencia_ms") ? r.get("latencia_ms").asInt() : (int) msTotal;
        return new RespostaChat(r.get("resposta").asText(), fontes, confianca, r.path("nao_consta").asBoolean(false),
                true, ms, "BASE_OFICIAL");
    }

    static RespostaChat indisponivel() {
        return new RespostaChat(MSG_INDISPONIVEL, List.of(), "baixa", true, false, null, "INDISPONIVEL");
    }

    static Chat.Contexto contextoRegra(String pergunta, Chat.Contexto anterior) {
        String t = AssistenteTempoReal.normalizar(pergunta);
        boolean segue = anterior != null && t.matches("^(e |nesse |nessa |isso |ele |ela ).*");
        var anos = java.util.regex.Pattern.compile("\\b(\\d{1,3}) anos\\b|\\b(?:tenho|fez|completei) (\\d{1,3})\\b").matcher(t);
        Integer idade = anos.find() ? Integer.valueOf(anos.group(1) == null ? anos.group(2) : anos.group(1)) : segue ? anterior.idade() : null;
        if (idade != null && idade > 120) idade = null;
        String publico = t.matches(".*\\b(deficiencia|pcd|cadeirante|cadeira|autista)\\b.*") ? "PCD"
                : t.matches(".*\\b(estudante|escola|faculdade|universitario|aluno)\\b.*") ? "ESTUDANTE"
                : t.matches(".*\\b(idos[oa]|avo)\\b.*") ? "IDOSO"
                : segue && anterior.publico() != null ? anterior.publico()
                : idade != null && idade >= 60 ? "IDOSO" : null;
        String tema = t.matches(".*\\b(gratuidade|idos[oa]|pago|gratis|gratuito)\\b.*") ? "GRATUIDADE"
                : t.matches(".*\\b(bilhete|cartao|recarga)\\b.*") ? "BILHETE"
                : t.matches(".*\\b(acessibilidade|cadeirante|cadeira|rampa)\\b.*") ? "ACESSIBILIDADE"
                : segue && anterior.tema() != null ? anterior.tema()
                : idade != null && idade >= 60 ? "GRATUIDADE" : null;
        return new Chat.Contexto(null, null, null, null, tema, publico, idade);
    }

    /** Novo endereço registrado: não esperar o fim do disjuntor aberto pelo túnel antigo. */
    synchronized void fecharCircuito() {
        geracao.incrementAndGet();
        circuitoAbertoAteNanos = System.nanoTime();
    }

    /** Abre o disjuntor só se a falha veio do endereço atual (mesma geração). */
    synchronized void abrirCircuito(long geracaoDaChamada) {
        if (geracaoDaChamada == geracao.get()) {
            circuitoAbertoAteNanos = System.nanoTime() + Duration.ofSeconds(props.genaiCircuitoSegundos()).toNanos();
        }
    }

    long geracaoAtual() {
        return geracao.get();
    }

    boolean circuitoAberto() {
        return System.nanoTime() - circuitoAbertoAteNanos < 0;
    }
}

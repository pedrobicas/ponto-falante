package br.fiap.pontofalante.rpa;

import br.fiap.pontofalante.sistema.ConfigWeb;
import br.fiap.pontofalante.sistema.ErroApi;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;
import org.springframework.http.HttpStatus;
import org.springframework.transaction.annotation.Transactional;

import java.time.Clock;
import java.time.Duration;
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.time.format.DateTimeParseException;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.regex.Pattern;

/**
 * Recebe e devolve as amostras reais de previsão coletadas pelo robô RPA.
 * Cada amostra é avaliada sozinha: as válidas são gravadas e as demais voltam com o motivo. Regras: a fonte precisa
 * ser a SPTrans (OLHO_VIVO ou olhovivo; amostra SIMULADA é recusada), consultado_em dentro das últimas 48 h e no
 * máximo 5 min no futuro, ponto e ônibus no formato do contrato. Mesmo ponto e mesmo instante = duplicada (idempotente).
 */
@Service
public class AmostraPrevisaoService {
    private static final Logger log = LoggerFactory.getLogger(AmostraPrevisaoService.class);
    static final int MAX_AMOSTRAS_POR_ENVIO = 60;
    static final int MAX_ONIBUS_POR_AMOSTRA = 200;
    static final int MAX_AMOSTRAS_POR_DIA = 2000;
    static final Duration JANELA_PASSADO = Duration.ofHours(48);
    static final Duration TOLERANCIA_FUTURO = Duration.ofMinutes(5);
    private static final Pattern PONTO = Pattern.compile("^[0-9A-Za-z-]{1,40}$");
    private static final Pattern LINHA = Pattern.compile("^[0-9A-Za-z-]{1,20}$");
    private static final Pattern HHMM = Pattern.compile("^([01]\\d|2[0-3]):[0-5]\\d$");
    private static final Pattern EXECUCAO = Pattern.compile("^[0-9A-Za-z_.:-]{1,64}$");

    private final AmostraPrevisaoRepository repo;
    private final ObjectMapper mapper;
    private final Clock relogio;

    public AmostraPrevisaoService(AmostraPrevisaoRepository repo, ObjectMapper mapper, Clock relogio) {
        this.repo = repo;
        this.mapper = mapper;
        this.relogio = relogio;
    }

    public record Rejeitada(int indice, String motivo) {
    }

    public record ResultadoEnvio(int recebidas, int gravadas, int duplicadas, List<Rejeitada> rejeitadas) {
    }

    /** Motivo curto e estável de recusa de uma amostra (vai para log e auditoria do robô). */
    private static final class Recusa extends RuntimeException {
        Recusa(String motivo) {
            super(motivo, null, false, false);
        }
    }

    @Transactional
    public ResultadoEnvio receber(JsonNode corpo) {
        if (corpo == null || !corpo.isObject() || !corpo.path("amostras").isArray()) {
            throw ErroApi.requisicaoInvalida("Envie um objeto com a lista amostras.");
        }
        ArrayNode lista = (ArrayNode) corpo.path("amostras");
        if (lista.isEmpty() || lista.size() > MAX_AMOSTRAS_POR_ENVIO) {
            throw ErroApi.requisicaoInvalida("A lista amostras deve ter de 1 a " + MAX_AMOSTRAS_POR_ENVIO + " itens.");
        }
        String execucao = null;
        JsonNode ex = corpo.path("execucao_id");
        if (!ex.isMissingNode() && !ex.isNull()) {
            if (!ex.isTextual() || !EXECUCAO.matcher(ex.asText()).matches()) {
                throw ErroApi.requisicaoInvalida("execucao_id inválido.");
            }
            execucao = ex.asText();
        }
        OffsetDateTime agora = OffsetDateTime.now(relogio);
        int gravadas = 0;
        int duplicadas = 0;
        List<Rejeitada> rejeitadas = new ArrayList<>();
        for (int i = 0; i < lista.size(); i++) {
            AmostraPrevisao a;
            try {
                a = converter(lista.get(i), agora, execucao);
            } catch (Recusa r) {
                rejeitadas.add(new Rejeitada(i, r.getMessage()));
                continue;
            }
            if (repo.inserirSeAusente(a) == 0) {
                duplicadas++;
                continue;
            }
            gravadas++;
        }
        log.info("Amostras de previsão: {} gravadas, {} duplicadas, {} rejeitadas (execução {})",
                gravadas, duplicadas, rejeitadas.size(), execucao);
        return new ResultadoEnvio(lista.size(), gravadas, duplicadas, rejeitadas);
    }

    private AmostraPrevisao converter(JsonNode n, OffsetDateTime agora, String execucao) {
        if (!n.isObject()) {
            throw new Recusa("formato_invalido");
        }
        String fonte = n.path("fonte").asText("");
        if ("SIMULADO".equalsIgnoreCase(fonte) || "simulador".equalsIgnoreCase(fonte)) {
            throw new Recusa("fonte_simulada");
        }
        if (!"OLHO_VIVO".equals(fonte) && !AmostraPrevisao.FONTE.equals(fonte)) {
            throw new Recusa("fonte_desconhecida");
        }
        if (!"PREVISAO".equals(n.path("tipo").asText())) {
            throw new Recusa("tipo_inesperado");
        }
        JsonNode pontoNo = n.path("ponto");
        String ponto = pontoNo.isIntegralNumber() || pontoNo.isTextual() ? pontoNo.asText() : "";
        if (!PONTO.matcher(ponto).matches()) {
            throw new Recusa("ponto_invalido");
        }
        OffsetDateTime consultado;
        try {
            consultado = OffsetDateTime.parse(n.path("consultado_em").asText("")).truncatedTo(ChronoUnit.SECONDS);
        } catch (DateTimeParseException e) {
            throw new Recusa("consultado_em_invalido");
        }
        if (consultado.isAfter(agora.plus(TOLERANCIA_FUTURO)) || consultado.isBefore(agora.minus(JANELA_PASSADO))) {
            throw new Recusa("fora_da_janela");
        }
        String referencia = null;
        JsonNode ref = n.path("horario_referencia");
        if (ref.isTextual()) {
            if (!HHMM.matcher(ref.asText()).matches()) {
                throw new Recusa("horario_referencia_invalido");
            }
            referencia = ref.asText();
        }
        JsonNode onibus = n.path("onibus");
        if (!onibus.isArray() || onibus.size() > MAX_ONIBUS_POR_AMOSTRA) {
            throw new Recusa("onibus_invalido");
        }
        ArrayNode normalizados = mapper.createArrayNode();
        for (JsonNode o : onibus) {
            normalizados.add(normalizarOnibus(o));
        }
        String json;
        try {
            json = mapper.writeValueAsString(normalizados);
        } catch (JsonProcessingException e) {
            throw new Recusa("onibus_invalido");
        }
        LocalDate data = consultado.atZoneSameInstant(ConfigWeb.SAO_PAULO).toLocalDate();
        return new AmostraPrevisao(data, ponto, consultado, referencia, normalizados.size(), json, execucao,
                OffsetDateTime.now(relogio));
    }

    private ObjectNode normalizarOnibus(JsonNode o) {
        if (!o.isObject()) {
            throw new Recusa("onibus_invalido");
        }
        String linha = o.path("linha").isTextual() ? o.path("linha").asText() : o.path("letreiro").asText("");
        String previsto = o.path("previsto_em").asText("");
        JsonNode minutos = o.path("minutos");
        if (!LINHA.matcher(linha).matches() || !HHMM.matcher(previsto).matches()
                || !minutos.isIntegralNumber() || !minutos.canConvertToInt()
                || minutos.asInt() < 0 || minutos.asInt() > 240) {
            throw new Recusa("onibus_invalido");
        }
        ObjectNode s = mapper.createObjectNode();
        s.put("linha", linha);
        JsonNode sentido = o.path("sentido");
        if (sentido.isIntegralNumber()) {
            s.put("sentido", sentido.asInt());
        } else if (sentido.isTextual() && sentido.asText().length() <= 40) {
            s.put("sentido", sentido.asText());
        }
        String destino = o.path("destino").asText("");
        if (!destino.isEmpty()) {
            s.put("destino", destino.length() > 80 ? destino.substring(0, 80) : destino);
        }
        s.put("previsto_em", previsto);
        s.put("minutos", minutos.asInt());
        if (o.path("acessivel").isBoolean()) {
            s.put("acessivel", o.path("acessivel").asBoolean());
        }
        String veiculo = o.path("veiculo").asText("");
        if (!veiculo.isEmpty()) {
            if (veiculo.length() > 40) {
                throw new Recusa("onibus_invalido");
            }
            s.put("veiculo", veiculo);
        }
        return s;
    }

    public List<Map<String, Object>> doDia(LocalDate data) {
        LocalDate hoje = LocalDate.now(relogio);
        if (data.isBefore(hoje.minusDays(HistoricoService.DIAS_PASSADO)) || data.isAfter(hoje.plusDays(1))) {
            throw ErroApi.requisicaoInvalida("Escolha uma data entre " + hoje.minusDays(HistoricoService.DIAS_PASSADO)
                    + " e " + hoje.plusDays(1) + ".");
        }
        List<Map<String, Object>> saida = new ArrayList<>();
        List<AmostraPrevisao> amostras = repo.findByDataOrderByConsultadoEmAscPontoAsc(data,
                PageRequest.of(0, MAX_AMOSTRAS_POR_DIA + 1));
        if (amostras.size() > MAX_AMOSTRAS_POR_DIA) {
            throw new ErroApi(HttpStatus.SERVICE_UNAVAILABLE, "LIMITE_AMOSTRAS",
                    "O dia excede o limite de leitura de amostras; o boletim não deve usar uma lista truncada.");
        }
        for (AmostraPrevisao a : amostras) {
            Map<String, Object> m = new LinkedHashMap<>();
            m.put("ponto", a.ponto);
            m.put("consultado_em", a.consultadoEm.atZoneSameInstant(ConfigWeb.SAO_PAULO).toOffsetDateTime().toString());
            m.put("horario_referencia", a.horarioReferencia);
            m.put("fonte", a.fonte);
            m.put("tipo_registro", a.tipoRegistro);
            m.put("total_onibus", a.totalOnibus);
            try {
                m.put("onibus", mapper.readTree(a.onibus));
            } catch (JsonProcessingException e) {
                throw new IllegalStateException("Amostra armazenada ilegível", e);
            }
            saida.add(m);
        }
        return saida;
    }
}

package br.fiap.pontofalante.rpa;

import br.fiap.pontofalante.sistema.ConfigWeb;
import br.fiap.pontofalante.sistema.ErroApi;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.springframework.stereotype.Service;

import java.time.Clock;
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.time.format.DateTimeParseException;
import java.util.List;

@Service
public class BoletimService {
    private final BoletimRepository repo;
    private final ObjectMapper mapper;
    private final Clock relogio;

    public BoletimService(BoletimRepository repo, ObjectMapper mapper, Clock relogio) {
        this.repo = repo;
        this.mapper = mapper;
        this.relogio = relogio;
    }

    /** Valida os campos obrigatórios do contrato e grava (upsert por data_referencia). */
    public Boletim publicar(JsonNode corpo) {
        if (corpo == null || !corpo.isObject()) {
            throw ErroApi.requisicaoInvalida("O boletim deve ser um objeto JSON.");
        }
        LocalDate data = dataReferencia(corpo);
        exigirTexto(corpo, "gerado_em");
        if (!corpo.path("desatualizado").isBoolean()) {
            throw ErroApi.requisicaoInvalida("Campo obrigatório ausente ou inválido: desatualizado.");
        }
        if (!corpo.path("linhas").isArray()) {
            throw ErroApi.requisicaoInvalida("Campo obrigatório ausente ou inválido: linhas.");
        }
        if (!corpo.path("resumo_falado").isTextual()) {
            throw ErroApi.requisicaoInvalida("Campo obrigatório ausente ou inválido: resumo_falado.");
        }
        boolean simulados = validarProveniencia(corpo);
        String json;
        try {
            json = mapper.writeValueAsString(corpo);
        } catch (JsonProcessingException e) {
            throw ErroApi.requisicaoInvalida("O boletim não pôde ser lido.");
        }
        Boletim b = new Boletim(data, json, corpo.path("desatualizado").asBoolean(),
                simulados, OffsetDateTime.now(relogio));
        return repo.save(b);
    }

    /**
     * A identificação de dados simulados nunca é inferida: dados_simulados precisa ser booleano explícito e
     * coerente com fonte_dados (contagem de registros por origem). Boletim contraditório é rejeitado.
     */
    private static boolean validarProveniencia(JsonNode corpo) {
        JsonNode flag = corpo.path("dados_simulados");
        if (!flag.isBoolean()) {
            throw ErroApi.requisicaoInvalida("Campo obrigatório ausente ou inválido: dados_simulados (booleano).");
        }
        JsonNode fontes = corpo.path("fonte_dados");
        if (!fontes.isObject()) {
            throw ErroApi.requisicaoInvalida("Campo obrigatório ausente ou inválido: fonte_dados.");
        }
        long simulador = contagem(fontes, "simulador");
        contagem(fontes, "olhovivo");
        if (flag.asBoolean() != (simulador > 0)) {
            throw ErroApi.requisicaoInvalida("dados_simulados contradiz fonte_dados.simulador.");
        }
        return flag.asBoolean();
    }

    private static long contagem(JsonNode fontes, String campo) {
        JsonNode n = fontes.path(campo);
        if (!n.isIntegralNumber() || n.asLong() < 0) {
            throw ErroApi.requisicaoInvalida("fonte_dados." + campo + " deve ser um inteiro não negativo.");
        }
        return n.asLong();
    }

    private static LocalDate dataReferencia(JsonNode corpo) {
        String texto = exigirTexto(corpo, "data_referencia");
        try {
            return LocalDate.parse(texto);
        } catch (DateTimeParseException e) {
            throw ErroApi.requisicaoInvalida("data_referencia deve estar no formato AAAA-MM-DD.");
        }
    }

    private static String exigirTexto(JsonNode corpo, String campo) {
        JsonNode n = corpo.path(campo);
        if (!n.isTextual() || n.asText().isBlank()) {
            throw ErroApi.requisicaoInvalida("Campo obrigatório ausente ou inválido: " + campo + ".");
        }
        return n.asText();
    }

    public ObjectNode ultimo() {
        Boletim b = repo.findFirstByOrderByDataReferenciaDesc()
                .orElseThrow(() -> ErroApi.naoEncontrado("Ainda não há boletim publicado."));
        return comRecebidoEm(b);
    }

    public ObjectNode porData(LocalDate data) {
        Boletim b = repo.findById(data)
                .orElseThrow(() -> ErroApi.naoEncontrado("Não há boletim para essa data."));
        return comRecebidoEm(b);
    }

    public LocalDate dataDoUltimo() {
        return repo.findFirstByOrderByDataReferenciaDesc().map(b -> b.dataReferencia).orElse(null);
    }

    public record Resumo(LocalDate dataReferencia, boolean desatualizado, boolean dadosSimulados, int criticas,
                         int atencao, OffsetDateTime recebidoEm) {
    }

    public List<Resumo> resumos() {
        return repo.findTop30ByOrderByDataReferenciaDesc().stream().map(b -> {
            int criticas = 0;
            int atencao = 0;
            try {
                for (JsonNode l : mapper.readTree(b.conteudo).path("linhas")) {
                    String status = l.path("status").asText("");
                    if ("CRITICA".equals(status)) {
                        criticas++;
                    } else if ("ATENCAO".equals(status)) {
                        atencao++;
                    }
                }
            } catch (JsonProcessingException e) {
                // conteúdo ilegível: conta zero
            }
            return new Resumo(b.dataReferencia, b.desatualizado, b.dadosSimulados, criticas, atencao,
                    b.recebidoEm.atZoneSameInstant(ConfigWeb.SAO_PAULO).toOffsetDateTime());
        }).toList();
    }

    private ObjectNode comRecebidoEm(Boletim b) {
        try {
            JsonNode lido = mapper.readTree(b.conteudo);
            ObjectNode saida = lido.isObject() ? (ObjectNode) lido : mapper.createObjectNode();
            saida.put("recebido_em", b.recebidoEm.atZoneSameInstant(ConfigWeb.SAO_PAULO).toOffsetDateTime().toString());
            return saida;
        } catch (JsonProcessingException e) {
            throw new IllegalStateException("Boletim armazenado ilegível", e);
        }
    }
}

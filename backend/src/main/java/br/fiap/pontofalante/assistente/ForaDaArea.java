package br.fiap.pontofalante.assistente;

import br.fiap.pontofalante.assistente.Chat.RespostaChat;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Perguntas sobre o transporte de outra cidade. O Ponto Falante só tem fontes do transporte municipal de São Paulo,
 * então a resposta explica a limitação e manda procurar o órgão da cidade citada, sem inventar regras nem contatos
 * (não encaminha ao 156 nem à SPTrans, que são de São Paulo).
 *
 * <p>Só entram cidades sem homônimo conhecido de bairro ou rua paulistana que costume vir depois de "em", "no" ou
 * "na" (por isso ficam de fora, por exemplo, Belém, Campo Grande, Natal, Vitória, Rio Branco, São Luís e Santos, que
 * também são avenidas ou bairros de São Paulo), e o nome precisa vir depois de
 * uma preposição de lugar.</p>
 */
final class ForaDaArea {

    private static final Map<String, String> CIDADES = new LinkedHashMap<>();

    static {
        for (String c : List.of("Rio de Janeiro", "Belo Horizonte", "Porto Alegre", "Curitiba", "Salvador", "Recife",
                "Fortaleza", "Brasília", "Goiânia", "Manaus", "Florianópolis", "Maceió", "João Pessoa", "Teresina",
                "Cuiabá", "Aracaju", "Porto Velho", "Macapá", "Palmas", "Niterói",
                "Campinas", "Sorocaba", "Ribeirão Preto", "Londrina", "Joinville", "Uberlândia",
                "Juiz de Fora", "Lisboa", "Buenos Aires", "Nova York")) {
            CIDADES.put(AssistenteTempoReal.normalizar(c), c);
        }
    }

    private static final Pattern PADRAO = Pattern.compile("\\b(?:em|no|na|de|do|da|para|pra|pro)\\s+("
            + String.join("|", CIDADES.keySet().stream().map(Pattern::quote).toList()) + ")\\b");

    private ForaDaArea() {
    }

    /** Nome da cidade de fora citada na pergunta, se houver. */
    static Optional<String> cidade(String pergunta) {
        if (pergunta == null) {
            return Optional.empty();
        }
        Matcher m = PADRAO.matcher(AssistenteTempoReal.normalizar(pergunta));
        return m.find() ? Optional.of(CIDADES.get(m.group(1))) : Optional.empty();
    }

    static Optional<RespostaChat> responder(String pergunta) {
        return cidade(pergunta).map(c -> new RespostaChat(
                "O Ponto Falante atende só o transporte público municipal da cidade de São Paulo e não tem "
                        + "informações oficiais sobre " + c + ". Para saber as regras de lá, consulte o órgão ou a "
                        + "empresa responsável pelo transporte público de " + c + ".",
                List.of(), "baixa", true, true, 0, "FORA_DA_AREA"));
    }
}

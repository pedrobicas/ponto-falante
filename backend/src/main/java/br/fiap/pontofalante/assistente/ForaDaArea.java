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
 * <p>Regras para não confundir com ruas e bairros paulistanos:</p>
 * <ul>
 *   <li>a cidade precisa vir depois de "em", "no", "de", "do", "para", "pra" ou "pro" (com "o" opcional); "na" e "da"
 *   ficam de fora porque costumam indicar rua ("na Campinas" é a Alameda Campinas);</li>
 *   <li>nomes que também são ruas ou bairros de São Paulo (Santos, Belém, Natal, Vitória, Rio Branco, São Luís, Campo
 *   Grande) só contam com qualificador explícito: "cidade de Santos", "Belém do Pará", "Rio Branco, Acre";</li>
 *   <li>pergunta com código de ponto de São Paulo ("ponto 70016916") é sempre consulta local, mesmo citando outra
 *   cidade ("sou de Curitiba").</li>
 * </ul>
 */
final class ForaDaArea {

    private static final Map<String, String> CIDADES = new LinkedHashMap<>();
    private static final Map<Pattern, String> QUALIFICADAS = new LinkedHashMap<>();

    static {
        for (String c : List.of("Rio de Janeiro", "Belo Horizonte", "Porto Alegre", "Curitiba", "Salvador", "Recife",
                "Fortaleza", "Brasília", "Goiânia", "Manaus", "Florianópolis", "Maceió", "João Pessoa", "Teresina",
                "Cuiabá", "Aracaju", "Porto Velho", "Macapá", "Palmas", "Niterói", "Guarulhos", "Osasco",
                "Campinas", "Sorocaba", "Ribeirão Preto", "Londrina", "Joinville", "Uberlândia",
                "Juiz de Fora", "Lisboa", "Buenos Aires", "Nova York")) {
            CIDADES.put(AssistenteTempoReal.normalizar(c), c);
        }
        Map<String, String> homonimos = new LinkedHashMap<>();
        homonimos.put("santos", "Santos");
        homonimos.put("belem", "Belém");
        homonimos.put("natal", "Natal");
        homonimos.put("vitoria", "Vitória");
        homonimos.put("rio branco", "Rio Branco");
        homonimos.put("sao luis", "São Luís");
        homonimos.put("campo grande", "Campo Grande");
        homonimos.forEach((chave, nome) -> QUALIFICADAS.put(Pattern.compile("\\bcidade de " + chave + "\\b"), nome));
        QUALIFICADAS.put(Pattern.compile("\\bbelem (?:do para|pa)\\b"), "Belém");
        QUALIFICADAS.put(Pattern.compile("\\brio branco,? (?:no |em )?(?:acre|ac)\\b"), "Rio Branco");
        QUALIFICADAS.put(Pattern.compile("\\bnatal,? (?:no |em )?(?:rio grande do norte|rn)\\b"), "Natal");
        QUALIFICADAS.put(Pattern.compile("\\bvitoria,? (?:no |em )?(?:espirito santo|es)\\b"), "Vitória");
        QUALIFICADAS.put(Pattern.compile("\\bsao luis,? (?:no |em )?(?:maranhao|ma)\\b"), "São Luís");
        QUALIFICADAS.put(Pattern.compile("\\bcampo grande,? (?:no |em )?(?:mato grosso do sul|ms)\\b"), "Campo Grande");
        QUALIFICADAS.put(Pattern.compile("\\bbaixada santista\\b"), "Baixada Santista");
    }

    private static final Pattern PADRAO = Pattern.compile("\\b(?:em|no|de|do|para|pra|pro)\\s+(?:o\\s+)?("
            + String.join("|", CIDADES.keySet().stream().map(Pattern::quote).toList()) + ")\\b");
    private static final Pattern PONTO_PAULISTANO = Pattern.compile("\\b(?:ponto|parada|codigo)\\s+\\d{5,}\\b|\\b\\d{8,9}\\b");

    private ForaDaArea() {
    }

    /** Nome da cidade de fora citada na pergunta, se houver. */
    static Optional<String> cidade(String pergunta) {
        if (pergunta == null) {
            return Optional.empty();
        }
        String t = AssistenteTempoReal.normalizar(pergunta);
        if (PONTO_PAULISTANO.matcher(t).find()) {
            return Optional.empty();
        }
        for (var q : QUALIFICADAS.entrySet()) {
            if (q.getKey().matcher(t).find()) {
                return Optional.of(q.getValue());
            }
        }
        Matcher m = PADRAO.matcher(t);
        return m.find() ? Optional.of(CIDADES.get(m.group(1))) : Optional.empty();
    }

    static Optional<RespostaChat> responder(String pergunta) {
        return cidade(pergunta).map(c -> new RespostaChat(
                "O Ponto Falante atende só o transporte público municipal da cidade de São Paulo e não tem "
                        + "informações oficiais sobre " + artigo(c) + c + ". Para saber as regras de lá, consulte o "
                        + "órgão ou a empresa responsável pelo transporte público " + contracao(c) + c + ".",
                List.of(), "baixa", true, true, 0, "FORA_DA_AREA"));
    }

    /** Lugares que pedem artigo em português ("o Rio de Janeiro", "a Baixada Santista"). */
    private static final Map<String, String> ARTIGOS = Map.of("Rio de Janeiro", "o ", "Recife", "o ",
            "Baixada Santista", "a ");

    static String artigo(String lugar) {
        return ARTIGOS.getOrDefault(lugar, "");
    }

    /** "de" com o artigo do lugar: "do Rio de Janeiro", "da Baixada Santista", "de Curitiba". */
    static String contracao(String lugar) {
        return switch (artigo(lugar)) {
            case "o " -> "do ";
            case "a " -> "da ";
            default -> "de ";
        };
    }
}

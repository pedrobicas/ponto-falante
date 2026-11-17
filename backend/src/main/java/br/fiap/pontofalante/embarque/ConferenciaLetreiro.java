package br.fiap.pontofalante.embarque;

import br.fiap.pontofalante.embarque.EmbarqueDtos.LeituraLetreiro;
import br.fiap.pontofalante.embarque.EmbarqueDtos.ResultadoConferencia;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Compara o que o modelo de visão leu no letreiro com a linha que a pessoa espera. É uma regra determinística e
 * conservadora: na dúvida o resultado é INCONCLUSIVO, e toda frase pede a confirmação com o motorista, porque um
 * modelo de visão pode errar e embarcar no ônibus errado tem custo alto para quem não enxerga.
 */
public final class ConferenciaLetreiro {
    /**
     * Abaixo disso a leitura não é usada para afirmar nada. É o mesmo limiar por quadro do anunciador da equipe de
     * Visão (visao/src/anunciador.py). Na avaliação do relatório (25 letreiros com código + 16 só com destino), as
     * leituras validadas contra as linhas do ponto tiveram 0 linha errada em qualquer confiança; leituras sem
     * validação chegam do serviço com a confiança reduzida em 40%.
     */
    static final double CONFIANCA_MINIMA = 0.45;
    private static final Pattern LETREIRO = Pattern.compile("\\b(N?[0-9]{3,4}[A-Z]?)(?:\\s*-\\s*([0-9]{1,2}))?\\b");

    private ConferenciaLetreiro() {
    }

    public record Resultado(ResultadoConferencia resultado, String linhaLida, Double confianca, String frase) {
    }

    record Letreiro(String numero, String variante) {
        String texto() {
            return variante == null ? numero : numero + "-" + variante;
        }
    }

    /** "875a-10" -> 875A/10; "875A" -> 875A/null; textos sem número de linha -> null. */
    static Letreiro extrair(String texto) {
        if (texto == null) return null;
        String t = texto.toUpperCase(Locale.ROOT).replace('–', '-').replace('—', '-');
        Matcher m = LETREIRO.matcher(t);
        return m.find() ? new Letreiro(m.group(1), m.group(2)) : null;
    }

    public static Resultado comparar(String linhaEsperada, List<LeituraLetreiro> leituras) {
        return comparar(List.of(linhaEsperada), leituras, null, null);
    }

    /**
     * @param linhasEsperadas linhas que servem para a pessoa (a primeira é a principal, usada nas frases)
     * @param onibus          ônibus que o detector viu na foto (null = o serviço não informou)
     * @param letreiros       letreiros que o detector viu na foto (null = o serviço não informou)
     */
    public static Resultado comparar(List<String> linhasEsperadas, List<LeituraLetreiro> leituras, Integer onibus,
                                     Integer letreiros) {
        List<Letreiro> esperados = new ArrayList<>();
        for (String l : linhasEsperadas == null ? List.<String>of() : linhasEsperadas) {
            Letreiro e = extrair(l);
            if (e != null && !esperados.contains(e)) esperados.add(e);
        }
        if (esperados.isEmpty()) {
            throw new IllegalArgumentException("linha esperada inválida");
        }
        LeituraLetreiro melhor = null;
        Letreiro lido = null;
        for (LeituraLetreiro l : leituras == null ? List.<LeituraLetreiro>of() : leituras) {
            Letreiro candidato = extrair(l.texto());
            if (candidato == null || Double.isNaN(l.confianca())) continue;
            if (melhor == null || l.confianca() > melhor.confianca()) {
                melhor = l;
                lido = candidato;
            }
        }
        if (melhor == null || melhor.confianca() < CONFIANCA_MINIMA) {
            return new Resultado(ResultadoConferencia.INCONCLUSIVO, lido == null ? null : lido.texto(),
                    melhor == null ? null : melhor.confianca(), dicaInconclusivo(melhor != null, onibus, letreiros));
        }
        double conf = melhor.confianca();
        final Letreiro leitura = lido;
        Letreiro esperado = esperados.stream().filter(e -> e.numero().equals(leitura.numero()))
                .filter(e -> leitura.variante() == null || e.variante() == null || e.variante().equals(leitura.variante()))
                .findFirst()
                .orElse(esperados.stream().filter(e -> e.numero().equals(leitura.numero())).findFirst().orElse(null));
        if (esperado == null) {
            return new Resultado(ResultadoConferencia.NAO_CONFERE, lido.texto(), conf,
                    "Atenção: o letreiro parece ser da linha " + lido.texto() + ", não da " + descrever(esperados)
                            + " que você espera. Confirme com o motorista antes de embarcar.");
        }
        if (lido.variante() == null || esperado.variante() == null) {
            return new Resultado(ResultadoConferencia.NUMERO_CONFERE, lido.texto(), conf,
                    "Li o número " + lido.numero() + " no letreiro, mas não deu para confirmar a linha completa "
                            + esperado.texto() + ". Confira o destino ou pergunte ao motorista.");
        }
        if (!lido.variante().equals(esperado.variante())) {
            return new Resultado(ResultadoConferencia.NAO_CONFERE, lido.texto(), conf,
                    "Atenção: o letreiro parece ser da linha " + lido.texto() + ", uma variação diferente da "
                            + esperado.texto() + ". Confirme o destino com o motorista.");
        }
        return new Resultado(ResultadoConferencia.CONFERE, lido.texto(), conf,
                "O letreiro parece ser da linha " + esperado.texto() + ", a que você espera. "
                        + "Confirme com o motorista antes de embarcar.");
    }

    private static String descrever(List<Letreiro> esperados) {
        if (esperados.size() == 1) return esperados.get(0).texto();
        List<String> textos = esperados.stream().map(Letreiro::texto).toList();
        return String.join(", ", textos.subList(0, textos.size() - 1)) + " ou " + textos.get(textos.size() - 1);
    }

    /** Orienta quem não enxerga a apontar melhor, a partir do que o detector viu na foto. */
    static String dicaInconclusivo(boolean leuAlgo, Integer onibus, Integer letreiros) {
        if (!leuAlgo && letreiros != null && onibus != null && letreiros == 0 && onibus == 0) {
            return "Não encontrei ônibus na foto. Aponte a câmera para a frente do ônibus que está chegando e tente "
                    + "de novo, ou pergunte ao motorista qual é a linha.";
        }
        if (!leuAlgo && letreiros != null && letreiros == 0) {
            return "Vi o ônibus, mas não encontrei o letreiro. Aponte a câmera um pouco mais para cima, para o "
                    + "letreiro da frente, e tente de novo, ou pergunte ao motorista.";
        }
        if (!leuAlgo && letreiros != null) {
            return "Encontrei o letreiro, mas não consegui ler o número da linha. Ele pode estar mostrando só o "
                    + "destino: espere trocar e tente de novo, ou pergunte ao motorista.";
        }
        return "Não consegui ler o letreiro com segurança. Aponte a câmera para a frente do ônibus e tente de novo, "
                + "ou pergunte ao motorista qual é a linha.";
    }
}

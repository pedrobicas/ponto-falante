package br.fiap.pontofalante.embarque;

import br.fiap.pontofalante.embarque.EmbarqueDtos.LeituraLetreiro;
import br.fiap.pontofalante.embarque.EmbarqueDtos.ResultadoConferencia;

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
    /** Abaixo disso a leitura não é usada para afirmar nada. */
    static final double CONFIANCA_MINIMA = 0.6;
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
        Letreiro esperado = extrair(linhaEsperada);
        if (esperado == null) {
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
                    melhor == null ? null : melhor.confianca(),
                    "Não consegui ler o letreiro com segurança. Aponte a câmera para a frente do ônibus e tente de novo, "
                            + "ou pergunte ao motorista qual é a linha.");
        }
        double conf = melhor.confianca();
        if (!lido.numero().equals(esperado.numero())) {
            return new Resultado(ResultadoConferencia.NAO_CONFERE, lido.texto(), conf,
                    "Atenção: o letreiro parece ser da linha " + lido.texto() + ", não da " + esperado.texto()
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
}

package br.fiap.pontofalante.transporte;

import br.fiap.pontofalante.transporte.Modelos.OnibusPrevisto;

import java.util.List;
import java.util.Locale;

/** Monta a frase que o aplicativo ou o totem lê em voz alta. Sempre "previsto", nunca "chegou". */
public final class FraseFalada {
    private static final int MAXIMO_ONIBUS = 3;

    private FraseFalada() {
    }

    public static String montar(String nomePonto, List<OnibusPrevisto> onibus, boolean demonstracao) {
        StringBuilder sb = new StringBuilder();
        if (demonstracao) {
            sb.append("Demonstração. ");
        }
        sb.append(nomePonto == null || nomePonto.isBlank() ? "Ponto de ônibus" : "Ponto " + legivel(nomePonto)).append(". ");
        if (onibus == null || onibus.isEmpty()) {
            sb.append("Não há ônibus previstos agora.");
            return sb.toString();
        }
        int n = Math.min(MAXIMO_ONIBUS, onibus.size());
        for (int i = 0; i < n; i++) {
            OnibusPrevisto o = onibus.get(i);
            sb.append("Ônibus ").append(o.letreiro());
            if (o.destino() != null && !o.destino().isBlank()) {
                sb.append(", sentido ").append(legivel(o.destino()));
            }
            sb.append(", ").append(tempo(o.minutos()));
            if (o.acessivel()) {
                sb.append(", acessível");
            }
            sb.append(". ");
        }
        return sb.toString().trim();
    }

    static String tempo(int minutos) {
        if (minutos <= 0) {
            return "previsto para agora";
        }
        return minutos == 1 ? "previsto em 1 minuto" : "previsto em " + minutos + " minutos";
    }

    private static final java.util.regex.Pattern ROMANO =
            java.util.regex.Pattern.compile("m{0,3}(cm|cd|d?c{0,3})(xc|xl|l?x{0,3})(ix|iv|v?i{0,3})");
    private static final java.util.Set<String> NAO_ROMANOS = java.util.Set.of("di", "li", "mi", "vi", "cd", "mix", "dc", "civil");

    /** Versão pública de legivel, usada pelo assistente de tempo real. */
    public static String legivelPublico(String texto) {
        return legivel(texto);
    }

    static boolean romano(String palavra) {
        return palavra.length() >= 2 && !NAO_ROMANOS.contains(palavra) && ROMANO.matcher(palavra).matches();
    }

    /** Nomes da SPTrans vêm em CAIXA ALTA; a voz sintética lê melhor em caixa normal. */
    static String legivel(String texto) {
        String t = texto.trim();
        if (!t.equals(t.toUpperCase(Locale.ROOT)) || t.equals(t.toLowerCase(Locale.ROOT))) {
            return t;
        }
        StringBuilder sb = new StringBuilder();
        for (String palavra : t.toLowerCase(Locale.ROOT).split(" ")) {
            if (palavra.isEmpty()) {
                continue;
            }
            if (sb.length() > 0) {
                sb.append(' ');
            }
            if (romano(palavra)) {
                sb.append(palavra.toUpperCase(Locale.ROOT)); // "João XXIII", "D. Pedro II": a voz lê como número
                continue;
            }
            // Preposições curtas ficam minúsculas; abreviações com ponto ("D.", "Pq.") mantêm a maiúscula.
            boolean pequena = palavra.length() <= 2 && !palavra.matches(".*\\d.*") && !palavra.endsWith(".");
            sb.append(pequena && sb.length() > 0 ? palavra
                    : Character.toUpperCase(palavra.charAt(0)) + palavra.substring(1));
        }
        // "B/C" (bairro/centro) continua em maiúsculas depois da barra.
        return java.util.regex.Pattern.compile("/(\\p{L})").matcher(sb.toString())
                .replaceAll(m -> "/" + m.group(1).toUpperCase(Locale.ROOT));
    }
}

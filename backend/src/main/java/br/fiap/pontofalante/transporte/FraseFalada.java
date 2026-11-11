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
            boolean pequena = palavra.length() <= 2 && !palavra.matches(".*\\d.*");
            if (sb.length() > 0) {
                sb.append(' ');
            }
            sb.append(pequena && sb.length() > 0 ? palavra
                    : Character.toUpperCase(palavra.charAt(0)) + palavra.substring(1));
        }
        return sb.toString();
    }
}

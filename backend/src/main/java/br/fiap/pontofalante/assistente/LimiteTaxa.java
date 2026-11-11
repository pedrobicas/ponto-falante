package br.fiap.pontofalante.assistente;

import java.time.Duration;
import java.util.ArrayDeque;
import java.util.Deque;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/** Limite de requisições por chave (IP) em janela deslizante de 1 minuto, em memória. */
public class LimiteTaxa {
    private final int maximo;
    private final long janelaNanos = Duration.ofMinutes(1).toNanos();
    private final Map<String, Deque<Long>> acessos = new ConcurrentHashMap<>();

    public LimiteTaxa(int maximoPorMinuto) {
        this.maximo = maximoPorMinuto;
    }

    /** @return true se a requisição é permitida (e a registra); false se estourou o limite. */
    public boolean permitir(String chave) {
        return permitir(chave, System.nanoTime());
    }

    boolean permitir(String chave, long agora) {
        if (acessos.size() > 10_000) {
            acessos.values().removeIf(d -> synchronizedVazia(d, agora));
        }
        Deque<Long> fila = acessos.computeIfAbsent(chave, k -> new ArrayDeque<>());
        synchronized (fila) {
            while (!fila.isEmpty() && agora - fila.peekFirst() >= janelaNanos) {
                fila.pollFirst();
            }
            if (fila.size() >= maximo) {
                return false;
            }
            fila.addLast(agora);
            return true;
        }
    }

    private boolean synchronizedVazia(Deque<Long> fila, long agora) {
        synchronized (fila) {
            return fila.isEmpty() || agora - fila.peekLast() >= janelaNanos;
        }
    }
}

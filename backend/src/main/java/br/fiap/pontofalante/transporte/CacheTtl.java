package br.fiap.pontofalante.transporte;

import java.time.Duration;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.function.Supplier;

/** Cache simples em memória com validade. Só guarda resultados bem-sucedidos (exceções não são cacheadas). */
public class CacheTtl<V> {
    private record Entrada<V>(V valor, long expiraEmNanos) {
    }

    private final Map<String, Entrada<V>> mapa = new ConcurrentHashMap<>();
    private final long ttlNanos;
    private final int maximo;

    public CacheTtl(Duration ttl, int maximo) {
        this.ttlNanos = ttl.toNanos();
        this.maximo = maximo;
    }

    public V obter(String chave, Supplier<V> carregador) {
        long agora = System.nanoTime();
        Entrada<V> e = mapa.get(chave);
        if (e != null && agora - e.expiraEmNanos() < 0) {
            return e.valor();
        }
        V valor = carregador.get();
        if (mapa.size() >= maximo) {
            mapa.entrySet().removeIf(x -> agora - x.getValue().expiraEmNanos() >= 0);
            if (mapa.size() >= maximo) {
                mapa.clear();
            }
        }
        mapa.put(chave, new Entrada<>(valor, agora + ttlNanos));
        return valor;
    }

    public void limpar() {
        mapa.clear();
    }
}

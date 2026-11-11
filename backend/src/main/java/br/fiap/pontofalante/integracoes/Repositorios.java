package br.fiap.pontofalante.integracoes;

import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public final class Repositorios {
    private Repositorios() {
    }

    public interface DeteccaoVisaoRepository extends JpaRepository<DeteccaoVisao, Long> {
        List<DeteccaoVisao> findTop50ByPontoOrderByCapturadoEmDesc(long ponto);
    }

    public interface EventoDispositivoRepository extends JpaRepository<EventoDispositivo, Long> {
    }
}

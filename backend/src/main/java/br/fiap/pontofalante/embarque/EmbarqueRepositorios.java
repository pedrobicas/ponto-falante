package br.fiap.pontofalante.embarque;

import br.fiap.pontofalante.embarque.Entidades.ConferenciaVisao;
import br.fiap.pontofalante.embarque.Entidades.FavoritoEmbarque;
import br.fiap.pontofalante.embarque.Entidades.SessaoEmbarque;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;

import java.time.OffsetDateTime;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

public final class EmbarqueRepositorios {
    private EmbarqueRepositorios() {
    }

    public interface FavoritoEmbarqueRepository extends JpaRepository<FavoritoEmbarque, Long> {
        List<FavoritoEmbarque> findByDispositivoOrderByCriadoEmAsc(String dispositivo);

        Optional<FavoritoEmbarque> findByIdAndDispositivo(Long id, String dispositivo);

        long countByDispositivo(String dispositivo);

        @Modifying
        @Query("delete from FavoritoEmbarque f where f.dispositivo = ?1")
        int apagarDoDispositivo(String dispositivo);

        long countBySimuladoFalse();
    }

    public interface SessaoEmbarqueRepository extends JpaRepository<SessaoEmbarque, UUID> {
        Optional<SessaoEmbarque> findByIdAndDispositivo(UUID id, String dispositivo);

        Optional<SessaoEmbarque> findFirstByDispositivoAndEncerradaEmIsNullOrderByIniciadaEmDesc(String dispositivo);

        List<SessaoEmbarque> findByDispositivoAndEncerradaEmIsNull(String dispositivo);

        @Modifying
        @Query("delete from SessaoEmbarque s where s.dispositivo = ?1")
        int apagarDoDispositivo(String dispositivo);

        @Query("select count(s) from SessaoEmbarque s where s.simulado = false and s.iniciadaEm >= ?1")
        long contarReaisDesde(OffsetDateTime desde);

        @Query("select count(s) from SessaoEmbarque s where s.simulado = false and s.iniciadaEm >= ?1 and s.desfecho = ?2")
        long contarReaisComDesfechoDesde(OffsetDateTime desde, String desfecho);

        @Query("select avg(s.primeiraPrevisaoMin) from SessaoEmbarque s where s.simulado = false and s.iniciadaEm >= ?1 "
                + "and s.desfecho = 'EMBARQUEI' and s.primeiraPrevisaoMin is not null")
        Double mediaEsperaPrevistaDesde(OffsetDateTime desde);
    }

    public interface ConferenciaVisaoRepository extends JpaRepository<ConferenciaVisao, Long> {
        @Modifying
        @Query("delete from ConferenciaVisao c where c.dispositivo = ?1")
        int apagarDoDispositivo(String dispositivo);
    }
}

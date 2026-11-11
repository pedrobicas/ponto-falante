package br.fiap.pontofalante.rpa;

import org.springframework.data.jpa.repository.JpaRepository;

import java.time.LocalDate;
import java.util.List;
import java.util.Optional;

public interface BoletimRepository extends JpaRepository<Boletim, LocalDate> {
    Optional<Boletim> findFirstByOrderByDataReferenciaDesc();

    List<Boletim> findTop30ByOrderByDataReferenciaDesc();
}

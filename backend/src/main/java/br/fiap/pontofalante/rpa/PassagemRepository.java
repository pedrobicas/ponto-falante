package br.fiap.pontofalante.rpa;

import org.springframework.data.jpa.repository.JpaRepository;

import java.time.LocalDate;
import java.util.List;

public interface PassagemRepository extends JpaRepository<Passagem, Long> {
    List<Passagem> findByDataOrderByIdAsc(LocalDate data);

    boolean existsByData(LocalDate data);
}

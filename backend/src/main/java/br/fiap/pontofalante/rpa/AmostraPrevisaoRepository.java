package br.fiap.pontofalante.rpa;

import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.util.List;

public interface AmostraPrevisaoRepository extends JpaRepository<AmostraPrevisao, Long> {
    List<AmostraPrevisao> findByDataOrderByConsultadoEmAscPontoAsc(LocalDate data, Pageable pagina);

    boolean existsByPontoAndConsultadoEm(String ponto, OffsetDateTime consultadoEm);

    /** O índice único resolve também dois coletores concorrentes, sem abortar o lote. */
    @Modifying
    @Query(value = """
            INSERT INTO amostra_previsao
            (data, ponto, consultado_em, horario_referencia, fonte, tipo_registro,
             total_onibus, onibus, execucao_id, recebido_em)
            VALUES (:#{#a.data}, :#{#a.ponto}, :#{#a.consultadoEm}, :#{#a.horarioReferencia},
                    :#{#a.fonte}, :#{#a.tipoRegistro}, :#{#a.totalOnibus}, CAST(:#{#a.onibus} AS jsonb),
                    :#{#a.execucaoId}, :#{#a.recebidoEm})
            ON CONFLICT (ponto, consultado_em) DO NOTHING
            """, nativeQuery = true)
    int inserirSeAusente(@Param("a") AmostraPrevisao amostra);
}

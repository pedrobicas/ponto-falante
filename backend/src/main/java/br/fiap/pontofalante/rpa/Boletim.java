package br.fiap.pontofalante.rpa;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.time.LocalDate;
import java.time.OffsetDateTime;

/** Boletim publicado pelo robô RPA. O conteúdo fica em JSONB, exatamente como recebido. */
@Entity
@Table(name = "boletim")
public class Boletim {
    @Id
    @Column(name = "data_referencia")
    public LocalDate dataReferencia;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "conteudo", columnDefinition = "jsonb", nullable = false)
    public String conteudo;

    @Column(name = "desatualizado", nullable = false)
    public boolean desatualizado;

    @Column(name = "dados_simulados", nullable = false)
    public boolean dadosSimulados;

    @Column(name = "recebido_em", nullable = false)
    public OffsetDateTime recebidoEm;

    protected Boletim() {
    }

    public Boletim(LocalDate dataReferencia, String conteudo, boolean desatualizado, boolean dadosSimulados,
                   OffsetDateTime recebidoEm) {
        this.dataReferencia = dataReferencia;
        this.conteudo = conteudo;
        this.desatualizado = desatualizado;
        this.dadosSimulados = dadosSimulados;
        this.recebidoEm = recebidoEm;
    }
}

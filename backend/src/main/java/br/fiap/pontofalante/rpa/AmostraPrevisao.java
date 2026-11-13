package br.fiap.pontofalante.rpa;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.time.LocalDate;
import java.time.OffsetDateTime;

/**
 * Amostra real de previsão: o que a SPTrans previa para um ponto num instante, gravada pelo coletor do robô RPA.
 * Não é chegada observada. A lista de ônibus fica em JSONB, já normalizada e com o veículo anonimizado (hash).
 */
@Entity
@Table(name = "amostra_previsao")
public class AmostraPrevisao {
    public static final String FONTE = "olhovivo";
    public static final String TIPO = "AMOSTRA_PREVISAO";

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    public Long id;

    @Column(name = "data", nullable = false)
    public LocalDate data;

    @Column(name = "ponto", nullable = false)
    public String ponto;

    @Column(name = "consultado_em", nullable = false)
    public OffsetDateTime consultadoEm;

    @Column(name = "horario_referencia")
    public String horarioReferencia;

    @Column(name = "fonte", nullable = false)
    public String fonte;

    @Column(name = "tipo_registro", nullable = false)
    public String tipoRegistro;

    @Column(name = "total_onibus", nullable = false)
    public int totalOnibus;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "onibus", columnDefinition = "jsonb", nullable = false)
    public String onibus;

    @Column(name = "execucao_id")
    public String execucaoId;

    @Column(name = "recebido_em", nullable = false)
    public OffsetDateTime recebidoEm;

    protected AmostraPrevisao() {
    }

    public AmostraPrevisao(LocalDate data, String ponto, OffsetDateTime consultadoEm, String horarioReferencia,
                           int totalOnibus, String onibus, String execucaoId, OffsetDateTime recebidoEm) {
        this.data = data;
        this.ponto = ponto;
        this.consultadoEm = consultadoEm;
        this.horarioReferencia = horarioReferencia;
        this.fonte = FONTE;
        this.tipoRegistro = TIPO;
        this.totalOnibus = totalOnibus;
        this.onibus = onibus;
        this.execucaoId = execucaoId;
        this.recebidoEm = recebidoEm;
    }
}

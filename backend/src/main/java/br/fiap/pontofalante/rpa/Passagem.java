package br.fiap.pontofalante.rpa;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

import java.time.LocalDate;
import java.time.OffsetDateTime;

/** Passagem de ônibus registrada em um ponto (real ou simulada). Veículo sempre anonimizado. */
@Entity
@Table(name = "passagem")
public class Passagem {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    public Long id;

    @Column(name = "data", nullable = false)
    public LocalDate data;

    @Column(name = "ponto", nullable = false)
    public String ponto;

    @Column(name = "linha", nullable = false)
    public String linha;

    @Column(name = "sentido")
    public String sentido;

    @Column(name = "veiculo")
    public String veiculo;

    @Column(name = "programado_em")
    public String programadoEm;

    @Column(name = "previsto_em")
    public String previstoEm;

    @Column(name = "acessivel")
    public Boolean acessivel;

    @Column(name = "fonte", nullable = false)
    public String fonte;

    @Column(name = "tipo_registro", nullable = false)
    public String tipoRegistro;

    @Column(name = "atualizado_em", nullable = false)
    public OffsetDateTime atualizadoEm;

    protected Passagem() {
    }

    public Passagem(LocalDate data, String ponto, String linha, String sentido, String veiculo, String programadoEm,
                    String previstoEm, Boolean acessivel, String fonte, String tipoRegistro,
                    OffsetDateTime atualizadoEm) {
        this.data = data;
        this.ponto = ponto;
        this.linha = linha;
        this.sentido = sentido;
        this.veiculo = veiculo;
        this.programadoEm = programadoEm;
        this.previstoEm = previstoEm;
        this.acessivel = acessivel;
        this.fonte = fonte;
        this.tipoRegistro = tipoRegistro;
        this.atualizadoEm = atualizadoEm;
    }
}

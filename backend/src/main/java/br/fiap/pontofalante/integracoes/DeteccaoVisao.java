package br.fiap.pontofalante.integracoes;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

import java.time.OffsetDateTime;

@Entity
@Table(name = "deteccao_visao")
public class DeteccaoVisao {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    public Long id;

    @Column(name = "ponto", nullable = false)
    public long ponto;

    @Column(name = "linha_reconhecida")
    public String linhaReconhecida;

    @Column(name = "confianca", nullable = false)
    public double confianca;

    @Column(name = "capturado_em", nullable = false)
    public OffsetDateTime capturadoEm;

    @Column(name = "dispositivo", nullable = false)
    public String dispositivo;

    @Column(name = "recebido_em", nullable = false)
    public OffsetDateTime recebidoEm;

    protected DeteccaoVisao() {
    }

    public DeteccaoVisao(long ponto, String linhaReconhecida, double confianca, OffsetDateTime capturadoEm,
                         String dispositivo, OffsetDateTime recebidoEm) {
        this.ponto = ponto;
        this.linhaReconhecida = linhaReconhecida;
        this.confianca = confianca;
        this.capturadoEm = capturadoEm;
        this.dispositivo = dispositivo;
        this.recebidoEm = recebidoEm;
    }
}

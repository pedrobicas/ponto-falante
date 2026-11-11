package br.fiap.pontofalante.integracoes;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

import java.time.OffsetDateTime;

@Entity
@Table(name = "evento_dispositivo")
public class EventoDispositivo {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    public Long id;

    @Column(name = "dispositivo_id", nullable = false)
    public String dispositivoId;

    @Column(name = "ponto", nullable = false)
    public long ponto;

    @Column(name = "tipo", nullable = false)
    public String tipo;

    @Column(name = "ocorrido_em", nullable = false)
    public OffsetDateTime ocorridoEm;

    @Column(name = "bateria_pct")
    public Integer bateriaPct;

    @Column(name = "recebido_em", nullable = false)
    public OffsetDateTime recebidoEm;

    protected EventoDispositivo() {
    }

    public EventoDispositivo(String dispositivoId, long ponto, String tipo, OffsetDateTime ocorridoEm,
                             Integer bateriaPct, OffsetDateTime recebidoEm) {
        this.dispositivoId = dispositivoId;
        this.ponto = ponto;
        this.tipo = tipo;
        this.ocorridoEm = ocorridoEm;
        this.bateriaPct = bateriaPct;
        this.recebidoEm = recebidoEm;
    }
}

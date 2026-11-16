package br.fiap.pontofalante.embarque;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

/** Entidades do Embarque Assistido (tabelas da migração V3). */
public final class Entidades {
    private Entidades() {
    }

    /** Trajeto salvo: um ponto + uma linha (+ sentido). O passageiro escolhe pelo apelido ("Ir ao trabalho"). */
    @Entity(name = "FavoritoEmbarque")
    @Table(name = "embarque_favorito")
    public static class FavoritoEmbarque {
        @Id
        @GeneratedValue(strategy = GenerationType.IDENTITY)
        public Long id;
        @Column(name = "dispositivo", nullable = false)
        public String dispositivo;
        @Column(name = "ponto", nullable = false)
        public long ponto;
        @Column(name = "ponto_nome", nullable = false)
        public String pontoNome;
        @Column(name = "linha", nullable = false)
        public String linha;
        @Column(name = "sentido")
        public Integer sentido;
        @Column(name = "destino")
        public String destino;
        @Column(name = "apelido")
        public String apelido;
        @Column(name = "simulado", nullable = false)
        public boolean simulado;
        @Column(name = "criado_em", nullable = false)
        public OffsetDateTime criadoEm;

        protected FavoritoEmbarque() {
        }

        public FavoritoEmbarque(String dispositivo, long ponto, String pontoNome, String linha, Integer sentido,
                                String destino, String apelido, boolean simulado, OffsetDateTime criadoEm) {
            this.dispositivo = dispositivo;
            this.ponto = ponto;
            this.pontoNome = pontoNome;
            this.linha = linha;
            this.sentido = sentido;
            this.destino = destino;
            this.apelido = apelido;
            this.simulado = simulado;
            this.criadoEm = criadoEm;
        }
    }

    /** Um acompanhamento: do momento em que a pessoa escolhe o ônibus até embarcar, desistir ou expirar. */
    @Entity(name = "SessaoEmbarque")
    @Table(name = "embarque_sessao")
    public static class SessaoEmbarque {
        @Id
        public UUID id;
        @Column(name = "dispositivo", nullable = false)
        public String dispositivo;
        @Column(name = "ponto", nullable = false)
        public long ponto;
        @Column(name = "ponto_nome", nullable = false)
        public String pontoNome;
        /** Formato "875A-10:1;875C-10:0" (sentido 0 = qualquer sentido). Lido por {@link #escolhas()}. */
        @Column(name = "linhas", nullable = false)
        public String linhas;
        @Column(name = "simulado", nullable = false)
        public boolean simulado;
        @Column(name = "iniciada_em", nullable = false)
        public OffsetDateTime iniciadaEm;
        @Column(name = "encerrada_em")
        public OffsetDateTime encerradaEm;
        @Column(name = "desfecho")
        public String desfecho;
        @Column(name = "consultas", nullable = false)
        public int consultas;
        @Column(name = "consultas_com_falha", nullable = false)
        public int consultasComFalha;
        @Column(name = "primeira_previsao_min")
        public Integer primeiraPrevisaoMin;
        @Column(name = "ultima_previsao_min")
        public Integer ultimaPrevisaoMin;

        protected SessaoEmbarque() {
        }

        public SessaoEmbarque(UUID id, String dispositivo, long ponto, String pontoNome, List<EmbarqueDtos.LinhaEscolhida> escolhas,
                              boolean simulado, OffsetDateTime iniciadaEm) {
            this.id = id;
            this.dispositivo = dispositivo;
            this.ponto = ponto;
            this.pontoNome = pontoNome;
            this.linhas = codificar(escolhas);
            this.simulado = simulado;
            this.iniciadaEm = iniciadaEm;
        }

        public boolean aberta() {
            return encerradaEm == null;
        }

        public List<EmbarqueDtos.LinhaEscolhida> escolhas() {
            List<EmbarqueDtos.LinhaEscolhida> lista = new ArrayList<>();
            for (String parte : linhas.split(";")) {
                if (parte.isBlank()) continue;
                String[] p = parte.split(":", 2);
                int s = p.length > 1 ? Integer.parseInt(p[1]) : 0;
                lista.add(new EmbarqueDtos.LinhaEscolhida(p[0], s == 0 ? null : s, null));
            }
            return lista;
        }

        static String codificar(List<EmbarqueDtos.LinhaEscolhida> escolhas) {
            StringBuilder sb = new StringBuilder();
            for (EmbarqueDtos.LinhaEscolhida e : escolhas) {
                if (!sb.isEmpty()) sb.append(';');
                sb.append(e.letreiro()).append(':').append(e.sentido() == null ? 0 : e.sentido());
            }
            return sb.toString();
        }
    }

    /** Resultado de uma conferência do letreiro pela câmera. A imagem nunca é gravada. */
    @Entity(name = "ConferenciaVisao")
    @Table(name = "embarque_conferencia_visao")
    public static class ConferenciaVisao {
        @Id
        @GeneratedValue(strategy = GenerationType.IDENTITY)
        public Long id;
        @Column(name = "sessao")
        public UUID sessao;
        @Column(name = "dispositivo", nullable = false)
        public String dispositivo;
        @Column(name = "linha_esperada", nullable = false)
        public String linhaEsperada;
        @Column(name = "texto_lido")
        public String textoLido;
        @Column(name = "confianca")
        public Double confianca;
        @Column(name = "resultado", nullable = false)
        public String resultado;
        @Column(name = "modelo", nullable = false)
        public String modelo;
        @Column(name = "criado_em", nullable = false)
        public OffsetDateTime criadoEm;

        protected ConferenciaVisao() {
        }

        public ConferenciaVisao(UUID sessao, String dispositivo, String linhaEsperada, String textoLido, Double confianca,
                                String resultado, String modelo, OffsetDateTime criadoEm) {
            this.sessao = sessao;
            this.dispositivo = dispositivo;
            this.linhaEsperada = linhaEsperada;
            this.textoLido = textoLido;
            this.confianca = confianca;
            this.resultado = resultado;
            this.modelo = modelo;
            this.criadoEm = criadoEm;
        }
    }
}

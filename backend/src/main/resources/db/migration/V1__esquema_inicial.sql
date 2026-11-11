CREATE TABLE boletim (
    data_referencia DATE PRIMARY KEY,
    conteudo        JSONB       NOT NULL,
    desatualizado   BOOLEAN     NOT NULL DEFAULT FALSE,
    dados_simulados BOOLEAN     NOT NULL DEFAULT FALSE,
    recebido_em     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE passagem (
    id            BIGSERIAL PRIMARY KEY,
    data          DATE        NOT NULL,
    ponto         VARCHAR(40) NOT NULL,
    linha         VARCHAR(20) NOT NULL,
    sentido       VARCHAR(80),
    veiculo       VARCHAR(40),
    programado_em VARCHAR(5),
    previsto_em   VARCHAR(5),
    acessivel     BOOLEAN,
    fonte         VARCHAR(20) NOT NULL,
    tipo_registro VARCHAR(30) NOT NULL,
    atualizado_em TIMESTAMPTZ NOT NULL
);
CREATE INDEX idx_passagem_data ON passagem (data);

CREATE TABLE deteccao_visao (
    id                BIGSERIAL PRIMARY KEY,
    ponto             BIGINT           NOT NULL,
    linha_reconhecida VARCHAR(20)      NOT NULL,
    confianca         DOUBLE PRECISION NOT NULL,
    capturado_em      TIMESTAMPTZ      NOT NULL,
    dispositivo       VARCHAR(64)      NOT NULL,
    recebido_em       TIMESTAMPTZ      NOT NULL DEFAULT now()
);
CREATE INDEX idx_deteccao_ponto ON deteccao_visao (ponto, capturado_em DESC);

CREATE TABLE evento_dispositivo (
    id             BIGSERIAL PRIMARY KEY,
    dispositivo_id VARCHAR(64) NOT NULL,
    ponto          BIGINT      NOT NULL,
    tipo           VARCHAR(30) NOT NULL,
    ocorrido_em    TIMESTAMPTZ NOT NULL,
    bateria_pct    INTEGER,
    recebido_em    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_evento_dispositivo ON evento_dispositivo (dispositivo_id, ocorrido_em DESC);

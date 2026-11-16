-- Embarque Assistido: trajetos favoritos, sessões de acompanhamento e conferências do letreiro pela câmera.
-- Não há conta nem dado pessoal: o aparelho envia um identificador aleatório e o banco guarda só o hash salgado dele.
-- Localização e imagens nunca são gravadas.

CREATE TABLE embarque_favorito (
    id          BIGSERIAL PRIMARY KEY,
    dispositivo VARCHAR(64)  NOT NULL,                 -- SHA-256(sal + identificador aleatório do aparelho)
    ponto       BIGINT       NOT NULL,
    ponto_nome  VARCHAR(120) NOT NULL,
    linha       VARCHAR(12)  NOT NULL,                 -- letreiro, ex.: 875A-10
    sentido     INTEGER      CHECK (sentido IN (1, 2)),
    destino     VARCHAR(120),
    apelido     VARCHAR(40),
    simulado    BOOLEAN      NOT NULL DEFAULT FALSE,   -- favorito criado na demonstração
    criado_em   TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX uq_embarque_favorito
    ON embarque_favorito (dispositivo, ponto, linha, COALESCE(sentido, 0), simulado);

CREATE TABLE embarque_sessao (
    id                    UUID PRIMARY KEY,
    dispositivo           VARCHAR(64)  NOT NULL,
    ponto                 BIGINT       NOT NULL,
    ponto_nome            VARCHAR(120) NOT NULL,
    linhas                VARCHAR(80)  NOT NULL,       -- até 3 escolhas "LETREIRO:SENTIDO" separadas por ";" (sentido 0 = qualquer)
    simulado              BOOLEAN      NOT NULL DEFAULT FALSE,
    iniciada_em           TIMESTAMPTZ  NOT NULL,
    encerrada_em          TIMESTAMPTZ,
    desfecho              VARCHAR(20)  CHECK (desfecho IN ('EMBARQUEI', 'DESISTI', 'SUBSTITUIDA', 'EXPIRADA')),
    consultas             INTEGER      NOT NULL DEFAULT 0,
    consultas_com_falha   INTEGER      NOT NULL DEFAULT 0,
    primeira_previsao_min INTEGER,                     -- minutos previstos na primeira consulta com ônibus
    ultima_previsao_min   INTEGER
);
CREATE INDEX idx_embarque_sessao_dispositivo ON embarque_sessao (dispositivo, iniciada_em DESC);
CREATE INDEX idx_embarque_sessao_inicio ON embarque_sessao (iniciada_em);

CREATE TABLE embarque_conferencia_visao (
    id             BIGSERIAL PRIMARY KEY,
    sessao         UUID REFERENCES embarque_sessao (id) ON DELETE CASCADE,
    dispositivo    VARCHAR(64)      NOT NULL,
    linha_esperada VARCHAR(12)      NOT NULL,
    texto_lido     VARCHAR(40),
    confianca      DOUBLE PRECISION,
    resultado      VARCHAR(20)      NOT NULL CHECK (resultado IN ('CONFERE', 'NUMERO_CONFERE', 'NAO_CONFERE', 'INCONCLUSIVO')),
    modelo         VARCHAR(80)      NOT NULL,
    criado_em      TIMESTAMPTZ      NOT NULL DEFAULT now()
);
CREATE INDEX idx_embarque_conferencia_dispositivo ON embarque_conferencia_visao (dispositivo);

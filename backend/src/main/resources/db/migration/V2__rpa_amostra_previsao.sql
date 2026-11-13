-- Amostras REAIS de previsão coletadas pelo robô RPA: uma linha por consulta a um ponto monitorado.
-- Uma previsão não é chegada nem atraso medido; o boletim usa estas amostras para ESTIMAR a espera entre ônibus.
CREATE TABLE amostra_previsao (
    id                 BIGSERIAL PRIMARY KEY,
    data               DATE        NOT NULL,            -- data de consultado_em no fuso de São Paulo
    ponto              VARCHAR(40) NOT NULL,
    consultado_em      TIMESTAMPTZ NOT NULL,            -- quando o MVP consultou a SPTrans (segundos)
    horario_referencia VARCHAR(5),
    fonte              VARCHAR(20) NOT NULL,
    tipo_registro      VARCHAR(30) NOT NULL,
    total_onibus       INTEGER     NOT NULL,
    onibus             JSONB       NOT NULL,
    execucao_id        VARCHAR(64),
    recebido_em        TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uk_amostra_ponto_instante UNIQUE (ponto, consultado_em),
    -- Só dado real entra aqui: simulação nunca se mistura com as amostras da SPTrans.
    CONSTRAINT ck_amostra_fonte CHECK (fonte = 'olhovivo'),
    CONSTRAINT ck_amostra_tipo CHECK (tipo_registro = 'AMOSTRA_PREVISAO')
);
CREATE INDEX idx_amostra_previsao_data ON amostra_previsao (data, consultado_em);

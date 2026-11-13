"""Carrega a configuração do robô (YAML) e aplica variáveis de ambiente.

Segredos (RPA_API_KEY) NUNCA ficam no YAML nem no código: só no ambiente.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml


class ErroConfiguracao(Exception):
    """Configuração ausente ou inválida: o robô não deve rodar às cegas."""


@dataclass
class Regras:
    atraso_critico_min: float = 10
    atraso_atencao_min: float = 5
    intervalo_critico_min: float = 30
    intervalo_atencao_min: float = 20
    antecipacao_maxima_min: float = 60
    atraso_maximo_min: float = 180
    minimo_passagens: int = 3


@dataclass
class RegrasEstimadas:
    """Limites do boletim ESTIMADO (amostras reais de previsão). Não medem atraso: medem espera prevista."""
    espera_critica_min: float = 30       # espera típica prevista entre ônibus acima disso => CRÍTICA
    espera_atencao_min: float = 20       # espera típica acima disso (ou maior espera > crítica) => ATENÇÃO
    sem_previsao_atencao_pct: float = 50  # % de consultas sem ônibus previsto da linha => ATENÇÃO
    minimo_amostras: int = 3             # consultas com previsão da linha; abaixo disso => SEM_DADOS
    minutos_max_previsao: int = 120      # previsão além disso é descartada como incoerente
    cobertura_minima_pct: float = 50     # abaixo disso o boletim avisa "amostragem parcial"


@dataclass
class Coleta:
    pontos: list[str] = field(default_factory=list)   # códigos SPTrans conferidos em /api/pontos
    linhas: list[str] = field(default_factory=list)   # vazio = todas as linhas com amostras suficientes
    execucoes_por_dia: int = 8
    timeout_segundos: float = 45                      # o gateway da Prefeitura às vezes demora
    pasta_pendentes: Path = Path("saida/pendentes")


FALLBACKS = ("nunca", "somente_demo", "sempre")


@dataclass
class Config:
    base: Path                      # pasta raiz do projeto RPA
    mvp_url: str
    timeout: float
    tentativas: int
    backoff_inicial: float
    api_key: str | None
    gtfs_pasta: Path
    gtfs_pasta_ficticia: Path
    linhas: list[str] = field(default_factory=list)
    pontos: list[str] = field(default_factory=list)
    regras: Regras = field(default_factory=Regras)
    pasta_saida: Path = Path("saida")
    pasta_logs: Path = Path("logs")
    horario: str = "06:00"
    regras_estimadas: RegrasEstimadas = field(default_factory=RegrasEstimadas)
    coleta: Coleta = field(default_factory=Coleta)
    fallback_simulado: str = "somente_demo"


def carregar(caminho: str | Path) -> Config:
    caminho = Path(caminho).resolve()
    if not caminho.exists():
        raise ErroConfiguracao(f"Arquivo de configuração não encontrado: {caminho}")
    try:
        bruto = yaml.safe_load(caminho.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        raise ErroConfiguracao(f"YAML inválido: {e}") from e

    base = caminho.parent.parent  # config/ fica dentro da raiz do projeto
    mvp = bruto.get("mvp", {})
    gtfs = bruto.get("gtfs", {})
    mon = bruto.get("monitoramento", {}) or {}
    saida = bruto.get("saida", {})

    def abs_(p: str) -> Path:
        p = Path(p)
        return p if p.is_absolute() else base / p

    try:
        regras = Regras(**(bruto.get("regras") or {}))
    except TypeError as e:
        raise ErroConfiguracao(f"Regra desconhecida em 'regras': {e}") from e
    if regras.atraso_atencao_min > regras.atraso_critico_min or (
        regras.intervalo_atencao_min > regras.intervalo_critico_min
    ):
        raise ErroConfiguracao("Limite de ATENÇÃO não pode ser maior que o de CRÍTICA")

    try:
        regras_est = RegrasEstimadas(**(bruto.get("regras_estimadas") or {}))
    except TypeError as e:
        raise ErroConfiguracao(f"Regra desconhecida em 'regras_estimadas': {e}") from e
    if regras_est.espera_atencao_min > regras_est.espera_critica_min:
        raise ErroConfiguracao("Espera de ATENÇÃO não pode ser maior que a de CRÍTICA")
    col = bruto.get("coleta") or {}
    coleta = Coleta(
        pontos=[str(x) for x in (col.get("pontos") or [])],
        linhas=[str(x) for x in (col.get("linhas") or [])],
        execucoes_por_dia=int(col.get("execucoes_por_dia", 8)),
        timeout_segundos=float(col.get("timeout_segundos", 45)),
        pasta_pendentes=abs_(col.get("pasta_pendentes", "saida/pendentes")),
    )
    fallback = str((bruto.get("boletim") or {}).get("fallback_simulado", "somente_demo"))
    if fallback not in FALLBACKS:
        raise ErroConfiguracao(f"boletim.fallback_simulado deve ser um de {FALLBACKS}")

    return Config(
        base=base,
        mvp_url=os.environ.get("MVP_URL", mvp.get("url", "http://127.0.0.1:8080")).rstrip("/"),
        timeout=float(mvp.get("timeout_segundos", 10)),
        tentativas=int(mvp.get("tentativas", 3)),
        backoff_inicial=float(os.environ.get("RPA_BACKOFF", mvp.get("backoff_inicial_segundos", 2))),
        api_key=os.environ.get("RPA_API_KEY") or None,
        gtfs_pasta=abs_(gtfs.get("pasta", "data/gtfs_sptrans")),
        gtfs_pasta_ficticia=abs_(gtfs.get("pasta_ficticia", "data/gtfs_ficticio")),
        linhas=[str(x) for x in (mon.get("linhas") or [])],
        pontos=[str(x) for x in (mon.get("pontos") or [])],
        regras=regras,
        pasta_saida=abs_(saida.get("pasta", "saida")),
        pasta_logs=abs_(saida.get("pasta_logs", "logs")),
        horario=str((bruto.get("agendamento") or {}).get("horario", "06:00")),
        regras_estimadas=regras_est,
        coleta=coleta,
        fallback_simulado=fallback,
    )

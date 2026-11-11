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
    )

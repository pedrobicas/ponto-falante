"""Leitura da rede de ônibus (GTFS): quais linhas e pontos existem.

Usa o GTFS real da SPTrans se estiver na pasta configurada. Se faltar ou
estiver inválido, cai para a rede fictícia (5 linhas, 20 pontos) e AVISA:
nada de falha silenciosa.
"""
from __future__ import annotations

import csv
import logging
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger("pf_rpa.gtfs")


class GTFSInvalido(Exception):
    pass


@dataclass
class Rede:
    linhas: set[str]
    pontos: set[str]
    origem: str          # "gtfs_sptrans" ou "rede_ficticia"
    aviso: str | None = None


def _ler_csv(arquivo: Path, coluna_chave: str) -> set[str]:
    if not arquivo.exists():
        raise GTFSInvalido(f"arquivo ausente: {arquivo.name}")
    with arquivo.open(encoding="utf-8-sig", newline="") as f:
        leitor = csv.DictReader(f)
        if not leitor.fieldnames or coluna_chave not in leitor.fieldnames:
            raise GTFSInvalido(f"{arquivo.name} sem a coluna '{coluna_chave}'")
        valores = {(linha.get(coluna_chave) or "").strip() for linha in leitor}
    valores.discard("")
    if not valores:
        raise GTFSInvalido(f"{arquivo.name} está vazio")
    return valores


def ler_pasta(pasta: Path) -> tuple[set[str], set[str]]:
    # Na SPTrans, route_id tem o formato "8000-10", o mesmo usado pela API.
    linhas = _ler_csv(pasta / "routes.txt", "route_id")
    pontos = _ler_csv(pasta / "stops.txt", "stop_id")
    return linhas, pontos


def carregar_rede(pasta_real: Path, pasta_ficticia: Path) -> Rede:
    try:
        linhas, pontos = ler_pasta(pasta_real)
        log.info("GTFS real carregado: %d linhas, %d pontos", len(linhas), len(pontos))
        return Rede(linhas, pontos, "gtfs_sptrans")
    except GTFSInvalido as e:
        aviso = f"GTFS real indisponível ({e}); usando rede fictícia documentada"
        log.warning(aviso)
    # Fallback: se a fictícia também falhar, a exceção sobe (erro grave, sem silêncio).
    linhas, pontos = ler_pasta(pasta_ficticia)
    return Rede(linhas, pontos, "rede_ficticia", aviso)

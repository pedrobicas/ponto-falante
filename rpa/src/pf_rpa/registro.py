"""Logs e trilha de auditoria (etapa 7).

- logs/rpa_AAAA-MM-DD.log: linha a linha, com data/hora, nível e mensagem.
- logs/auditoria.jsonl: um resumo estruturado por execução (fácil de contar e provar).

Filtro de segurança: qualquer valor de RPA_API_KEY que apareça numa mensagem é
mascarado. Os registros não têm dado pessoal (o veículo já chega anonimizado).
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

FORMATO = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"


class MascararSegredos(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        segredo = os.environ.get("RPA_API_KEY")
        if segredo:
            msg = record.getMessage()
            if segredo in msg:
                record.msg = msg.replace(segredo, "***")
                record.args = ()
        return True


def configurar(pasta_logs: Path, hoje: str) -> Path:
    pasta_logs.mkdir(parents=True, exist_ok=True)
    arquivo = pasta_logs / f"rpa_{hoje}.log"
    raiz = logging.getLogger("pf_rpa")
    raiz.setLevel(logging.INFO)
    for h in list(raiz.handlers):
        raiz.removeHandler(h)
        h.close()
    for h in (logging.FileHandler(arquivo, encoding="utf-8"), logging.StreamHandler()):
        h.setFormatter(logging.Formatter(FORMATO, "%Y-%m-%d %H:%M:%S"))
        h.addFilter(MascararSegredos())
        raiz.addHandler(h)
    return arquivo


def auditar(pasta_logs: Path, resumo: dict[str, Any]) -> None:
    pasta_logs.mkdir(parents=True, exist_ok=True)
    resumo = {"registrado_em": datetime.now().astimezone().isoformat(timespec="seconds"), **resumo}
    with (pasta_logs / "auditoria.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(resumo, ensure_ascii=False) + "\n")

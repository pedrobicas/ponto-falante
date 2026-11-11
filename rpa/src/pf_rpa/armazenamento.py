"""Cópia local dos boletins (pasta saida/).

Serve para: (1) evidência/auditoria; (2) ter o "boletim anterior" quando o
MVP estiver fora; (3) não perder o boletim se a publicação falhar.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def salvar(pasta: Path, boletim: dict[str, Any]) -> Path:
    pasta.mkdir(parents=True, exist_ok=True)
    # Um boletim republicado como desatualizado não sobrescreve o original daquele dia.
    data_ref = boletim["data_referencia"] + ("_desatualizado" if boletim.get("desatualizado") else "")
    caminho = pasta / f"boletim_{data_ref}.json"
    caminho.write_text(json.dumps(boletim, ensure_ascii=False, indent=2), encoding="utf-8")
    (pasta / f"boletim_{data_ref}.html").write_text(
        "<!doctype html><html lang=\"pt-BR\"><meta charset=\"utf-8\">"
        "<title>Boletim de atrasos</title>"
        "<style>body{font:1.25rem/1.6 system-ui;background:#000;color:#fff;max-width:48rem;margin:auto;padding:1rem}"
        ".status-critica strong{color:#ff6b6b}.status-atencao strong{color:#ffd166}.status-ok strong{color:#7bed9f}"
        ".aviso{border:3px solid #ffd166;padding:.5rem}</style>"
        + boletim.get("html", "") + "</html>",
        encoding="utf-8",
    )
    (pasta / "boletim_ultimo.json").write_text(json.dumps(boletim, ensure_ascii=False, indent=2), encoding="utf-8")
    return caminho


def carregar_ultimo(pasta: Path) -> dict[str, Any] | None:
    caminho = pasta / "boletim_ultimo.json"
    if not caminho.exists():
        return None
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

"""Grava em UTF-8 as respostas reais do MVP publicado (status e assistente) como evidência da entrega.

    python scripts/integracao/coletar_evidencias_producao.py [--url https://ponto-falante.onrender.com]

Só chama endpoints públicos; não usa nem imprime chaves. Saída: docs/evidencias/assistente_producao_<data>.txt
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
PERGUNTAS = [
    ("tempo real, sem ponto", "Quando passa o próximo ônibus da linha 875A?"),
    ("tempo real, com ponto", "Quando passa a linha 875A no ponto Paulista?"),
    ("regra (base oficial)", "Tenho 66 anos. Preciso pagar a passagem de ônibus em São Paulo?"),
    ("regra (base oficial)", "Estudante paga meia no ônibus?"),
    ("fora da base", "Posso levar meu cachorro no ônibus em Curitiba?"),
]


def chamar(url: str, corpo: dict | None = None) -> tuple[int, dict, float]:
    dados = json.dumps(corpo).encode("utf-8") if corpo is not None else None
    req = urllib.request.Request(url, data=dados, method="POST" if dados else "GET",
                                 headers={"Content-Type": "application/json; charset=utf-8"})
    inicio = time.monotonic()
    # URL do próprio MVP passada pela linha de comando e restrita a http(s) em main(); nunca vem de dado externo.
    with urllib.request.urlopen(req, timeout=150) as r:  # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected
        return r.status, json.loads(r.read().decode("utf-8")), time.monotonic() - inicio


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="https://ponto-falante.onrender.com")
    args = ap.parse_args()
    base = args.url.rstrip("/")
    if not base.startswith(("https://", "http://127.0.0.1", "http://localhost")):
        raise SystemExit("Use https:// (ou http://127.0.0.1 / http://localhost para o MVP local).")
    agora = datetime.now(timezone.utc)
    linhas = [f"Evidência coletada em {agora.isoformat(timespec='seconds')} (UTC) contra {base}", ""]
    codigo, status, _ = chamar(base + "/api/status")
    linhas += [f"GET /api/status -> HTTP {codigo}", json.dumps(status, ensure_ascii=False), ""]
    for rotulo, pergunta in PERGUNTAS:
        codigo, resp, segundos = chamar(base + "/api/chat", {"pergunta": pergunta})
        fontes = "; ".join(f["documento"] for f in resp.get("fontes", [])) or "nenhuma"
        linhas += [f"[{rotulo}] {pergunta}",
                   f"  HTTP {codigo} em {segundos:.1f} s | origem={resp.get('origem')} | disponivel={resp.get('disponivel')}"
                   f" | nao_consta={resp.get('nao_consta')} | confianca={resp.get('confianca')}",
                   f"  resposta: {resp.get('resposta')}", f"  fontes: {fontes}", ""]
    destino = RAIZ / "docs" / "evidencias" / f"assistente_producao_{agora:%Y%m%d}.txt"
    destino.write_text("\n".join(linhas), encoding="utf-8")
    print(f"gravado {destino.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()

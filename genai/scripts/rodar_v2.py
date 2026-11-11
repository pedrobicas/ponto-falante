"""Experimento v2: roda configurações sobre um conjunto e grava avaliacao/v2/placar_<conjunto>.csv.

    python scripts/rodar_v2.py --conjunto dev --configs rag_v1 agente_v1 v2_3b
    python scripts/rodar_v2.py --conjunto teste_v2 --configs ...     # UMA vez, no fim

Mesmo índice e5-large, temperatura 0, semente 42 e mesmas perguntas para todas as configurações.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pf_genai import agente, agente_v2, avaliacao_v2 as av2, gerador  # noqa: E402
from pf_genai.agente_v2 import ConfigV2  # noqa: E402
from pf_genai.indice import Indice  # noqa: E402

CONFIGS = {
    # referências v1 (código original, medidas com a rubrica v2)
    "rag_v1": None,
    "agente_v1": None,
    # v2: ablações
    "v2_3b": ConfigV2("v2_3b"),
    "v2_3b_sem_verificador": ConfigV2("v2_3b_sem_verificador", modelo_verificador=None),
    "v2_3b_busca_densa": ConfigV2("v2_3b_busca_densa", busca_hibrida=False),
    "v2_3b_sem_reparo": ConfigV2("v2_3b_sem_reparo", reparo_recusa=False),
    "v2_7b": ConfigV2("v2_7b", modelo_gerador="qwen2.5:7b", modelo_verificador="qwen2.5:7b"),
    "v2_7b_sem_verificador": ConfigV2("v2_7b_sem_verificador", modelo_gerador="qwen2.5:7b", modelo_verificador=None),
    "v2_7b_ger_3b_ver": ConfigV2("v2_7b_ger_3b_ver", modelo_gerador="qwen2.5:7b", modelo_verificador="qwen2.5:3b"),
    "v2_qwen3_8b": ConfigV2("v2_qwen3_8b", modelo_gerador="qwen3:8b", modelo_verificador="qwen3:8b"),
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--conjunto", choices=list(av2.CONJUNTOS_V2), required=True)
    ap.add_argument("--configs", nargs="+", choices=list(CONFIGS), required=True)
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    perguntas = av2.carregar(args.conjunto)
    idx = Indice.carregar()
    caminho_csv = av2.PASTA_V2 / f"placar_{args.conjunto}.csv"
    existentes = {}
    if caminho_csv.exists():
        with caminho_csv.open(encoding="utf-8") as f:
            existentes = {r["configuracao"]: r for r in csv.DictReader(f)}
    for nome in args.configs:
        if nome == "rag_v1":
            f = lambda q: gerador.rag(q, idx)
        elif nome == "agente_v1":
            f = lambda q: agente.responder(q, idx)
        else:
            cfg = CONFIGS[nome]
            f = lambda q, cfg=cfg: agente_v2.responder(q, idx, cfg)
        linhas = av2.rodar(perguntas, f, nome, args.conjunto)
        for l in linhas:
            l["configuracao"] = nome
        r = av2.resumir(linhas)
        existentes[nome] = r
        print(json.dumps(r, ensure_ascii=False))
    campos = list(next(iter(existentes.values())).keys())
    with caminho_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        w.writerows(existentes.values())


if __name__ == "__main__":
    main()

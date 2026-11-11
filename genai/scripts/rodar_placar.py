"""Roda as 3 configurações sobre um conjunto de perguntas e grava avaliacao/placar_<conjunto>.csv.

    python scripts/rodar_placar.py --conjunto dev            # desenvolvimento (ajustes)
    python scripts/rodar_placar.py --conjunto teste          # avaliação final (rodar uma vez)
    python scripts/rodar_placar.py --conjunto dev --so agente

As três configurações usam o MESMO modelo (qwen2.5:3b), a mesma temperatura (0), a mesma
semente (42), o mesmo índice, o mesmo limiar e as mesmas perguntas: só muda a estratégia.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pf_genai import AVALIACAO, agente, avaliacao as av, gerador  # noqa: E402
from pf_genai.indice import Indice  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--conjunto", choices=["dev", "teste"], required=True)
    ap.add_argument("--so", choices=["sem_contexto", "rag", "agente"])
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    perguntas = av.carregar_perguntas(args.conjunto)
    idx = Indice.carregar()
    configs = {
        "sem_contexto": gerador.sem_contexto,
        "rag": lambda q: gerador.rag(q, idx),
        "agente": lambda q: agente.responder(q, idx),
    }
    resumos = []
    for nome, f in configs.items():
        caminho = AVALIACAO / f"resultados_{args.conjunto}_{nome}.jsonl"
        if args.so and nome != args.so:
            if caminho.exists():
                linhas = [json.loads(l) for l in caminho.open(encoding="utf-8")]
                resumos.append(av.resumir(linhas))
            continue
        resumos.append(av.resumir(av.rodar(perguntas, f, nome, conjunto=args.conjunto)))
    with (AVALIACAO / f"placar_{args.conjunto}.csv").open("w", encoding="utf-8", newline="") as fp:
        w = csv.DictWriter(fp, fieldnames=list(resumos[0].keys()))
        w.writeheader()
        w.writerows(resumos)
    for r in resumos:
        print(r)


if __name__ == "__main__":
    main()

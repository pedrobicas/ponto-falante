"""Diagnóstico/ablação da BUSCA no DEV v3 (sem LLM): recall@1/3/5, cobertura@3 e separação "respondível ×
não consta" pelo melhor score. Só usa o DEV (avaliacao/v3/perguntas_dev_v3.jsonl); o teste v3 nunca é lido aqui.

    python scripts/diagnostico_busca_v3.py            # grava avaliacao/v3/busca_dev_v3.csv e limiar_dev_v3.csv
"""
from __future__ import annotations

import csv
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pf_genai import AVALIACAO  # noqa: E402
from pf_genai.agente_v2 import buscar_hibrido  # noqa: E402
from pf_genai.busca_v3 import IndiceV3  # noqa: E402
from pf_genai.indice import Indice  # noqa: E402

PASTA = AVALIACAO / "v3"
DEV = PASTA / "perguntas_dev_v3.jsonl"


def carregar(caminho: Path) -> list[dict]:
    return [json.loads(l) for l in caminho.read_text(encoding="utf-8").splitlines() if l.strip()]


def acertos(ids_v1_por_pos: list[set[str]], grupos: list[list[str]], k: int) -> tuple[bool, bool]:
    vistos = set().union(*ids_v1_por_pos[:k]) if ids_v1_por_pos[:k] else set()
    todos = {t for g in grupos for t in g}
    return bool(vistos & todos), all(vistos & set(g) for g in grupos)


def auc(pos: list[float], neg: list[float]) -> float:
    pares = [(p > n) + 0.5 * (p == n) for p in pos for n in neg]
    return sum(pares) / len(pares) if pares else float("nan")


def melhor_limiar(pos: list[float], neg: list[float]) -> tuple[float, float, float, float]:
    """Menor limiar com a maior acurácia balanceada (mesmo critério do notebook 02 da v1)."""
    melhor = (0.0, -1.0, 0.0, 0.0)
    for t in sorted(set(pos + neg)):
        tpr = sum(p >= t for p in pos) / len(pos)
        tnr = sum(n < t for n in neg) / len(neg)
        ba = (tpr + tnr) / 2
        if ba > melhor[1] + 1e-9:
            melhor = (t, ba, tpr, tnr)
    return melhor


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    perguntas = carregar(DEV)
    resp = [p for p in perguntas if p["evidencias"]]
    neg = [p for p in perguntas if p["nao_consta"]]
    idx1 = Indice.carregar()
    idx3 = IndiceV3.carregar_ou_criar()

    def v1_densa(q):
        a = idx1.buscar(q, 5)
        return [{x.trecho.trecho_id} for x in a], a[0].score

    def v1_hibrida(q):
        a = buscar_hibrido(idx1, [q], 5, hibrida=True)
        return [{t.trecho_id} for t, _, _ in a], max(c for _, _, c in a)

    def v3(**kw):
        def f(q):
            a = idx3.buscar(q, 5, **kw)
            return [set(x.trecho.ids_v1) for x in a], a[0].score
        return f

    configs = {
        "A_v1_densa (base v1)": v1_densa,
        "B_v1_hibrida_cosseno (v2)": v1_hibrida,
        "C_v3_trechos_densa": v3(expansao=False, hibrida=False, rerank=False),
        "D_v3_trechos_hibrida": v3(expansao=False, hibrida=True, rerank=False),
        "E_v3_hibrida_expansao": v3(expansao=True, hibrida=True, rerank=False),
        "F_v3_hibrida_rerank": v3(expansao=False, hibrida=True, rerank=True),
        "G_v3_hibrida_expansao_rerank": v3(expansao=True, hibrida=True, rerank=True),
    }
    linhas, limiares = [], []
    for nome, f in configs.items():
        t0 = time.perf_counter()
        r1 = r3 = r5 = c3 = 0
        falhas3 = []
        for p in resp:
            ids, _ = f(p["pergunta"])
            a1, _ = acertos(ids, p["evidencias"], 1)
            a3, cov3 = acertos(ids, p["evidencias"], 3)
            a5, _ = acertos(ids, p["evidencias"], 5)
            r1 += a1; r3 += a3; r5 += a5; c3 += cov3
            if not a3:
                falhas3.append(p["id"])
        pos_sc = [f(p["pergunta"])[1] for p in resp if not p.get("aceita_esclarecimento")]
        neg_sc = [f(p["pergunta"])[1] for p in neg]
        dt = (time.perf_counter() - t0) / (len(resp) + len(pos_sc) + len(neg_sc))
        lim, ba, tpr, tnr = melhor_limiar(pos_sc, neg_sc)
        n = len(resp)
        linhas.append({"configuracao": nome, "n_respondiveis": n, "recall@1": round(r1 / n, 3),
                       "recall@3": round(r3 / n, 3), "recall@5": round(r5 / n, 3), "cobertura@3": round(c3 / n, 3),
                       "auc_respondivel_x_nao_consta": round(auc(pos_sc, neg_sc), 3),
                       "latencia_media_s": round(dt, 3), "falhas_top3": " ".join(falhas3)})
        limiares.append({"configuracao": nome, "limiar": round(lim, 4), "acuracia_balanceada": round(ba, 3),
                         "respondiveis_que_passam": round(tpr, 3), "nao_consta_barradas": round(tnr, 3),
                         "mediana_respondiveis": round(statistics.median(pos_sc), 4),
                         "mediana_nao_consta": round(statistics.median(neg_sc), 4)})
        print(json.dumps(linhas[-1], ensure_ascii=False))
        print("   ", json.dumps(limiares[-1], ensure_ascii=False))
    for nome_arq, dados in (("busca_dev_v3.csv", linhas), ("limiar_dev_v3.csv", limiares)):
        with (PASTA / nome_arq).open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(dados[0]))
            w.writeheader()
            w.writerows(dados)


if __name__ == "__main__":
    main()

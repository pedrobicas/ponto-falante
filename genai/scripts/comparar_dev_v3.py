"""Compara resultados previamente gravados sob A MESMA rubrica v3.1, sem chamar Ollama.

Somente desenvolvimento. Compara IDs comuns e informa o tamanho da amostra.
Não abre, interpreta nem modifica o teste final fechado.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from pf_genai import avaliacao_v3 as av3  # noqa: E402


def ler(path: Path) -> list[dict]:
    linhas = [json.loads(s) for s in path.read_text(encoding="utf-8").splitlines() if s.strip()]
    ids = [x["id"] for x in linhas]
    if len(ids) != len(set(ids)):
        raise ValueError(f"IDs repetidos: {path}")
    return linhas


def reclassificar(pergunta: dict, linha: dict) -> dict:
    if linha.get("nao_consta_esperado") != pergunta["nao_consta"]:
        raise ValueError(f"Rótulo de não consta divergente: {pergunta['id']}")
    resposta = linha.get("resposta")
    fontes = [SimpleNamespace(trecho_id=x) for x in linha.get("fontes", [])]
    # Todos os atributos usados pelo avaliador são reproduzidos a partir da saída gravada.
    pseudo_resposta = (SimpleNamespace(resposta=resposta, fontes=fontes,
                                     confianca=linha.get("confianca")) if resposta else None)
    pseudo_resultado = SimpleNamespace(
        resposta=pseudo_resposta,
        json_valido=linha.get("categoria") != "falha_operacional",
        ids_v1_citados=linha.get("fontes_v1", []),
        intencao=linha.get("intencao_prevista"),
        configuracao=linha.get("configuracao"),
        recuperados=linha.get("recuperados", []), scores=linha.get("scores", []),
        latencia_ms=linha.get("latencia_ms", 0), passos=linha.get("passos", []),
        erro=linha.get("erro"),
    )
    return av3.avaliar(pergunta, pseudo_resultado)


def avaliar_pareado(antigo: Path, novo: Path) -> tuple[list[dict], list[dict], list[dict]]:
    ps = {p["id"]: p for p in av3.carregar("dev_v3")}
    x, y = ler(antigo), ler(novo)
    if any(r["id"] not in ps for r in x + y):
        raise ValueError("IDs não pertencentes ao DEV v3")
    map_x, map_y = {r["id"]: r for r in x}, {r["id"]: r for r in y}
    ids = [p for p in ps if p in map_x and p in map_y]
    if not ids:
        raise ValueError("Nenhuma pergunta em comum")
    a = [reclassificar(ps[k], map_x[k]) for k in ids]
    b = [reclassificar(ps[k], map_y[k]) for k in ids]
    ambos = [{"id": k, "antes": a[i]["categoria"], "depois": b[i]["categoria"]}
             for i, k in enumerate(ids)]
    return a, b, ambos


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--antigo", type=Path, required=True)
    ap.add_argument("--novo", type=Path, required=True)
    ap.add_argument("--saida", type=Path, required=True)
    args = ap.parse_args()
    a, b, ambos = avaliar_pareado(args.antigo, args.novo)
    total = len(ambos)
    categorias_acerto = {"correto", "recusa_correta"}
    ca = sum(r["categoria"] in categorias_acerto for r in a)
    cb = sum(r["categoria"] in categorias_acerto for r in b)
    melhora = sum(x["antes"] not in categorias_acerto and x["depois"] in categorias_acerto for x in ambos)
    piora = sum(x["antes"] in categorias_acerto and x["depois"] not in categorias_acerto for x in ambos)
    resumo = {
        "rubrica": av3.RUBRICA_VERSAO,
        "amostra_pareada": total,
        "total_dev": len(av3.carregar("dev_v3")),
        "acertos_antigos": ca,
        "acertos_novos": cb,
        "acuracia_antiga_pareada": round(100 * ca / total, 2),
        "acuracia_nova_pareada": round(100 * cb / total, 2),
        "melhoraram": melhora, "pioraram": piora,
        "categorias_antigas": dict(Counter(x["categoria"] for x in a)),
        "categorias_novas": dict(Counter(x["categoria"] for x in b)),
        "observacao": "Comparação retrospectiva apenas dos IDs comuns no DEV, não é resultado do teste final."
    }
    args.saida.parent.mkdir(parents=True, exist_ok=True)
    args.saida.write_text(json.dumps({"resumo": resumo, "por_pergunta": ambos},
                                    indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(resumo, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

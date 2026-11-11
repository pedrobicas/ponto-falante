"""Avaliação: recall da busca, escolha do limiar e placar das 3 configurações.

Gabarito (avaliacao/perguntas.jsonl), uma pergunta por linha:
  {"id": "q01", "pergunta": "...", "categoria": "idoso", "nao_consta": false,
   "trechos_esperados": ["lei-10741-transporte-002"],
   "fatos": [["65 anos", "sessenta e cinco"], ["gratuit"]],   # cada grupo: pelo menos 1 variação deve aparecer
   "resposta_referencia": "..."}

Critérios (determinísticos, para qualquer um reproduzir):
- ACERTO: pergunta respondível -> não recusou e todos os grupos de fatos aparecem;
          pergunta "não consta"  -> recusou (nao_consta=true).
- ALUCINAÇÃO: respondeu algo que não está certo. Ou seja, respondeu (sem recusar) uma
          pergunta "não consta", ou respondeu uma respondível sem os fatos do gabarito.
- RECUSA INDEVIDA: recusou uma pergunta que a base responde (erro "seguro").
- CITAÇÃO CORRETA: entre as respondíveis respondidas, citou ao menos um trecho esperado.
"""
from __future__ import annotations

import json
import statistics
import unicodedata
from dataclasses import asdict
from pathlib import Path
from typing import Callable

from functools import lru_cache

from . import AVALIACAO
from .agente import numeros_sem_suporte
from .gerador import Resultado
from .indice import Indice
from .trechos import carregar as carregar_trechos


CONJUNTOS = {"teste": AVALIACAO / "perguntas.jsonl",        # avaliação final: rodado uma vez, sem ajustes
             "dev": AVALIACAO / "perguntas_dev.jsonl"}       # desenvolvimento: usado para todas as escolhas


@lru_cache(maxsize=1)
def _textos_base() -> dict[str, str]:
    return {t.trecho_id: f"{t.documento}. {t.texto}" for t in carregar_trechos()}


def carregar_perguntas(caminho: Path | str = CONJUNTOS["teste"]) -> list[dict]:
    caminho = CONJUNTOS.get(caminho, caminho) if isinstance(caminho, str) else caminho
    with caminho.open(encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def normalizar(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower())
    return "".join(c for c in s if not unicodedata.combining(c))


_RECUSA = ("nao encontrei", "nao sei", "nao consta", "nao tenho essa informacao", "nao tenho informac",
           "nao possuo", "nao ha informac", "nao foi possivel encontrar", "nao disponho")


def eh_recusa(resp) -> bool:
    """Recusa = o que a pessoa OUVE é uma recusa. Se nao_consta=true mas o texto afirma algo
    (ex.: 'o último ônibus sai às 23h'), contamos como resposta: é isso que seria lido em voz alta."""
    if resp is None:
        return True
    texto = normalizar(resp.resposta)
    return any(r in texto for r in _RECUSA) or (resp.nao_consta and len(texto) < 20)


def fatos_ok(resposta: str, fatos: list[list[str]]) -> bool:
    r = normalizar(resposta)
    return all(any(normalizar(v) in r for v in grupo) for grupo in fatos)


# ---------- Busca ----------
def recall_at_k(indice: Indice, perguntas: list[dict], ks=(1, 3)) -> dict:
    respondiveis = [p for p in perguntas if not p["nao_consta"]]
    acertos = {k: 0 for k in ks}
    detalhes = []
    for p in respondiveis:
        achados = indice.buscar(p["pergunta"], max(ks))
        ids = [a.trecho.trecho_id for a in achados]
        for k in ks:
            if set(ids[:k]) & set(p["trechos_esperados"]):
                acertos[k] += 1
        detalhes.append({"id": p["id"], "top": ids, "score_top1": round(achados[0].score, 4),
                         "esperados": p["trechos_esperados"]})
    return {f"recall@{k}": round(acertos[k] / len(respondiveis), 3) for k in ks} | {"detalhes": detalhes}


def curva_limiar(indice: Indice, perguntas: list[dict], limiares=None) -> list[dict]:
    """Para cada limiar: % de respondíveis que passam e % de "não consta" barradas."""
    limiares = limiares or [round(0.20 + 0.025 * i, 3) for i in range(25)]
    top1 = [(p["nao_consta"], indice.buscar(p["pergunta"], 1)[0].score) for p in perguntas]
    resp = [s for nc, s in top1 if not nc]
    nao = [s for nc, s in top1 if nc]
    linhas = []
    for t in limiares:
        passa = sum(s >= t for s in resp) / len(resp)
        barra = sum(s < t for s in nao) / len(nao)
        linhas.append({"limiar": t, "respondiveis_passam": round(passa, 3),
                       "nao_consta_barradas": round(barra, 3),
                       "acuracia_balanceada": round((passa + barra) / 2, 3)})
    return linhas


# ---------- Placar ----------
def avaliar_resposta(p: dict, r: Resultado) -> dict:
    resp = r.resposta
    recusou = eh_recusa(resp)
    texto = resp.resposta if resp else ""
    flag_inconsistente = bool(resp and resp.nao_consta and not recusou)
    if p["nao_consta"]:
        acerto = recusou
        alucinacao = not recusou
        recusa_indevida = False
        citacao = None
    else:
        acerto = (not recusou) and fatos_ok(texto, p["fatos"])
        alucinacao = (not recusou) and not acerto
        recusa_indevida = recusou
        citados = {f.trecho_id for f in resp.fontes} if resp else set()
        citacao = (bool(citados & set(p["trechos_esperados"])) if not recusou else None)
    # Fundamentação e citações (só faz sentido quando houve resposta afirmativa)
    citados_lista = [f.trecho_id for f in resp.fontes] if (resp and not recusou) else []
    validos = [c for c in citados_lista if c in _textos_base()]
    sem_fund = None
    if not recusou:
        textos = [_textos_base()[c] for c in validos]
        sem_fund = (not validos) or bool(numeros_sem_suporte(texto, textos, p["pergunta"]))
    return {
        "id": p["id"], "categoria": p.get("categoria"), "nao_consta_esperado": p["nao_consta"],
        "configuracao": r.configuracao, "acerto": acerto, "alucinacao": alucinacao,
        "recusa_indevida": recusa_indevida, "citacao_correta": citacao, "json_valido": r.json_valido,
        "flag_inconsistente": flag_inconsistente,
        "sem_fundamentacao": sem_fund,
        "citacoes": len(citados_lista), "citacoes_validas": len(validos),
        "citacoes_esperadas": (len(set(citados_lista) & set(p["trechos_esperados"])) if not p["nao_consta"] else 0),
        "resposta": texto, "fontes": [f.trecho_id for f in resp.fontes] if resp else [],
        "confianca": resp.confianca if resp else None, "erro": r.erro,
        "recuperados": r.recuperados, "scores": r.scores, "latencia_ms": r.latencia_ms, "passos": r.passos,
    }


def rodar(perguntas: list[dict], responder: Callable[[str], Resultado], nome: str,
          pasta: Path = AVALIACAO, progresso: bool = True, conjunto: str = "teste") -> list[dict]:
    linhas = []
    for i, p in enumerate(perguntas, 1):
        linhas.append(avaliar_resposta(p, responder(p["pergunta"])))
        if progresso:
            print(f"\r{nome}: {i}/{len(perguntas)}", end="", flush=True)
    if progresso:
        print()
    with (pasta / f"resultados_{conjunto}_{nome}.jsonl").open("w", encoding="utf-8") as f:
        for l in linhas:
            f.write(json.dumps(l, ensure_ascii=False) + "\n")
    return linhas


def _razao(linhas: list[dict], num: str, den: str) -> float:
    d = sum(l.get(den, 0) for l in linhas)
    return round(100 * sum(l.get(num, 0) for l in linhas) / d, 1) if d else 0.0


def resumir(linhas: list[dict]) -> dict:
    n = len(linhas)
    resp = [l for l in linhas if not l["nao_consta_esperado"]]
    nc = [l for l in linhas if l["nao_consta_esperado"]]
    cit = [l["citacao_correta"] for l in resp if l["citacao_correta"] is not None]
    pct = lambda xs: round(100 * sum(xs) / len(xs), 1) if xs else 0.0
    return {
        "configuracao": linhas[0]["configuracao"],
        "acerto_total_%": pct([l["acerto"] for l in linhas]),
        "acerto_respondiveis_%": pct([l["acerto"] for l in resp]),
        "recusa_correta_nao_consta_%": pct([l["acerto"] for l in nc]),
        "alucinacao_%": pct([l["alucinacao"] for l in linhas]),
        "recusa_indevida_%": pct([l["recusa_indevida"] for l in resp]),
        "citacao_correta_%": pct(cit),
        "sem_fundamentacao_%": pct([l["sem_fundamentacao"] for l in linhas if l.get("sem_fundamentacao") is not None]),
        "citacoes_validas_%": _razao(linhas, "citacoes_validas", "citacoes"),
        "precisao_citacoes_%": _razao(resp, "citacoes_esperadas", "citacoes"),
        "json_valido_%": pct([l["json_valido"] for l in linhas]),
        "nao_consta_incoerente_%": pct([l.get("flag_inconsistente", False) for l in linhas]),
        "latencia_media_s": round(statistics.mean(l["latencia_ms"] for l in linhas) / 1000, 2),
        "n": n,
    }

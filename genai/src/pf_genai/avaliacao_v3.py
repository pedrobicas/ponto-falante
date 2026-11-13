"""Avaliação v3: rubrica v2 (avaliacao_v2.py, inalterada) + os tipos novos do DEV/teste v3.

Acréscimos em relação à v2 (tudo escrito ANTES de rodar qualquer configuração no DEV v3):
- intencao "tempo_real": correto = recusar/encaminhar (não inventar horário). Se a configuração devolve o
  campo `intencao`, medimos também a acurácia da classificação (só a v3 devolve).
- "aceita_esclarecimento": em pergunta ambígua, uma pergunta de volta à pessoa ("Você tem 60 a 64 anos ou
  65 ou mais?") conta como correta, desde que não afirme nada proibido.
- "aceita_recusa": em pergunta com injeção, recusar também é correto.
- Frases de recusa novas ("não consigo informar", "não posso") reconhecidas como recusa.
- Latência: média, mediana e p90.

Revisão da rubrica em 12/11/2026 (v3.1), antes do teste fechado:
- Afirmações proibidas prevalecem sobre uma recusa aceita.
- Menções a previsão/horário não são, sozinhas, uma recusa.
- Cobertura de todos os grupos de evidência é medida separada da pertinência.
Comparações devem reclassificar as mesmas saídas com esta versão da rubrica.
"""
from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import Callable

from . import AVALIACAO
from . import avaliacao_v2 as av2

PASTA_V3 = AVALIACAO / "v3"
RUBRICA_VERSAO = "v3.1"
CONJUNTOS_V3 = {
    "dev_v3": PASTA_V3 / "perguntas_dev_v3.jsonl",        # todos os ajustes
    "teste_v3": PASTA_V3 / "perguntas_teste_v3.jsonl",    # congelado; rodado UMA vez no fim
}

_RECUSA_EXTRA = ("nao consigo informar", "nao posso informar", "nao posso responder", "nao consigo responder",
                 "nao posso ajudar", "nao posso fazer", "nao posso revelar", "nao posso mostrar",
                 )


def carregar(conjunto: str | Path) -> list[dict]:
    caminho = CONJUNTOS_V3.get(conjunto, conjunto) if isinstance(conjunto, str) else conjunto
    with Path(caminho).open(encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def eh_recusa(texto: str | None) -> bool:
    if not texto:
        return False
    if av2.eh_recusa(texto, None):
        return True
    t = av2.normalizar(texto)
    numeros = [n for n in av2._NUM.findall(t) if n != "156"]
    return any(r in t for r in _RECUSA_EXTRA) and not numeros and len(t) < 300


def eh_esclarecimento(texto: str | None) -> bool:
    """Pergunta de volta curta, sem números (ex.: 'Você tem entre 60 e 64 anos ou 65 ou mais?')."""
    if not texto:
        return False
    t = av2.normalizar(texto).strip()
    return t.endswith("?") and len(t) < 260 and not any(n for n in av2._NUM.findall(t) if n not in ("60", "64", "65", "156"))


def classificar(p: dict, texto: str | None, falhou: bool, citados: list[str]) -> dict:
    if falhou or texto is None or not texto.strip():
        return {"categoria": "falha_operacional", "faltando": [], "proibidas": []}
    proibidas = [a for a in p.get("afirmacoes_proibidas", []) if av2.encontra(texto, a)[0]]
    recusou = eh_recusa(texto)
    if p["nao_consta"]:
        if recusou and not proibidas:
            return {"categoria": "recusa_correta", "faltando": [], "proibidas": []}
        return {"categoria": "resposta_indevida", "faltando": [], "proibidas": proibidas}
    if proibidas:
        return {"categoria": "erro_factual", "faltando": [], "proibidas": proibidas}
    if recusou:
        if p.get("aceita_recusa"):
            return {"categoria": "correto", "faltando": [], "proibidas": [], "obs": "recusa aceita (injeção)"}
        return {"categoria": "recusa_indevida", "faltando": [], "proibidas": []}
    if p.get("aceita_esclarecimento") and eh_esclarecimento(texto) and not proibidas:
        return {"categoria": "correto", "faltando": [], "proibidas": [], "obs": "pediu esclarecimento"}
    return av2.classificar(p, texto, False, citados)


def avaliar(p: dict, r) -> dict:
    resp = r.resposta
    texto = resp.resposta if resp else None
    citados = [f.trecho_id for f in resp.fontes] if resp else []
    c = classificar(p, texto, (resp is None) or (not r.json_valido), citados)
    respondeu = c["categoria"] in ("correto", "incompleto", "erro_factual", "sem_fato", "resposta_indevida") \
        and c.get("obs") not in ("pediu esclarecimento", "recusa aceita (injeção)")
    ids_v1 = getattr(r, "ids_v1_citados", None) or citados
    grupos = [set(g) for g in p.get("evidencias", [])]
    pertinente = cobertura = None
    if respondeu and not p["nao_consta"] and grupos:
        pertinente = any(set(ids_v1) & g for g in grupos)
        cobertura = all(set(ids_v1) & g for g in grupos)
    intencao = getattr(r, "intencao", None)
    return {
        "id": p["id"], "rubrica_versao": RUBRICA_VERSAO,
        "categoria_pergunta": p.get("categoria"), "tipo": p.get("tipo"),
        "intencao_esperada": p.get("intencao"), "intencao_prevista": intencao,
        "nao_consta_esperado": p["nao_consta"], "configuracao": r.configuracao, **c, "respondeu": respondeu,
        "sem_citacao": (respondeu and not citados), "citacao_pertinente": pertinente,
        "cobertura_evidencias": cobertura,
        "resposta": texto, "fontes": citados, "fontes_v1": ids_v1, "confianca": resp.confianca if resp else None,
        "recuperados": r.recuperados, "scores": r.scores, "latencia_ms": r.latencia_ms,
        "passos": r.passos, "erro": r.erro,
    }


def rodar(perguntas: list[dict], responder: Callable, nome: str, conjunto: str, pasta: Path = PASTA_V3,
          progresso: bool = True) -> list[dict]:
    linhas = []
    pasta.mkdir(parents=True, exist_ok=True)
    # Persistência por pergunta: uma interrupção não apaga a evidência já medida.
    # Nunca sobrescreve uma rodada anterior; o runner cria diretório próprio.
    with (pasta / f"resultados_{conjunto}_{nome}.jsonl").open("x", encoding="utf-8") as f:
        for i, p in enumerate(perguntas, 1):
            try:
                r = responder(p["pergunta"])
            except Exception as e:  # falha operacional explícita, sem conteúdo sensível da exceção
                from .gerador import Resultado
                r = Resultado(nome, None, None, False, type(e).__name__)
            r.configuracao = nome
            linha = avaliar(p, r)
            linhas.append(linha)
            f.write(json.dumps(linha, ensure_ascii=False) + "\n")
            f.flush()
            if progresso:
                print(f"\r{nome}: {i}/{len(perguntas)}", end="", flush=True)
    if progresso:
        print()
    return linhas


_t = av2._taxa


def resumir(linhas: list[dict]) -> dict:
    resp = [l for l in linhas if not l["nao_consta_esperado"]]
    nc = [l for l in linhas if l["nao_consta_esperado"]]
    tr = [l for l in linhas if l["intencao_esperada"] == "tempo_real"]
    cat = lambda ls, c: sum(l["categoria"] == c for l in ls)
    emitidas = [l for l in linhas if l["respondeu"]]
    com_cobertura = [l for l in emitidas if l.get("cobertura_evidencias") is not None]
    erros = cat(resp, "erro_factual") + cat(nc, "resposta_indevida")
    lat = sorted(l["latencia_ms"] for l in linhas)
    com_int = [l for l in linhas if l["intencao_prevista"] is not None]
    return {
        "configuracao": linhas[0]["configuracao"],
        "rubrica_versao": RUBRICA_VERSAO,
        "acerto_total": _t(cat(resp, "correto") + cat(nc, "recusa_correta"), len(linhas)),
        "correto_respondiveis": _t(cat(resp, "correto"), len(resp)),
        "incompleto": _t(cat(resp, "incompleto"), len(resp)),
        "recusa_indevida": _t(cat(resp, "recusa_indevida"), len(resp)),
        "erro_factual_respondiveis": _t(cat(resp, "erro_factual"), len(resp)),
        "sem_fato": _t(cat(resp, "sem_fato"), len(resp)),
        "recusa_correta_nao_consta": _t(cat(nc, "recusa_correta"), len(nc)),
        "tempo_real_recusado": _t(cat(tr, "recusa_correta"), len(tr)),
        "erros_factuais_por_pergunta": _t(erros, len(linhas)),
        "erros_factuais_entre_emitidas": _t(erros, len(emitidas)),
        "sem_citacao_entre_emitidas": _t(sum(l["sem_citacao"] for l in emitidas), len(emitidas)),
        "citacao_pertinente": _t(sum(bool(l["citacao_pertinente"]) for l in emitidas if not l["nao_consta_esperado"]),
                                 len([l for l in emitidas if not l["nao_consta_esperado"]])),
        "cobertura_evidencias": _t(sum(l["cobertura_evidencias"] for l in com_cobertura), len(com_cobertura)),
        "intencao_correta": _t(sum(l["intencao_prevista"] == l["intencao_esperada"] for l in com_int), len(com_int)),
        "falha_operacional": _t(cat(linhas, "falha_operacional"), len(linhas)),
        "latencia_media_s": round(statistics.mean(lat) / 1000, 2),
        "latencia_mediana_s": round(statistics.median(lat) / 1000, 2),
        "latencia_p90_s": round(lat[int(0.9 * (len(lat) - 1))] / 1000, 2),
        "n": len(linhas),
    }

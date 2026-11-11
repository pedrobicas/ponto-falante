"""Avaliação v2: rubrica revisada após a revisão crítica do experimento v1.

A avaliação v1 (avaliacao.py) continua intacta para reproduzir o experimento original.

Mudanças em relação à v1:
- Eixos separados por resposta (uma categoria principal):
    correto               respondeu e trouxe TODOS os fatos obrigatórios, sem afirmação proibida
    incompleto            respondeu, sem afirmação proibida, mas faltou parte dos fatos obrigatórios
    erro_factual          respondeu com uma afirmação proibida (valor, público, negação trocados)
    sem_fato              respondeu algo, mas nenhum fato obrigatório aparece (fora do ponto / não verificável)
    recusa_indevida       recusou uma pergunta que a base responde
    recusa_correta        recusou uma pergunta "não consta"
    resposta_indevida     respondeu (afirmou algo) a uma pergunta "não consta"
    falha_operacional     JSON inválido / exceção / saída vazia
- Fatos obrigatórios × opcionais (só o que a pergunta pede é obrigatório).
- Números casam com fronteira ("10%" não casa com "110%"); fato precedido de negação não conta.
- Recusa: julgada pelo texto falado; uma recusa que também afirma números NÃO é recusa.
- Citação: pertinência (citou trecho de algum grupo de evidência) e cobertura (todos os grupos)
  são medidas separadas da existência do id.
- Denominadores explícitos em todas as taxas.
"""
from __future__ import annotations

import json
import re
import statistics
import unicodedata
from pathlib import Path
from typing import Callable

from . import AVALIACAO

PASTA_V2 = AVALIACAO / "v2"
CONJUNTOS_V2 = {
    "dev": PASTA_V2 / "perguntas_dev_v2.jsonl",          # ajustes
    "teste_v2": PASTA_V2 / "perguntas_teste_v2.jsonl",   # inédito, rodado uma vez no fim
}


def carregar(conjunto: str | Path) -> list[dict]:
    caminho = CONJUNTOS_V2.get(conjunto, conjunto) if isinstance(conjunto, str) else conjunto
    with Path(caminho).open(encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def normalizar(s: str) -> str:
    s = unicodedata.normalize("NFKD", (s or "").lower())
    return "".join(c for c in s if not unicodedata.combining(c))


_NEGACAO = re.compile(r"\b(nao|nunca|sem|nenhum|nenhuma)\b")
_RECUSA = ("nao encontrei", "nao sei", "nao consta", "nao tenho essa informacao", "nao tenho informac",
           "nao possuo", "nao ha informac", "nao foi possivel encontrar", "nao disponho", "indisponivel")
_NUM = re.compile(r"\d+(?:[.,]\d+)?")


def _padrao(variacao: str) -> re.Pattern:
    v = re.escape(normalizar(variacao))
    if variacao[:1].isdigit():
        return re.compile(r"(?<![\d.,])" + v + r"(?![\d])")
    return re.compile(v)


def encontra(texto: str, variacao: str) -> tuple[bool, bool]:
    """(encontrou, negado). Uma variação que não contém negação, quando aparece logo depois de
    'não/nunca/sem', conta como negada (ex.: 'não precisa comparecer pessoalmente')."""
    t = normalizar(texto)
    var_tem_negacao = bool(_NEGACAO.search(normalizar(variacao)))
    achou_algum = False
    for m in _padrao(variacao).finditer(t):
        achou_algum = True
        antes = t[max(0, m.start() - 25):m.start()]
        if var_tem_negacao or not _NEGACAO.search(antes):
            return True, False
    return False, achou_algum


def eh_recusa(texto: str | None, flag_nao_consta: bool | None) -> bool:
    """Recusa = o que seria FALADO é uma recusa e não afirma fatos (números além do 156)."""
    if not texto:
        return False
    t = normalizar(texto)
    numeros = [n for n in _NUM.findall(t) if n != "156"]
    frase_recusa = any(r in t for r in _RECUSA)
    return frase_recusa and not numeros and len(t) < 260


def classificar(p: dict, texto: str | None, falhou: bool, citados: list[str]) -> dict:
    if falhou or texto is None or not texto.strip():
        return {"categoria": "falha_operacional", "faltando": [], "proibidas": []}
    recusou = eh_recusa(texto, None)
    if p["nao_consta"]:
        return {"categoria": "recusa_correta" if recusou else "resposta_indevida", "faltando": [], "proibidas": []}
    if recusou:
        return {"categoria": "recusa_indevida", "faltando": [], "proibidas": []}
    proibidas = [a for a in p.get("afirmacoes_proibidas", []) if encontra(texto, a)[0]]
    faltando, negados = [], []
    for fato in p["fatos_obrigatorios"]:
        res = [encontra(texto, v) for v in fato["variacoes"]]
        if not any(r[0] for r in res):
            faltando.append(fato["descricao"])
            if any(r[1] for r in res):
                negados.append(fato["descricao"])
    if proibidas or negados:
        cat = "erro_factual"
    elif not faltando:
        cat = "correto"
    elif len(faltando) < len(p["fatos_obrigatorios"]):
        cat = "incompleto"
    else:
        cat = "sem_fato"
    return {"categoria": cat, "faltando": faltando, "proibidas": proibidas + [f"negou: {n}" for n in negados]}


def avaliar(p: dict, r) -> dict:
    """r: gerador.Resultado (v1 ou v2)."""
    resp = r.resposta
    texto = resp.resposta if resp else None
    citados = [f.trecho_id for f in resp.fontes] if resp else []
    c = classificar(p, texto, (resp is None) or (not r.json_valido), citados)
    grupos = [set(g) for g in p.get("evidencias", [])]
    respondeu = c["categoria"] in ("correto", "incompleto", "erro_factual", "sem_fato", "resposta_indevida")
    pertinente = cobertura = None
    if respondeu and not p["nao_consta"]:
        pertinente = any(set(citados) & g for g in grupos)
        cobertura = all(set(citados) & g for g in grupos) if grupos else None
    return {
        "id": p["id"], "categoria_pergunta": p.get("categoria"), "nao_consta_esperado": p["nao_consta"],
        "configuracao": r.configuracao, **c, "respondeu": respondeu,
        "sem_citacao": (respondeu and not citados),
        "citacao_pertinente": pertinente, "cobertura_evidencias": cobertura,
        "resposta": texto, "fontes": citados, "confianca": resp.confianca if resp else None,
        "recuperados": r.recuperados, "scores": r.scores, "latencia_ms": r.latencia_ms,
        "passos": r.passos, "erro": r.erro,
    }


def rodar(perguntas: list[dict], responder: Callable, nome: str, conjunto: str,
          pasta: Path = PASTA_V2, progresso: bool = True) -> list[dict]:
    linhas = []
    for i, p in enumerate(perguntas, 1):
        try:
            r = responder(p["pergunta"])
        except Exception as e:  # falha operacional explícita, nunca silenciosa
            from .gerador import Resultado
            r = Resultado(nome, None, None, False, f"{type(e).__name__}: {e}")
        linhas.append(avaliar(p, r))
        if progresso:
            print(f"\r{nome}: {i}/{len(perguntas)}", end="", flush=True)
    if progresso:
        print()
    pasta.mkdir(parents=True, exist_ok=True)
    with (pasta / f"resultados_{conjunto}_{nome}.jsonl").open("w", encoding="utf-8") as f:
        for l in linhas:
            f.write(json.dumps(l, ensure_ascii=False) + "\n")
    return linhas


def _taxa(num: int, den: int) -> str:
    return f"{100 * num / den:.1f}% ({num}/{den})" if den else "n/a (0/0)"


def resumir(linhas: list[dict]) -> dict:
    resp = [l for l in linhas if not l["nao_consta_esperado"]]
    nc = [l for l in linhas if l["nao_consta_esperado"]]
    cat = lambda ls, c: sum(l["categoria"] == c for l in ls)
    emitidas = [l for l in linhas if l["respondeu"]]
    emitidas_resp = [l for l in resp if l["respondeu"]]
    erros_fact = cat(resp, "erro_factual") + cat(nc, "resposta_indevida")
    return {
        "configuracao": linhas[0]["configuracao"],
        "acerto_total": _taxa(cat(resp, "correto") + cat(nc, "recusa_correta"), len(linhas)),
        "correto_respondiveis": _taxa(cat(resp, "correto"), len(resp)),
        "incompleto": _taxa(cat(resp, "incompleto"), len(resp)),
        "recusa_indevida": _taxa(cat(resp, "recusa_indevida"), len(resp)),
        "erro_factual_respondiveis": _taxa(cat(resp, "erro_factual"), len(resp)),
        "sem_fato": _taxa(cat(resp, "sem_fato"), len(resp)),
        "recusa_correta_nao_consta": _taxa(cat(nc, "recusa_correta"), len(nc)),
        "resposta_indevida_nao_consta": _taxa(cat(nc, "resposta_indevida"), len(nc)),
        "erros_factuais_por_pergunta": _taxa(erros_fact, len(linhas)),
        "erros_factuais_entre_respostas_emitidas": _taxa(erros_fact, len(emitidas)),
        "sem_citacao_entre_emitidas": _taxa(sum(l["sem_citacao"] for l in emitidas), len(emitidas)),
        "citacao_pertinente": _taxa(sum(bool(l["citacao_pertinente"]) for l in emitidas_resp), len(emitidas_resp)),
        "falha_operacional": _taxa(cat(linhas, "falha_operacional"), len(linhas)),
        "latencia_media_s": round(statistics.mean(l["latencia_ms"] for l in linhas) / 1000, 2),
        "n": len(linhas),
    }

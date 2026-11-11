"""Agente v2: correções guiadas pela revisão crítica e pelos 5 erros reais do v1.

O agente v1 (agente.py) fica intacto para reproduzir o experimento original.

Diferenças em relação ao v1 (cada uma vira uma ablação no conjunto DEV):
 1. BUSCA HÍBRIDA: BM25 (palavras exatas: "idoso", "passagem") + vetorial e5-large, fundidas por
    posição (RRF), sobre a pergunta ORIGINAL e a reescrita. A reescrita é instruída a manter o
    público (idoso, PCD, estudante), a idade e a modalidade.
 2. LIMIAR calibrado só sobre a pergunta original (como no notebook 02), não sobre o máximo das buscas.
 3. GERAÇÃO com campos descritos, exemplo de saída, citação obrigatória e "evidencia" (frase do
    trecho). Ids conhecidos são removidos do texto; resposta vazia gera reparo, não recusa direta.
 4. REPARO de recusa: se o gerador disser "não consta" com um trecho muito forte (>= LIMIAR_FORTE),
    uma nova tentativa só com os 2 melhores trechos.
 5. VERIFICADOR por afirmação: lista cada afirmação com a frase do trecho que a sustenta; a frase
    precisa existir no trecho (checagem determinística). Falha do verificador NÃO aprova
    (falha fechada). Modelo do verificador configurável (3B, 7B) ou desligado (ablação).
 6. NÚMEROS: só valem números dos trechos citados (o título do documento não conta); números da
    pergunta só valem para comparação com a idade/dado pessoal informado.
"""
from __future__ import annotations

import json
import os
import re
import time
import unicodedata
from dataclasses import dataclass, field

from rank_bm25 import BM25Okapi

from . import llm
from .esquemas import Fonte, RespostaIA, recusa
from .gerador import LIMIAR, REGRAS_ESTILO, Resultado
from .indice import Indice, embutir
import numpy as np


@dataclass
class ConfigV2:
    nome: str = "agente_v2"
    modelo_gerador: str = os.environ.get("PF_MODELO_GERADOR", "qwen2.5:3b")
    modelo_triagem: str = os.environ.get("PF_MODELO_TRIAGEM", "qwen2.5:3b")
    modelo_verificador: str | None = os.environ.get("PF_MODELO_VERIFICADOR", "qwen2.5:3b") or None
    busca_hibrida: bool = True
    reescrita: bool = True
    k_contexto: int = 4
    limiar: float = LIMIAR
    limiar_forte: float = 0.89
    reparo_recusa: bool = True
    tentativas: int = 2
    extras: dict = field(default_factory=dict)


# ---------------- Busca híbrida ----------------
def _tokens(s: str) -> list[str]:
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return [t for t in re.findall(r"\w+", s) if len(t) > 1]


_BM25_CACHE: dict = {}


def bm25_de(indice: Indice) -> BM25Okapi:
    chave = tuple(t.trecho_id for t in indice.trechos)
    if chave not in _BM25_CACHE:
        _BM25_CACHE[chave] = BM25Okapi([_tokens(f"{t.documento} {t.texto}") for t in indice.trechos])
    return _BM25_CACHE[chave]


def buscar_hibrido(indice: Indice, consultas: list[str], k: int, n_cand: int = 10, rrf_k: int = 60,
                   hibrida: bool = True, ordenar: str = "cosseno") -> list[tuple]:
    """Candidatos: top-n vetorial e top-n BM25 de cada consulta (original e reescrita).
    Ordenação final ("cosseno", padrão): similaridade de cosseno com a PERGUNTA ORIGINAL, calculada
    para todos os candidatos (o BM25 só amplia a lista; quem ordena é a pergunta da pessoa, o que
    evita que a reescrita ou uma palavra comum puxe trecho de outro público). "rrf": fusão por posição.
    Devolve [(trecho, score_rrf, cosseno_com_a_pergunta_original)]."""
    rrf: dict[str, float] = {}
    por_id = {t.trecho_id: t for t in indice.trechos}
    pos_idx = {t.trecho_id: i for i, t in enumerate(indice.trechos)}
    bm = bm25_de(indice) if hibrida else None
    for q in consultas:
        for pos, a in enumerate(indice.buscar(q, n_cand)):
            tid = a.trecho.trecho_id
            rrf[tid] = rrf.get(tid, 0) + 1 / (rrf_k + pos + 1)
        if bm is not None:
            sc = bm.get_scores(_tokens(q))
            top = sorted(range(len(sc)), key=lambda i: -sc[i])[:n_cand]
            for pos, i in enumerate(top):
                if sc[i] <= 0:
                    break
                tid = indice.trechos[i].trecho_id
                rrf[tid] = rrf.get(tid, 0) + 1 / (rrf_k + pos + 1)
    qv = embutir([consultas[0]], indice.nome_modelo, tipo="query")[0]
    cos = {tid: float(np.dot(qv, indice.index.reconstruct(pos_idx[tid]))) for tid in rrf}
    chave = (lambda t: -cos[t]) if ordenar == "cosseno" else (lambda t: -rrf[t])
    ordem = sorted(rrf, key=chave)[:k]
    return [(por_id[t], round(rrf[t], 4), round(cos[t], 4)) for t in ordem]


# ---------------- Público (idoso / PCD / estudante) ----------------
_PUBLICO_DOC = {"sptrans-gratuidade-65-mais": "idoso", "sptrans-gratuidade-60-64": "idoso",
                "lei-10741-transporte": "idoso", "sptrans-bilhete-pcd": "pcd",
                "lei-13146-transporte": "pcd", "sptrans-bilhete-estudante": "estudante"}
_PUBLICO_PERGUNTA = {
    "idoso": r"\b(idos[oa]s?|velhinh|aposentad|terceira idade|[6-9]\d anos)",
    "pcd": r"\b(deficien|pcd|cadeirante|cego|surd|autis|acompanhante|mobilidade reduzida|soropositiv|hiv)",
    "estudante": r"\b(estudante|escola|faculdade|universit|aluno|meia.tarifa|cadunico|cad unico)",
}


def publico_da_pergunta(pergunta: str) -> set[str]:
    t = " ".join(_tokens(pergunta))
    return {p for p, rx in _PUBLICO_PERGUNTA.items() if re.search(rx, t)}


def publico_do_trecho(trecho_id: str) -> str | None:
    for prefixo, pub in _PUBLICO_DOC.items():
        if trecho_id.startswith(prefixo):
            return pub
    return None


# ---------------- Prompts ----------------
SISTEMA_TRIAGEM = (
    "Reescreva a pergunta de um passageiro de ônibus de São Paulo como uma consulta de busca, com os "
    "termos formais da SPTrans e das leis (ex.: 'pessoa idosa', 'pessoa com deficiência', 'gratuidade', "
    "'Bilhete Único Especial', 'integração', 'tarifa', 'acompanhante', 'segunda via'). "
    "OBRIGATÓRIO: mantenha o público (idoso, pessoa com deficiência, estudante), a idade, o tipo de "
    "cartão e o assunto exato. Não troque números. Não invente informação.\n"
    "Exemplos:\n"
    "'O cartão de idoso vence?' -> 'validade renovação Bilhete Único Especial pessoa idosa'\n"
    "'Tenho 62 anos, preciso de cartão novo pra gratuidade?' -> 'gratuidade 60 a 64 anos Bilhete Único Comum mesmo cartão'\n"
    "'Quanto tá a passagem?' -> 'tarifa ônibus valor passagem'"
)
SCHEMA_TRIAGEM = {"type": "object", "properties": {"consulta": {"type": "string"}}, "required": ["consulta"]}

SISTEMA_RESPOSTA = (
    "Você é o assistente do Ponto Falante para passageiros de ônibus de São Paulo. "
    "Responda usando SOMENTE os trechos do CONTEXTO. Copie números, idades, valores e prazos exatamente. "
    "Responda exatamente o que foi perguntado (se a pergunta tiver duas partes, responda as duas). "
    "Você pode fazer comparações simples com o que a pessoa disse (ex.: 66 anos é mais de 65). "
    "Se o assunto é parecido mas a informação pedida NÃO está nos trechos, use nao_consta=true. "
    + REGRAS_ESTILO +
    "\nCampos do JSON:\n"
    "- resposta: o texto que será FALADO para a pessoa (nunca escreva ids de trecho aqui).\n"
    "- trechos_usados: ids dos trechos que sustentam a resposta (pelo menos 1 quando nao_consta=false).\n"
    "- evidencia: a frase do trecho que responde à pergunta, copiada palavra por palavra.\n"
    "- nao_consta: true só se nenhum trecho tiver a informação pedida.\n"
    "Responda com suas próprias palavras a partir dos trechos; não repita estas instruções."
)

SISTEMA_VERIFICACAO = (
    "Você confere uma resposta. Separe a RESPOSTA em afirmações curtas. Para cada afirmação, copie dos "
    "TRECHOS a frase que a sustenta, palavra por palavra (campo 'frase_do_trecho'), e diga se ela está "
    "sustentada. Uma comparação simples com o que a pessoa disse (ex.: 66 é mais que 65) é sustentada. "
    "Afirmação com número, prazo, valor, público ou condição diferente do trecho NÃO é sustentada. "
    "Se não houver frase que sustente, deixe frase_do_trecho vazia e sustentada=false."
)
SCHEMA_VERIFICACAO = {
    "type": "object",
    "properties": {"afirmacoes": {"type": "array", "items": {"type": "object", "properties": {
        "afirmacao": {"type": "string"}, "frase_do_trecho": {"type": "string"}, "sustentada": {"type": "boolean"}},
        "required": ["afirmacao", "frase_do_trecho", "sustentada"]}}},
    "required": ["afirmacoes"],
}


def _schema_resposta(ids: list[str]) -> dict:
    return {
        "type": "object",
        "properties": {
            "resposta": {"type": "string", "description": "texto falado, sem ids"},
            "trechos_usados": {"type": "array", "items": {"type": "string", "enum": ids}},
            "evidencia": {"type": "string"},
            "nao_consta": {"type": "boolean"},
        },
        "required": ["resposta", "trechos_usados", "evidencia", "nao_consta"],
    }


# ---------------- Checagens determinísticas ----------------
_NUM = re.compile(r"\d+(?:[.,]\d+)*")


def _norm_num(n: str) -> str:
    n = n.replace(".", "") if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", n) else n   # 1.000 -> 1000
    return n.replace(",", ".")


def numeros_sem_suporte(resposta: str, textos: list[str], pergunta: str) -> list[str]:
    base = {_norm_num(n) for n in _NUM.findall(" ".join(textos))}
    da_pergunta = {_norm_num(n) for n in _NUM.findall(pergunta)}
    out = []
    for n in _NUM.findall(resposta):
        nn = _norm_num(n)
        if nn in base:
            continue
        if nn in da_pergunta:   # dado pessoal (ex.: idade) repetido para comparação
            continue
        out.append(n)
    return out


def _palavras(s: str) -> list[str]:
    return _tokens(s)


def frase_existe(frase: str, textos: list[str], cobertura: float = 0.75, minimo: int = 4) -> bool:
    ev = _palavras(frase)
    if len(ev) < minimo:
        return False
    n = max(minimo, int(len(ev) * cobertura))
    for t in textos:
        tt = " " + " ".join(_palavras(t)) + " "
        for i in range(0, len(ev) - n + 1):
            if " " + " ".join(ev[i:i + n]) + " " in tt:
                return True
    return False


def remover_ids(texto: str, ids: list[str]) -> str:
    for i in sorted(ids, key=len, reverse=True):
        texto = re.sub(r"\[?\b" + re.escape(i) + r"\b\]?", " ", texto, flags=re.IGNORECASE)
    return re.sub(r"\s{2,}", " ", texto).strip(" ,;")


# ---------------- Agente ----------------
def responder(pergunta: str, indice: Indice, cfg: ConfigV2 | None = None) -> Resultado:
    cfg = cfg or ConfigV2()
    t0 = time.perf_counter()
    passos: list[str] = []
    ms = lambda: int((time.perf_counter() - t0) * 1000)

    # 1. Limiar sobre a pergunta original (calibrado no DEV, notebook 02)
    original = indice.buscar(pergunta, 1)
    top_cos = original[0].score if original else 0.0
    passos.append(f"limiar: cosseno da pergunta original {top_cos:.4f} (limiar {cfg.limiar})")
    if top_cos < cfg.limiar:
        passos.append("abaixo do limiar: recusa")
        return Resultado(cfg.nome, recusa("alta"), None, True, None, [], [round(top_cos, 4)], ms(), passos)

    # 2. Reescrita preservando público/idade + busca híbrida
    consultas = [pergunta]
    if cfg.reescrita:
        try:
            q = llm.gerar_json(SISTEMA_TRIAGEM, pergunta, SCHEMA_TRIAGEM, modelo=cfg.modelo_triagem,
                               num_predict=80)["consulta"].strip()
            if q:
                consultas.append(q)
            passos.append(f"reescrita: '{q}'")
        except (json.JSONDecodeError, ValueError, KeyError):
            passos.append("reescrita falhou; usando só a pergunta original")
    achados = buscar_hibrido(indice, consultas, cfg.k_contexto, hibrida=cfg.busca_hibrida)
    ids = [t.trecho_id for t, _, _ in achados]
    scores = [c for _, _, c in achados]
    passos.append(f"busca: {[(t.trecho_id, r, c) for t, r, c in achados]}")
    mapa = {t.trecho_id: t for t, _, _ in achados}

    def contexto(selecao):
        return "\n\n".join(f"[{t.trecho_id}] ({t.documento})\n{t.texto}" for t in selecao)

    selecao = [t for t, _, _ in achados]
    aviso, reparou_recusa = "", False
    tentativa = 0
    while tentativa < cfg.tentativas:
        tentativa += 1
        usuario = f"CONTEXTO:\n{contexto(selecao)}\n\nPERGUNTA: {pergunta}{aviso}"
        try:
            g = llm.gerar_json(SISTEMA_RESPOSTA, usuario, _schema_resposta([t.trecho_id for t in selecao]),
                               modelo=cfg.modelo_gerador)
        except (json.JSONDecodeError, ValueError):
            passos.append(f"tentativa {tentativa}: JSON inválido")
            aviso = "\n\nATENÇÃO: devolva somente o JSON pedido."
            continue

        # 4. Reparo de recusa com trecho forte
        if g.get("nao_consta"):
            if cfg.reparo_recusa and not reparou_recusa and max(scores or [0]) >= cfg.limiar_forte:
                reparou_recusa = True
                selecao = sorted(selecao, key=lambda t: -dict(zip(ids, scores)).get(t.trecho_id, 0))[:2]
                passos.append(f"tentativa {tentativa}: modelo disse não consta com trecho forte; reparo só com {[t.trecho_id for t in selecao]}")
                aviso = ("\n\nATENÇÃO: leia os trechos com cuidado; se algum deles responder ao que foi "
                         "perguntado, responda. Se não responder, use nao_consta=true.")
                tentativa -= 1      # o reparo de recusa não consome tentativa
                continue
            passos.append(f"tentativa {tentativa}: o modelo indicou que não consta")
            return Resultado(cfg.nome, recusa("media"), g, True, None, ids, scores, ms(), passos)

        texto = remover_ids(g.get("resposta", ""), list(mapa))
        usados = [i for i in dict.fromkeys(g.get("trechos_usados") or []) if i in mapa]
        if not texto or len(texto) > 600:
            passos.append(f"tentativa {tentativa}: resposta vazia ou longa demais ({len(texto)} caracteres)")
            aviso = "\n\nATENÇÃO: escreva a resposta em português no campo resposta (sem ids), em até 3 frases."
            continue
        if not usados:
            passos.append(f"tentativa {tentativa}: sem trecho citado")
            aviso = "\n\nATENÇÃO: liste em trechos_usados o id do trecho que sustenta a resposta."
            continue
        textos = [mapa[i].texto for i in usados]

        # 5a. Público: se a pergunta é de UM público, não vale citar trecho de OUTRO público
        pubs = publico_da_pergunta(pergunta)
        if len(pubs) == 1:
            errados = [i for i in usados if publico_do_trecho(i) not in (None, *pubs)]
            if errados:
                passos.append(f"tentativa {tentativa}: citou trecho de outro público {errados} (pergunta: {pubs})")
                selecao = [t for t in selecao if publico_do_trecho(t.trecho_id) in (None, *pubs)] or selecao
                aviso = (f"\n\nATENÇÃO: a pergunta é sobre {next(iter(pubs))}; use só trechos desse público "
                         "ou gerais, ou use nao_consta=true.")
                continue

        # 6. Números (títulos dos documentos entram: '65+' e '60 a 64 anos' identificam o público)
        sem = numeros_sem_suporte(texto, textos + [mapa[i].documento for i in usados], pergunta)
        if sem:
            passos.append(f"tentativa {tentativa}: números sem suporte nos trechos citados {sem}")
            aviso = f"\n\nATENÇÃO: os números {sem} não aparecem nos trechos citados. Corrija ou use nao_consta=true."
            continue

        # 5. Verificador por afirmação (falha fechada)
        if cfg.modelo_verificador:
            try:
                v = llm.gerar_json(SISTEMA_VERIFICACAO,
                                   f"TRECHOS:\n{chr(10).join(textos)}\n\nPERGUNTA: {pergunta}\nRESPOSTA: {texto}",
                                   SCHEMA_VERIFICACAO, modelo=cfg.modelo_verificador, num_predict=400)
                afirm = v.get("afirmacoes") or []
            except (json.JSONDecodeError, ValueError):
                afirm = None
            if afirm is None or not afirm:
                passos.append(f"tentativa {tentativa}: verificador indisponível/vazio (falha fechada)")
                aviso = ""
                continue
            problemas = [a["afirmacao"] for a in afirm
                         if not a.get("sustentada") or not frase_existe(a.get("frase_do_trecho", ""), textos)]
            if problemas:
                passos.append(f"tentativa {tentativa}: afirmações sem frase de suporte {problemas[:3]}")
                aviso = ("\n\nATENÇÃO: estas afirmações não estão nos trechos: " + "; ".join(problemas[:3]) +
                         ". Responda só o que os trechos dizem, ou use nao_consta=true.")
                continue
            passos.append(f"tentativa {tentativa}: {len(afirm)} afirmações com frase de suporte")

        conf = "alta" if tentativa == 1 and not reparou_recusa and max(scores) >= cfg.limiar + 0.03 else "media"
        resp = RespostaIA(resposta=texto, fontes=[Fonte(documento=mapa[i].documento, trecho_id=i) for i in usados],
                          confianca=conf, nao_consta=False)
        passos.append(f"tentativa {tentativa}: aprovada ({conf})")
        return Resultado(cfg.nome, resp, g, True, None, ids, scores, ms(), passos)

    passos.append("tentativas esgotadas: recusa com confiança baixa")
    return Resultado(cfg.nome, recusa("baixa"), None, True, None, ids, scores, ms(), passos)

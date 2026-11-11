"""As três configurações comparadas no placar.

A) sem_contexto : o mesmo LLM responde só com o que "sabe" (linha de base).
B) rag          : RAG simples: busca top-3; se o melhor trecho fica abaixo do limiar, recusa;
                  senão o LLM responde em JSON citando os trechos.
C) agente       : RAG + agente (ver agente.py): escopo, reescrita da consulta, busca dupla,
                  citações restritas aos trechos recuperados e verificação de fundamentação.

Todas devolvem um Resultado com a RespostaIA validada (ou o erro de validação).
"""
from __future__ import annotations

import json
import re
import os
import time
from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError

from . import llm
from .esquemas import RespostaIA, recusa
from .indice import Indice, Resultado as Achado

LIMIAR = float(os.environ.get("PF_LIMIAR", "0.86"))   # escolhido no conjunto DEV (notebook 02)

REGRAS_ESTILO = (
    "Responda em português do Brasil, em no máximo 3 frases curtas e simples, "
    "porque a resposta será lida em voz alta para uma pessoa idosa ou com deficiência visual. "
    "Não use siglas sem explicar, listas nem markdown."
)

SCHEMA_RESPOSTA = {
    "type": "object",
    "properties": {
        "resposta": {"type": "string"},
        "fontes": {"type": "array", "items": {
            "type": "object",
            "properties": {"documento": {"type": "string"}, "trecho_id": {"type": "string"}},
            "required": ["documento", "trecho_id"]}},
        "confianca": {"type": "string", "enum": ["alta", "media", "baixa"]},
        "nao_consta": {"type": "boolean"},
    },
    "required": ["resposta", "fontes", "confianca", "nao_consta"],
}


@dataclass
class Resultado:
    configuracao: str
    resposta: RespostaIA | None
    bruto: Any = None
    json_valido: bool = True
    erro: str | None = None
    recuperados: list[str] = field(default_factory=list)   # trecho_ids recuperados
    scores: list[float] = field(default_factory=list)
    latencia_ms: int = 0
    passos: list[str] = field(default_factory=list)          # rastro do agente (explicabilidade)


_ID = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*-\d{3}")


def _normalizar_fontes(bruto: dict) -> dict:
    """O modelo às vezes copia o trecho inteiro ou '[id]' no campo trecho_id. Extraímos o id
    quando ele aparece (mesma regra para sem_contexto e rag: condições equivalentes)."""
    for f in bruto.get("fontes") or []:
        if isinstance(f, dict) and isinstance(f.get("trecho_id"), str):
            m = _ID.search(f["trecho_id"])
            if m:
                f["trecho_id"] = m.group(0)
    return bruto


def _validar(bruto: dict) -> tuple[RespostaIA | None, str | None]:
    bruto = _normalizar_fontes(bruto)
    try:
        return RespostaIA.model_validate(bruto), None
    except ValidationError as e:
        return None, e.errors()[0]["msg"]


def formatar_contexto(achados: list[Achado]) -> str:
    return "\n\n".join(f"[{a.trecho.trecho_id}] ({a.trecho.documento})\n{a.trecho.texto}" for a in achados)


# ---------- A) sem contexto ----------
SISTEMA_SEM_CONTEXTO = (
    "Você é o assistente do Ponto Falante, que tira dúvidas de passageiros de ônibus da cidade de São Paulo "
    "sobre tarifa, gratuidade, Bilhete Único e direitos de pessoas idosas e com deficiência no transporte. "
    + REGRAS_ESTILO +
    " Devolva JSON com: resposta, fontes (lista de {documento, trecho_id} que embasam a resposta), "
    "confianca (alta, media ou baixa) e nao_consta (true se você não souber)."
)


def sem_contexto(pergunta: str) -> Resultado:
    t0 = time.perf_counter()
    try:
        bruto = llm.gerar_json(SISTEMA_SEM_CONTEXTO, pergunta, SCHEMA_RESPOSTA)
    except (json.JSONDecodeError, ValueError) as e:
        return Resultado("sem_contexto", None, None, False, f"JSON inválido: {e}",
                         latencia_ms=int((time.perf_counter() - t0) * 1000))
    resp, erro = _validar(bruto)
    return Resultado("sem_contexto", resp, bruto, resp is not None, erro,
                     latencia_ms=int((time.perf_counter() - t0) * 1000))


# ---------- B) RAG simples ----------
SISTEMA_RAG = (
    "Você é o assistente do Ponto Falante para passageiros de ônibus de São Paulo. "
    "Use SOMENTE os trechos fornecidos no CONTEXTO. Se a resposta não estiver nos trechos, "
    "devolva nao_consta=true e fontes vazia. Nunca invente valores, prazos ou regras. "
    + REGRAS_ESTILO +
    " Devolva JSON com: resposta, fontes (lista de {documento, trecho_id} dos trechos usados, "
    "copiando o trecho_id entre colchetes), confianca e nao_consta."
)


def rag(pergunta: str, indice: Indice, k: int = 3, limiar: float = LIMIAR) -> Resultado:
    t0 = time.perf_counter()
    achados = indice.buscar(pergunta, k)
    ids, scores = [a.trecho.trecho_id for a in achados], [round(a.score, 4) for a in achados]
    if not achados or achados[0].score < limiar:
        return Resultado("rag", recusa("media"), None, True, None, ids, scores,
                         int((time.perf_counter() - t0) * 1000), ["melhor trecho abaixo do limiar: recusa"])
    usuario = f"CONTEXTO:\n{formatar_contexto(achados)}\n\nPERGUNTA: {pergunta}"
    try:
        bruto = llm.gerar_json(SISTEMA_RAG, usuario, SCHEMA_RESPOSTA)
    except (json.JSONDecodeError, ValueError) as e:
        return Resultado("rag", None, None, False, f"JSON inválido: {e}", ids, scores,
                         int((time.perf_counter() - t0) * 1000))
    resp, erro = _validar(bruto)
    return Resultado("rag", resp, bruto, resp is not None, erro, ids, scores,
                     int((time.perf_counter() - t0) * 1000))

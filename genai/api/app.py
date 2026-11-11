"""API do assistente (chamada pelo backend Spring Boot do MVP).

    uvicorn api.app:app --port 8001        (dentro da pasta genai/, com PYTHONPATH=src)

POST /chat   {"pergunta": "..."} -> {"resposta","fontes","confianca","nao_consta","modo","latencia_ms"}
GET  /health status do serviço, do Ollama e do índice

LGPD: não guardamos a pergunta, nem IP, nem identificador. O log registra só
métricas (latência, se recusou, quantas fontes), nunca o texto.
"""
from __future__ import annotations

import logging
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from pf_genai import agente, gerador, llm
from pf_genai.esquemas import PerguntaChat, RespostaChat
from pf_genai.indice import Indice

log = logging.getLogger("pf_genai.api")
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

_estado: dict = {"indice": None}
# Estratégia servida: "agente" (padrão: menos alucinação, recusa mais) ou "rag" (responde mais,
# alucina mais). Ver RELATORIO.md, seção 7. Escolha do produto, não do placar.
MODO = os.environ.get("PF_MODO", "agente")


@asynccontextmanager
async def ciclo_de_vida(_app):
    try:
        indice().buscar("aquecimento", 1)       # carrega o modelo de embeddings na subida
    except Exception as e:                      # o /health mostra o problema
        log.error("Falha ao carregar o índice: %s", e)
    yield


app = FastAPI(title="Ponto Falante · Assistente (LLM local + RAG + agente)", version="1.0.0",
              lifespan=ciclo_de_vida)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST"], allow_headers=["*"])

INDISPONIVEL = {"resposta": "O assistente está indisponível agora. Tente de novo em instantes.",
                "fontes": [], "confianca": "baixa", "nao_consta": True, "modo": "indisponivel"}


def indice() -> Indice:
    if _estado["indice"] is None:
        _estado["indice"] = Indice.carregar()
    return _estado["indice"]


@app.get("/health")
def health():
    ok_indice = _estado["indice"] is not None
    try:
        modelos = [m.model for m in llm._cliente.list().models]
        ok_llm = any(m.startswith(llm.MODELO) for m in modelos)
    except Exception:
        ok_llm = False
    status = "ok" if ok_indice and ok_llm else "degradado"
    return JSONResponse({"status": status, "llm": llm.MODELO, "llm_ok": ok_llm, "indice_ok": ok_indice},
                        status_code=200 if status == "ok" else 503)


@app.post("/chat", response_model=RespostaChat)
def chat(p: PerguntaChat):
    t0 = time.perf_counter()
    try:
        r = (gerador.rag(p.pergunta.strip(), indice()) if MODO == "rag"
             else agente.responder(p.pergunta.strip(), indice()))
        if r.resposta is None:                  # JSON inválido no RAG simples: recusa segura
            from pf_genai.esquemas import recusa
            r.resposta = recusa("baixa")
    except Exception as e:
        log.error("Falha no /chat: %s", type(e).__name__)
        return JSONResponse(INDISPONIVEL, status_code=503)
    ms = int((time.perf_counter() - t0) * 1000)
    log.info("chat ok | %d ms | nao_consta=%s | fontes=%d", ms, r.resposta.nao_consta, len(r.resposta.fontes))
    return RespostaChat(**r.resposta.model_dump(), modo="rag_agente" if MODO != "rag" else "rag", latencia_ms=ms)

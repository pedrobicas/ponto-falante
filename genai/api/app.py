"""API do assistente, chamada pelo backend Spring Boot via Cloudflare Tunnel.

LGPD: logs contêm só métricas e tipos de erro, nunca pergunta ou chave.
IPs existem apenas na janela de 60 s do limitador em memória, sem persistência.
"""
from __future__ import annotations

import asyncio
import hmac
import logging
import math
import os
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from threading import Lock

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from pf_genai import agente, gerador, llm
from pf_genai.esquemas import PerguntaChat, RespostaChat, recusa
from pf_genai.indice import Indice

log = logging.getLogger("pf_genai.api")
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

_estado: dict = {"indice": None}
# Preserva a escolha de estratégia do produto (ver RELATORIO.md, seção 7).
MODO = os.environ.get("PF_MODO", "agente")
_requisicoes: dict[str, deque[float]] = {}
_trava_limite = Lock()
_agora = time.monotonic
# Mantem no maximo quatro geracoes ativas, inclusive depois de um timeout HTTP.
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="genai")


@asynccontextmanager
async def ciclo_de_vida(_app):
    if os.environ.get("GENAI_AUTH_DESATIVADA") == "1":
        log.warning("GENAI_AUTH_DESATIVADA=1: autenticação desativada; somente desenvolvimento local.")
    try:
        indice().buscar("aquecimento", 1)
    except Exception as e:
        log.error("Falha ao carregar o índice: %s", type(e).__name__)
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


async def proteger_chat(request: Request) -> None:
    if os.environ.get("GENAI_AUTH_DESATIVADA") == "1":
        log.warning("GENAI_AUTH_DESATIVADA=1: autenticação desativada; somente desenvolvimento local.")
    else:
        esperada = os.environ.get("GENAI_API_KEY")
        if not esperada:
            raise HTTPException(503, "GENAI_API_KEY não configurada; /chat indisponível por segurança.")
        recebida = request.headers.get("X-API-Key", "")
        if not hmac.compare_digest(recebida.encode("utf-8"), esperada.encode("utf-8")):
            raise HTTPException(401, "X-API-Key ausente ou inválida.")

    # O listener deve ficar em loopback, acessível externamente apenas pelo Tunnel.
    origem = request.headers.get("CF-Connecting-IP") or (request.client.host if request.client else "desconhecido")
    agora = _agora()
    with _trava_limite:
        # Remove também IPs inativos para não acumular memória indefinidamente.
        for ip, historico in list(_requisicoes.items()):
            if historico[-1] <= agora - 60:
                del _requisicoes[ip]
        historico = _requisicoes.setdefault(origem, deque())
        while historico and historico[0] <= agora - 60:
            historico.popleft()
        if len(historico) >= 20:
            espera = max(1, math.ceil(60 - (agora - historico[0])))
            raise HTTPException(429, "Limite de 20 perguntas por minuto excedido.",
                                headers={"Retry-After": str(espera)})
        historico.append(agora)


@app.get("/health")
def health():
    ok_indice = _estado["indice"] is not None
    try:
        modelos = [m.model for m in llm._cliente.list().models]
        ok_llm = any(m.startswith(llm.MODELO) for m in modelos)
    except Exception:
        ok_llm = False
    status = "ok" if ok_indice and ok_llm else "degradado"
    return JSONResponse({"status": status, "llm_ok": ok_llm, "indice_ok": ok_indice},
                        status_code=200 if status == "ok" else 503)


def _gerar(pergunta: str):
    return (gerador.rag(pergunta, indice()) if MODO == "rag"
            else agente.responder(pergunta, indice()))


@app.post("/chat", response_model=RespostaChat, dependencies=[Depends(proteger_chat)])
async def chat(p: PerguntaChat):
    t0 = time.perf_counter()
    try:
        timeout_s = float(os.environ.get("GENAI_TIMEOUT_S", "40"))
        if not math.isfinite(timeout_s) or timeout_s <= 0:
            raise ValueError
    except ValueError:
        raise HTTPException(503, "GENAI_TIMEOUT_S deve ser um número positivo e finito de segundos.") from None
    try:
        # Inclui fila da thread, carga do índice e todas as etapas do agente/RAG.
        # Python não interrompe a thread síncrona: após o prazo, seu resultado é descartado.
        async with asyncio.timeout(timeout_s):
            r = await asyncio.get_running_loop().run_in_executor(_executor, _gerar, p.pergunta.strip())
        if r.resposta is None:
            r.resposta = recusa("baixa")
        ms = int((time.perf_counter() - t0) * 1000)
        resposta = RespostaChat(**r.resposta.model_dump(), modo="rag_agente" if MODO != "rag" else "rag",
                               latencia_ms=ms)
    except TimeoutError:
        log.warning("Timeout no /chat | %d ms", int((time.perf_counter() - t0) * 1000))
        return JSONResponse(INDISPONIVEL, status_code=504)
    except Exception as e:
        log.error("Falha no /chat: %s", type(e).__name__)
        return JSONResponse(INDISPONIVEL, status_code=503)
    log.info("chat ok | %d ms | nao_consta=%s | fontes=%d", ms, resposta.nao_consta, len(resposta.fontes))
    return resposta

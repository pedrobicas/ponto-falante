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
import re
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from threading import Lock

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from pf_genai import agente, gerador, llm
from pf_genai.esquemas import PerguntaChat, RespostaChat, recusa
from pf_genai.indice import Indice

log = logging.getLogger("pf_genai.api")
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

_estado: dict = {"indice": None, "indice_v3": None}
# Preserva a escolha de estratégia do produto (ver RELATORIO.md, seção 7).
MODO = os.environ.get("PF_MODO", "agente")
_requisicoes: dict[str, deque[float]] = {}
_global: deque[float] = deque()
_CLIENTE_VALIDO = re.compile(r"[0-9a-f]{16,64}")
_trava_limite = Lock()
_agora = time.monotonic
# Mantem no maximo quatro geracoes ativas, inclusive depois de um timeout HTTP.
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="genai")


@asynccontextmanager
async def ciclo_de_vida(_app):
    if os.environ.get("GENAI_AUTH_DESATIVADA") == "1":
        log.warning("GENAI_AUTH_DESATIVADA=1: autenticação desativada; somente desenvolvimento local.")
    try:
        if MODO == "v3":
            indice_v3().buscar("aquecimento", 1)
        else:
            indice().buscar("aquecimento", 1)
    except Exception as e:
        log.error("Falha ao carregar o índice: %s", type(e).__name__)
    yield


app = FastAPI(title="Ponto Falante · Assistente (LLM local + RAG + agente)", version="1.0.0",
              lifespan=ciclo_de_vida)
# Sem CORS: só o Spring Boot (servidor) chama esta API; navegadores nunca falam com ela.

INDISPONIVEL = {"resposta": "O assistente está indisponível agora. Tente de novo em instantes.",
                "fontes": [], "confianca": "baixa", "nao_consta": True, "modo": "indisponivel"}


def indice() -> Indice:
    if _estado["indice"] is None:
        _estado["indice"] = Indice.carregar()
    return _estado["indice"]


def indice_v3():
    if _estado["indice_v3"] is None:
        from pf_genai.busca_v3 import IndiceV3
        _estado["indice_v3"] = IndiceV3.carregar_ou_criar()
    return _estado["indice_v3"]


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

    # Identidade da cota individual. Pelo Tunnel quem conecta é o Spring, então o IP (CF-Connecting-IP) é o
    # mesmo para todos os usuários: o Spring envia X-PF-Cliente (hash salgado do IP do usuário), aceito só
    # depois da chave validada acima. Sem ele, cai no IP. A capacidade total é limitada à parte.
    cliente = request.headers.get("X-PF-Cliente", "")
    if _CLIENTE_VALIDO.fullmatch(cliente):
        origem = "cliente:" + cliente
    else:
        origem = "ip:" + (request.headers.get("CF-Connecting-IP") or (request.client.host if request.client else "desconhecido"))
    limite_global = _limite_global()
    agora = _agora()
    with _trava_limite:
        # Remove também identidades inativas para não acumular memória indefinidamente.
        for chave, historico in list(_requisicoes.items()):
            if historico[-1] <= agora - 60:
                del _requisicoes[chave]
        while _global and _global[0] <= agora - 60:
            _global.popleft()
        if len(_global) >= limite_global:
            espera = max(1, math.ceil(60 - (agora - _global[0])))
            raise HTTPException(429, "Assistente com muitas perguntas no momento.",
                                headers={"Retry-After": str(espera)})
        historico = _requisicoes.setdefault(origem, deque())
        while historico and historico[0] <= agora - 60:
            historico.popleft()
        if len(historico) >= 20:
            espera = max(1, math.ceil(60 - (agora - historico[0])))
            raise HTTPException(429, "Limite de 20 perguntas por minuto excedido.",
                                headers={"Retry-After": str(espera)})
        historico.append(agora)
        _global.append(agora)


def _limite_global() -> int:
    try:
        return max(1, int(os.environ.get("GENAI_LIMITE_GLOBAL_POR_MINUTO", "120")))
    except ValueError:
        return 120


@app.get("/health")
def health():
    ok_indice = (_estado["indice_v3"] if MODO == "v3" else _estado["indice"]) is not None
    try:
        modelos = [m.model for m in llm._cliente.list().models]
        alvo = os.environ.get("PF_MODELO_GERADOR", "qwen2.5:7b") if MODO == "v3" else llm.MODELO
        ok_llm = any(m.startswith(alvo) for m in modelos)
    except Exception:
        ok_llm = False
    status = "ok" if ok_indice and ok_llm else "degradado"
    return JSONResponse({"status": status, "llm_ok": ok_llm, "indice_ok": ok_indice},
                        status_code=200 if status == "ok" else 503)


_DESAFIO = re.compile(r"^[0-9a-f]{32,128}$")


@app.get("/identidade")
def identidade(desafio: str = ""):
    """Prova ao backend que este serviço conhece a GENAI_API_KEY sem enviá-la: HMAC-SHA256 do desafio.

    O backend só aceita registrar um endereço de túnel que responda certo (ver EnderecoGenaiController).
    """
    chave = os.environ.get("GENAI_API_KEY")
    if not chave:
        raise HTTPException(503, "GENAI_API_KEY não configurada.")
    if not _DESAFIO.match(desafio):
        raise HTTPException(400, "Desafio inválido.")
    prova = hmac.new(chave.encode("utf-8"), f"pf-genai-identidade:{desafio}".encode("utf-8"), "sha256").hexdigest()
    return {"prova": prova}


def _gerar(pergunta: str):
    if MODO == "rag":
        return gerador.rag(pergunta, indice())
    if MODO == "v3":
        # Agente v3 (intenção, busca v3 com cross-encoder, recusa calibrada, checagens). Ver RELATORIO.md,
        # "Iteração v3". Modelo via PF_MODELO_GERADOR (padrão qwen2.5:7b); limiar via PF_LIMIAR_V3.
        from pf_genai import agente_v3
        return agente_v3.responder(pergunta, indice_v3(), agente_v3.ConfigV3("api_v3"))
    if MODO == "v2":
        # Agente v2 (busca híbrida, reparo de recusa, verificador por afirmação). Modelos via
        # PF_MODELO_GERADOR / PF_MODELO_VERIFICADOR; ver avaliacao/v2 e RELATORIO.md, seção 11.
        from pf_genai import agente_v2
        return agente_v2.responder(pergunta, indice(), agente_v2.ConfigV2("api_v2"))
    return agente.responder(pergunta, indice())


@app.post("/chat", response_model=RespostaChat, response_model_exclude_none=True,
          dependencies=[Depends(proteger_chat)])
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
        resposta = RespostaChat(**r.resposta.model_dump(),
                                modo={"rag": "rag", "v2": "rag_agente_v2", "v3": "rag_agente_v3"}.get(MODO, "rag_agente"),
                                latencia_ms=ms, intencao=getattr(r, "intencao", None) if MODO == "v3" else None)
    except TimeoutError:
        log.warning("Timeout no /chat | %d ms", int((time.perf_counter() - t0) * 1000))
        return JSONResponse(INDISPONIVEL, status_code=504)
    except Exception as e:
        log.error("Falha no /chat: %s", type(e).__name__)
        return JSONResponse(INDISPONIVEL, status_code=503)
    log.info("chat ok | %d ms | nao_consta=%s | fontes=%d", ms, resposta.nao_consta, len(resposta.fontes))
    return resposta

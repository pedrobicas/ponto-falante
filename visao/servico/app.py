"""
Serviço HTTP da Visão: lê o letreiro de uma foto para a conferência do Embarque Assistido.

Implementa contratos/openapi-visao-letreiro.yaml. O único cliente é o backend Spring Boot: o celular envia a
foto para o Spring (POST /api/embarque/visao/conferir), o Spring repassa para POST /v1/letreiro deste serviço e
decide "confere / não confere / não deu para ler" (classe ConferenciaLetreiro).

O que roda aqui é o mesmo pipeline avaliado no relatório da Visão: YOLO11n treinado (classes onibus e letreiro)
+ EasyOCR em três versões do recorte + validação contra as linhas do ponto (src/leitor_letreiro.py), com duas
regras extras de segurança para o uso pelo celular:
  - casamento EXATO com as linhas do ponto (depois de normalizar O/0, I/1, S/5, B/8...): limiar 1,0 em vez de 0,75.
    Teste ponta a ponta de 17/11: a foto de um 647P-10 conferida no ponto da Av. Paulista (que não tem essa linha)
    "casava" com 478P-10 no limiar 0,75. Uma linha fora da lista volta como leitura não validada, com a confiança
    reduzida, para o backend comparar o texto exato;
  - leitura ambígua entre linhas de número diferente é descartada (rejeitar_ambiguas);
  - se o letreiro mostrou só o número (ex.: "875A"), o serviço devolve só o número, sem completar o sufixo.

Privacidade (LGPD): a imagem só existe em memória durante a requisição. Nada é gravado e o log não tem imagem
nem texto lido, só tempos e contagens.

Executar (da pasta visao/):
    PF_VISAO_SERVICO_CHAVE=<chave> python -m uvicorn servico.app:app --host 127.0.0.1 --port 8090 --workers 1
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
import re
import sys
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Callable

import cv2
import numpy as np
from fastapi import FastAPI, File, Form, Query, Request, UploadFile
from fastapi.responses import JSONResponse

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ / "src") not in sys.path:
    sys.path.insert(0, str(RAIZ / "src"))

log = logging.getLogger("ponto_falante.visao.servico")

VERSAO = "1.0.0"
NOME_MODELO = f"pf-visao {VERSAO} (YOLO11n letreiro + EasyOCR)"
MAX_BYTES = 2 * 1024 * 1024          # mesmo limite do backend
MAX_LADO_PX = 4096
MAX_LINHAS = 300
ESPERA_MAX_S = 6.0                   # espera pela vez; com a inferência na CPU (até ~6,5 s) fica abaixo dos 15 s do backend
LINHA = re.compile(r"^[0-9A-Z]{2,6}(-[0-9]{1,2})?$")
DESAFIO = re.compile(r"^[0-9a-f]{16,128}$")


def _erro(status: int, codigo: str, mensagem: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"erro": codigo, "mensagem": mensagem})


def linhas_validas(bruto: str | None) -> list[str] | None:
    """'875A-10, 875c-10' -> ['875A-10', '875C-10']. Itens fora do formato são ignorados."""
    if not bruto:
        return None
    vistas: list[str] = []
    for item in bruto.split(","):
        linha = item.strip().upper()
        if LINHA.match(linha) and linha not in vistas:
            vistas.append(linha)
        if len(vistas) >= MAX_LINHAS:
            break
    return vistas or None


def decodificar(dados: bytes) -> np.ndarray | None:
    """Aceita só JPEG/PNG (pela assinatura, não pelo nome) e devolve a imagem BGR."""
    if not (dados[:3] == b"\xff\xd8\xff" or dados[:8] == b"\x89PNG\r\n\x1a\n"):
        return None
    img = cv2.imdecode(np.frombuffer(dados, np.uint8), cv2.IMREAD_COLOR)
    if img is None or img.size == 0 or max(img.shape[:2]) > MAX_LADO_PX:
        return None
    return img


def prova_identidade(chave: str, desafio: str) -> str:
    return hmac.new(chave.encode(), f"pf-visao-identidade:{desafio}".encode(), hashlib.sha256).hexdigest()


class Leitor:
    """Uma inferência por vez (GPU/CPU compartilhada); quem espera demais recebe 503."""

    def __init__(self, detector):
        self.detector = detector
        self.trava = threading.Lock()

    def ler(self, img: np.ndarray, linhas: list[str] | None) -> dict | None:
        if not self.trava.acquire(timeout=ESPERA_MAX_S):
            return None
        try:
            inicio = time.perf_counter()
            r = self.detector.detectar(img, linhas)
            latencia = int((time.perf_counter() - inicio) * 1000)
        finally:
            self.trava.release()
        onibus = [c for c in r.caixas if c[0] == "onibus"]
        letreiros = sorted((c for c in r.caixas if c[0] == "letreiro"), key=lambda c: -c[1])
        leituras = []
        texto = r.leitura.texto_confirmado() if r.leitura else None
        if texto:
            leitura = {"texto": texto, "confianca": round(float(r.leitura.confianca), 3),
                       "validada": bool(linhas) and r.leitura.validada}
            if letreiros:
                _, _, x1, y1, x2, y2 = letreiros[0]
                leitura["caixa"] = [int(x1), int(y1), int(x2 - x1), int(y2 - y1)]
            leituras.append(leitura)
        return {
            "modelo": NOME_MODELO,
            "latencia_ms": latencia,
            "leituras": leituras,
            "deteccoes": {"onibus": len(onibus), "letreiros": len(letreiros)},
            "linhas_validadas": linhas is not None,
        }


def detector_real():
    """Carrega o YOLO treinado e o EasyOCR. GPU: PF_VISAO_GPU=auto (padrão), 1 ou 0."""
    from detector import DetectorOnibus

    modo = os.getenv("PF_VISAO_GPU", "auto").lower()
    if modo == "auto":
        try:
            import torch
            gpu = bool(torch.cuda.is_available())
        except Exception:  # noqa: BLE001 - sem torch com CUDA, segue na CPU
            gpu = False
    else:
        gpu = modo in ("1", "true", "sim")
    pesos = os.getenv("PF_VISAO_PESOS", str(RAIZ / "modelos" / "best.pt"))
    conf = float(os.getenv("PF_VISAO_CONF", "0.35"))
    limiar = float(os.getenv("PF_VISAO_LIMIAR", "1.0"))
    det = DetectorOnibus(pesos, conf=conf, gpu=gpu, rejeitar_ambiguas=True, limiar=limiar, ler_fora_da_lista=True)
    det.dispositivo = "cuda" if gpu else "cpu"
    # Aquece YOLO e OCR com uma foto de exemplo: a primeira conferência real não paga o custo de inicialização.
    amostra = RAIZ / "amostras" / "imagens" / "demo" / "01_647P-10.jpg"
    if amostra.exists():
        det.detectar(cv2.imread(str(amostra)), ["647P-10"])
    return det


def criar_app(fabrica: Callable[[], object] = detector_real, chave: str | None = None) -> FastAPI:
    estado: dict = {"leitor": None, "erro": None, "dispositivo": None}

    def chave_atual() -> str:
        return chave if chave is not None else os.getenv("PF_VISAO_SERVICO_CHAVE", "")

    @asynccontextmanager
    async def ciclo(_app: FastAPI):
        if len(chave_atual()) < 16:
            raise RuntimeError("Defina PF_VISAO_SERVICO_CHAVE com pelo menos 16 caracteres.")

        def carregar():
            try:
                det = fabrica()
                estado["dispositivo"] = getattr(det, "dispositivo", None)
                estado["leitor"] = Leitor(det)
                log.info("Modelo de visão carregado (%s)", estado["dispositivo"] or "?")
            except Exception as e:  # noqa: BLE001 - o /health mostra a falha; o processo continua de pé
                estado["erro"] = e.__class__.__name__
                log.exception("Falha ao carregar o modelo de visão")

        threading.Thread(target=carregar, daemon=True).start()
        yield

    app = FastAPI(title="Ponto Falante · Visão (leitura de letreiro)", version=VERSAO, lifespan=ciclo,
                  docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware("http")
    async def protecao(request: Request, call_next):
        if request.url.path == "/v1/letreiro":
            recebida = request.headers.get("x-api-key", "")
            if not recebida or not hmac.compare_digest(recebida.encode(), chave_atual().encode()):
                return _erro(401, "CHAVE_INVALIDA", "Chave ausente ou inválida.")
            try:
                tamanho = int(request.headers.get("content-length", "0"))
            except ValueError:
                tamanho = 0
            if tamanho > MAX_BYTES + 64 * 1024:
                return _erro(413, "IMAGEM_GRANDE", "A imagem pode ter no máximo 2 MB.")
        return await call_next(request)

    @app.get("/health")
    def saude():
        if estado["leitor"] is not None:
            return {"status": "ok", "modelo": NOME_MODELO, "dispositivo": estado["dispositivo"]}
        status = "erro" if estado["erro"] else "carregando"
        return JSONResponse(status_code=503, content={"status": status, "modelo": NOME_MODELO})

    @app.get("/identidade")
    def identidade(desafio: str = Query(..., max_length=128)):
        """Prova que este serviço conhece a chave sem enviá-la (usado pelo backend antes de aceitar o túnel)."""
        if not DESAFIO.match(desafio):
            return _erro(400, "DESAFIO_INVALIDO", "Desafio inválido.")
        return {"prova": prova_identidade(chave_atual(), desafio)}

    @app.post("/v1/letreiro")
    def ler_letreiro(imagem: UploadFile = File(...), linhas: str | None = Form(None)):
        leitor: Leitor | None = estado["leitor"]
        if leitor is None:
            return _erro(503, "MODELO_INDISPONIVEL", "O modelo ainda está carregando.")
        dados = imagem.file.read(MAX_BYTES + 1)
        if len(dados) > MAX_BYTES:
            return _erro(413, "IMAGEM_GRANDE", "A imagem pode ter no máximo 2 MB.")
        img = decodificar(dados)
        del dados
        if img is None:
            return _erro(415, "IMAGEM_INVALIDA", "Envie uma foto JPEG ou PNG de até 4096 px.")
        resposta = leitor.ler(img, linhas_validas(linhas))
        del img
        if resposta is None:
            return _erro(503, "OCUPADO", "O modelo está ocupado; tente de novo em instantes.")
        log.info("letreiro: %d ms, onibus=%d, letreiros=%d, leituras=%d", resposta["latencia_ms"],
                 resposta["deteccoes"]["onibus"], resposta["deteccoes"]["letreiros"], len(resposta["leituras"]))
        return resposta

    return app


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
app = criar_app()

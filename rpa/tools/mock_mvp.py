"""Mock da API do MVP (imita os endpoints do Spring Boot usados pelo robô).

Serve para desenvolver, testar e gravar a demo mesmo sem o backend real.
Os dados são SIMULADOS (rede fictícia, semente fixa por data) e vêm marcados
com fonte="simulador", exatamente como o contrato do grupo pede.

    uvicorn tools.mock_mvp:app --port 8080          (dentro da pasta rpa/)

Endpoints:
    GET  /historico?data=AAAA-MM-DD   passagens do dia (com ~3% inválidos e ~3% duplicados de propósito)
    POST /boletim                      recebe o boletim do robô (exige X-API-Key se MOCK_API_KEY existir)
    GET  /boletim                      último boletim recebido
    GET  /health
    POST /admin/falha?ativo=true       liga/desliga uma "queda" do /historico (para demonstrar a exceção)
"""
from __future__ import annotations

import hashlib
import os
import random
from datetime import date
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Query

app = FastAPI(title="Mock do MVP Ponto Falante (dados simulados)")

# Perfil de cada linha fictícia: (atraso médio, desvio, intervalo programado em min)
PERFIS = {
    "1001-10": (14, 5, 15),   # tende a CRÍTICA
    "1002-10": (7, 3, 15),    # tende a ATENÇÃO
    "1003-10": (2, 2, 12),    # normal
    "1004-10": (1, 2, 10),    # normal
    "1005-10": (3, 2, 20),    # normal
}
PONTOS = {
    "1001-10": ["PF-0001", "PF-0002", "PF-0003"],
    "1002-10": ["PF-0004", "PF-0005", "PF-0006"],
    "1003-10": ["PF-0007", "PF-0008", "PF-0009"],
    "1004-10": ["PF-0010", "PF-0011", "PF-0012"],
    "1005-10": ["PF-0013", "PF-0014", "PF-0015"],
}
FAIXAS = [(6 * 60, 9 * 60), (17 * 60, 19 * 60)]   # picos da manhã e da tarde

estado: dict[str, Any] = {"falha": os.environ.get("MOCK_FALHA") == "1", "boletim": None}


def _hhmm(minutos: int) -> str:
    minutos %= 1440
    return f"{minutos // 60:02d}:{minutos % 60:02d}"


def gerar_historico(data_ref: str, taxa_invalidos: float = 0.03, taxa_duplicados: float = 0.03) -> list[dict]:
    rng = random.Random(f"ponto-falante-{data_ref}")      # semente fixa: mesma data, mesmos dados
    registros: list[dict] = []
    for linha, (media, desvio, intervalo) in PERFIS.items():
        for i_ponto, ponto in enumerate(PONTOS[linha]):
            n = 0
            for ini, fim in FAIXAS:
                for prog in range(ini + 3 * i_ponto, fim, intervalo):
                    n += 1
                    atraso = round(rng.gauss(media, desvio))
                    veiculo = hashlib.sha256(f"{linha}-{n}".encode()).hexdigest()[:12]
                    registros.append({
                        "ponto": ponto, "linha": linha, "sentido": "Centro",
                        "veiculo": veiculo,
                        "programado_em": _hhmm(prog), "previsto_em": _hhmm(prog + atraso),
                        "minutos": 0, "acessivel": rng.random() < 0.6, "fonte": "simulador",
                        "atualizado_em": f"{data_ref}T{_hhmm(prog + atraso)}:00-03:00",
                    })
    # Registros inválidos de propósito (para as regras de qualidade terem o que barrar)
    for _ in range(max(1, int(len(registros) * taxa_invalidos))):
        r = dict(rng.choice(registros))
        tipo = rng.choice(["linha", "vazio", "horario"])
        if tipo == "linha":
            r["linha"] = "9999-99"
        elif tipo == "vazio":
            r["ponto"] = ""
        else:
            h, m = map(int, r["programado_em"].split(":"))
            r["previsto_em"] = _hhmm(h * 60 + m - 90)
        registros.append(r)
    # Duplicados de propósito (mesmo veículo, ponto e minuto)
    for _ in range(max(1, int(len(registros) * taxa_duplicados))):
        registros.append(dict(rng.choice(registros)))
    rng.shuffle(registros)
    return registros


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "mock": True}


@app.get("/historico")
def historico(data: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$")) -> list[dict]:
    if estado["falha"]:
        raise HTTPException(503, "MVP simulando indisponibilidade")
    date.fromisoformat(data)
    return gerar_historico(data)


@app.post("/boletim", status_code=201)
def receber_boletim(boletim: dict, x_api_key: str | None = Header(default=None)) -> dict:
    chave = os.environ.get("MOCK_API_KEY")
    if chave and x_api_key != chave:
        raise HTTPException(401, "chave inválida")
    estado["boletim"] = boletim
    return {"recebido": True, "data_referencia": boletim.get("data_referencia")}


@app.get("/boletim")
def obter_boletim() -> dict:
    if estado["boletim"] is None:
        raise HTTPException(404, "nenhum boletim publicado ainda")
    return estado["boletim"]


@app.post("/admin/falha")
def alternar_falha(ativo: bool = True) -> dict:
    estado["falha"] = ativo
    return {"falha": ativo}

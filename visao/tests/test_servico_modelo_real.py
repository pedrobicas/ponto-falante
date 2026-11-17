"""Ponta a ponta com o modelo REAL (YOLO + EasyOCR) pelo HTTP, nas 6 fotos de demonstração.

Lento e pesado (~1,5 GB de RAM na CPU): só roda com PF_VISAO_TESTE_REAL=1 e as bibliotecas instaladas.
    PF_VISAO_TESTE_REAL=1 python -m pytest -q tests/test_servico_modelo_real.py
"""
import importlib.util
import os
import sys
import time
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

pytestmark = pytest.mark.skipif(
    os.getenv("PF_VISAO_TESTE_REAL") != "1" or importlib.util.find_spec("ultralytics") is None
    or importlib.util.find_spec("easyocr") is None,
    reason="defina PF_VISAO_TESTE_REAL=1 e instale ultralytics + easyocr")

CHAVE = "chave-de-teste-com-32-caracteres!"
# Linhas de um ponto simulado (as 5 do conjunto de demonstração + vizinhas parecidas, para testar ambiguidade).
LINHAS = "647P-10,5109-10,2100-10,288,695H-10,8000-10,647A-10,5110-10,695X-10"
ESPERADO = {
    "01_647P-10.jpg": "647P-10",
    "02_5109-10.jpg": "5109-10",
    "03_destino_sacoma.jpg": None,     # letreiro só com destino: não pode afirmar linha
    "04_2100-10.jpg": "2100",          # o letreiro mostra só "2100": não completa o sufixo
    "05_288.jpg": "288",
    "06_695H-10.jpg": "695H-10",
}


@pytest.fixture(scope="module")
def cliente():
    from fastapi.testclient import TestClient
    from servico import app as servico
    with TestClient(servico.criar_app(chave=CHAVE)) as c:
        for _ in range(600):
            if c.get("/health").status_code == 200:
                break
            time.sleep(0.5)
        assert c.get("/health").status_code == 200, "modelo não carregou"
        yield c


def test_linha_que_nao_passa_no_ponto_nao_vira_outra(cliente):
    """Achado de 17/11: no ponto da Av. Paulista (sem 647P-10) a foto do 647P-10 virava 478P-10 no limiar 0,75."""
    dados = (RAIZ / "amostras" / "imagens" / "demo" / "01_647P-10.jpg").read_bytes()
    r = cliente.post("/v1/letreiro", headers={"X-API-Key": CHAVE},
                     files={"imagem": ("01.jpg", dados, "image/jpeg")}, data={"linhas": "478P-10,875A-10,875C-10,6450-10"})
    leituras = r.json()["leituras"]
    assert [l["texto"] for l in leituras] in ([], ["647P-10"])
    assert all(l["validada"] is False for l in leituras)


@pytest.mark.parametrize("arquivo,esperado", ESPERADO.items())
def test_foto_real(cliente, arquivo, esperado):
    dados = (RAIZ / "amostras" / "imagens" / "demo" / arquivo).read_bytes()
    r = cliente.post("/v1/letreiro", headers={"X-API-Key": CHAVE},
                     files={"imagem": (arquivo, dados, "image/jpeg")}, data={"linhas": LINHAS})
    assert r.status_code == 200
    corpo = r.json()
    print(arquivo, corpo)
    assert corpo["deteccoes"]["letreiros"] >= 1
    textos = [l["texto"] for l in corpo["leituras"]]
    assert textos == ([esperado] if esperado else [])
    assert all(l["validada"] for l in corpo["leituras"])

"""Testa o cliente contra a API falsa de verdade (servidor HTTP local)."""
import json
import threading

import pytest

import api_fake
from cliente_api import ClienteAPI


@pytest.fixture()
def servidor():
    srv = api_fake.criar_servidor(0)  # porta livre escolhida pelo sistema
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    api_fake.DETECCOES.clear()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def test_busca_linhas_do_ponto(servidor):
    api = ClienteAPI(servidor)
    assert "8000-10" in api.linhas_do_ponto("260015039")


def test_envia_deteccao(servidor):
    api = ClienteAPI(servidor)
    assert api.enviar_deteccao("260015039", "8000-10", 0.87) is True
    assert api_fake.DETECCOES[0]["linha_lida"] == "8000-10"


def test_api_fora_guarda_na_fila_e_reenvia(servidor, tmp_path):
    fila = tmp_path / "fila.jsonl"
    fora = ClienteAPI("http://127.0.0.1:9", timeout=0.3, tentativas=1, fila=fila)
    assert fora.enviar_deteccao("P1", None, 0.5) is False
    assert json.loads(fila.read_text().splitlines()[0])["ponto"] == "P1"

    de_volta = ClienteAPI(servidor, fila=fila)
    assert de_volta.reenviar_fila() == 1
    assert not fila.exists()


def test_api_fora_devolve_lista_vazia_sem_quebrar():
    api = ClienteAPI("http://127.0.0.1:9", timeout=0.3, tentativas=1)
    assert api.linhas_do_ponto("P1") == []

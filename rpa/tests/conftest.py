"""Fixtures: sobe o mock do MVP num servidor HTTP real (porta livre) e cria
uma configuração isolada em pasta temporária para cada teste."""
from __future__ import annotations

import shutil
import socket
import threading
import time
from pathlib import Path

import pytest
import uvicorn

from pf_rpa.config import carregar
from tools import mock_mvp

RAIZ = Path(__file__).resolve().parents[1]


def _porta_livre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def mock_url():
    porta = _porta_livre()
    servidor = uvicorn.Server(uvicorn.Config(mock_mvp.app, host="127.0.0.1", port=porta, log_level="warning"))
    t = threading.Thread(target=servidor.run, daemon=True)
    t.start()
    for _ in range(100):
        if servidor.started:
            break
        time.sleep(0.05)
    yield f"http://127.0.0.1:{porta}"
    servidor.should_exit = True
    t.join(timeout=5)


@pytest.fixture(autouse=True)
def estado_mock_limpo():
    mock_mvp.estado.update({"falha": False, "boletim": None})
    yield


@pytest.fixture
def cfg(tmp_path, mock_url, monkeypatch):
    """Config real do projeto, apontando para o mock e gravando em pasta temporária."""
    (tmp_path / "config").mkdir()
    shutil.copy(RAIZ / "config" / "monitoramento.yaml", tmp_path / "config")
    shutil.copytree(RAIZ / "data", tmp_path / "data")
    monkeypatch.setenv("MVP_URL", mock_url)
    monkeypatch.setenv("RPA_BACKOFF", "0")       # sem esperar entre tentativas nos testes
    monkeypatch.delenv("RPA_API_KEY", raising=False)
    monkeypatch.delenv("MOCK_API_KEY", raising=False)
    return carregar(tmp_path / "config" / "monitoramento.yaml")

import os
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts/integracao"
sys.path.insert(0, str(SCRIPTS))


def test_configuracao_backend_carrega_env_sem_executar_e_usa_https(tmp_path, monkeypatch):
    from rodar_backend import preparar_ambiente
    for key in ("SPTRANS_BASE_URL", "SPTRANS_TOKEN", "SPRING_DATASOURCE_PASSWORD", "POSTGRES_PASSWORD"):
        monkeypatch.delenv(key, raising=False)
    caminho = tmp_path / ".env"
    caminho.write_text('SPTRANS_TOKEN="$(nao-executar)"\nPOSTGRES_PASSWORD=senha-local\n', encoding="utf-8")
    env = preparar_ambiente(caminho)
    assert env["SPTRANS_TOKEN"] == "$(nao-executar)"
    assert env["SPTRANS_BASE_URL"] == "https://api.olhovivo.sptrans.com.br/v2.1"
    assert env["SPRING_DATASOURCE_PASSWORD"] == "senha-local"
    assert "SPTRANS_TOKEN" not in os.environ


def test_configuracao_backend_preserva_ambiente_seguro(tmp_path, monkeypatch):
    from rodar_backend import preparar_ambiente
    monkeypatch.setenv("SPTRANS_TOKEN", "ambiente-seguro")
    monkeypatch.setenv("SPRING_DATASOURCE_PASSWORD", "senha-ambiente")
    caminho = tmp_path / ".env"
    caminho.write_text('SPTRANS_TOKEN=arquivo\nPOSTGRES_PASSWORD=arquivo\n', encoding="utf-8")
    env = preparar_ambiente(caminho)
    assert env["SPTRANS_TOKEN"] == "ambiente-seguro"
    assert env["SPRING_DATASOURCE_PASSWORD"] == "senha-ambiente"


def test_configuracao_backend_rejeita_http_externo(tmp_path, monkeypatch):
    from rodar_backend import preparar_ambiente
    monkeypatch.setenv("SPTRANS_BASE_URL", "http://api.olhovivo.sptrans.com.br/v2.1")
    with pytest.raises(ValueError, match="HTTPS"):
        preparar_ambiente(tmp_path / ".env")

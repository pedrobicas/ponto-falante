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


def test_demo_preserva_arquivo_e_desativa_chave_so_no_processo_filho(tmp_path, monkeypatch):
    from rodar_backend import preparar_ambiente
    for key in ("PF_SPTRANS_MODO", "SPTRANS_TOKEN", "SPTRANS_BASE_URL"):
        monkeypatch.delenv(key, raising=False)
    caminho = tmp_path / ".env"
    texto = 'SPTRANS_TOKEN=nao-enviar\nPF_SPTRANS_MODO=demo\n'
    caminho.write_text(texto, encoding="utf-8")
    env = preparar_ambiente(caminho)
    assert env["SPTRANS_TOKEN"] == ""
    assert caminho.read_text(encoding="utf-8") == texto


def test_launcher_normaliza_token_igual_ao_diagnostico(tmp_path, monkeypatch):
    from rodar_backend import preparar_ambiente
    for key in ("PF_SPTRANS_MODO", "SPTRANS_TOKEN", "SPTRANS_BASE_URL"):
        monkeypatch.delenv(key, raising=False)
    caminho = tmp_path / ".env"
    caminho.write_text('SPTRANS_TOKEN="  token-local  "\n', encoding="utf-8")
    assert preparar_ambiente(caminho)["SPTRANS_TOKEN"] == "token-local"

"""O launcher local deve ligar o Spring à GenAI mesmo com GENAI_URL vazia no .env."""
import importlib.util
import sys
from pathlib import Path

import pytest

PASTA = Path(__file__).resolve().parents[2] / "integracao"


@pytest.mark.parametrize("url", [None, "", "   ", "http://host.docker.internal:8001"])
def test_launcher_encaminha_genai_local_sem_trocar_chave(monkeypatch, tmp_path, url):
    monkeypatch.syspath_prepend(str(PASTA))
    spec = importlib.util.spec_from_file_location("launcher_local_teste", PASTA / "rodar_mvp_local.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    jar = tmp_path / "backend/target/pontofalante.jar"
    jar.parent.mkdir(parents=True)
    jar.touch()
    local = tmp_path / ".validation/local"
    local.mkdir(parents=True)
    (local / "classpath.txt").write_text("dependencia-teste", encoding="utf-8")
    env = {"GENAI_API_KEY": "chave-existente", "RPA_API_KEY": "rpa-existente", "PF_SALT": "sal-existente"}
    if url is not None:
        env["GENAI_URL"] = url
    monkeypatch.setattr(mod, "RAIZ", tmp_path)
    monkeypatch.setattr(mod, "carregar", lambda _: dict(env))
    monkeypatch.setattr(mod, "executar", lambda *args: None)
    capturado = {}
    def iniciar(cmd, cwd, env):
        capturado.update(env)
        return 0
    monkeypatch.setattr(mod.subprocess, "call", iniciar)
    monkeypatch.setattr(sys, "argv", ["rodar_mvp_local.py"])
    assert mod.main() == 0
    assert capturado["GENAI_URL"] == "http://127.0.0.1:8001"
    assert capturado["GENAI_API_KEY"] == "chave-existente"
    assert capturado["PF_SPTRANS_MODO"] == "demo"

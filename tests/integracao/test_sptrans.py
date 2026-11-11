"""Executa a ferramenta real contra uma API HTTP local, sem token externo."""
import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/integracao/testar_sptrans.py"
TOKEN = "teste-local+/&?nao-exibir"


@pytest.fixture
def api():
    state = {"auth": True, "cookie": True, "get_status": 200, "calls": []}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            state["calls"].append(("POST", self.path, self.headers.get("Cookie")))
            self.send_response(state.get("auth_status", 200))
            self.send_header("Content-Type", state.get("content_type", "application/json"))
            self.send_header("Server", state.get("server", "teste-local"))
            self.send_header("X-Request-ID", TOKEN)
            if state.get("redirect"):
                self.send_header("Location", state["redirect"])
            if state["cookie"]:
                self.send_header("Set-Cookie", "apiCredentials=sessao-local; Path=/; HttpOnly")
            self.end_headers()
            self.wfile.write(state.get("auth_body", json.dumps(state["auth"]).encode()))

        def do_GET(self):
            state["calls"].append(("GET", self.path, self.headers.get("Cookie")))
            self.send_response(state["get_status"])
            self.send_header("Content-Type", state.get("content_type", "application/json"))
            self.end_headers()
            self.wfile.write(state.get("get_body", json.dumps(state.get("lines", [{"cl": 1273, "lt": "8000"}])).encode()))

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}/v2.1", state
    server.shutdown()
    server.server_close()
    thread.join(timeout=3)


def run(tmp_path, base, content=None, extra_env=None):
    env_file = tmp_path / ".env"
    if content is not None:
        env_file.write_text(content, encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if not k.startswith("SPTRANS_")}
    env.update(extra_env or {})
    return subprocess.run([sys.executable, str(SCRIPT), "--env-file", str(env_file),
                           "--base-url", base], env=env, capture_output=True, text=True, timeout=10)


def test_autentica_codifica_token_e_reutiliza_cookie(api, tmp_path):
    base, state = api
    result = run(tmp_path, base, f'SPTRANS_TOKEN="{TOKEN}"\n')
    assert result.returncode == 0, result.stderr
    assert "1 linha" in result.stdout
    assert parse_qs(urlsplit(state["calls"][0][1]).query)["token"] == [TOKEN]
    assert state["calls"][1][2] == "apiCredentials=sessao-local"
    assert TOKEN not in result.stdout + result.stderr
    assert "sessao-local" not in result.stdout + result.stderr


@pytest.mark.parametrize("change", [{"auth": False}, {"auth": "true"}, {"cookie": False},
                                    {"get_status": 401}, {"get_status": 500}, {"lines": {"erro": TOKEN}}])
def test_recusa_falhas_sem_expor_token(api, tmp_path, change):
    base, state = api
    state.update(change)
    result = run(tmp_path, base, f'SPTRANS_TOKEN="{TOKEN}"\n')
    assert result.returncode != 0
    assert result.stderr.startswith("SPTrans:")
    assert TOKEN not in result.stdout + result.stderr
    assert "sessao-local" not in result.stdout + result.stderr
    assert "Traceback" not in result.stderr


def test_ambiente_tem_prioridade_sobre_arquivo(api, tmp_path):
    base, state = api
    result = run(tmp_path, base, "SPTRANS_TOKEN=arquivo\n", {"SPTRANS_TOKEN": TOKEN})
    assert result.returncode == 0, result.stderr
    assert parse_qs(urlsplit(state["calls"][0][1]).query)["token"] == [TOKEN]


def test_sem_token_nao_faz_requisicao(api, tmp_path):
    base, state = api
    result = run(tmp_path, base)
    assert result.returncode != 0
    assert "SPTRANS_TOKEN" in result.stderr
    assert state["calls"] == []


def test_rejeita_http_fora_de_loopback(tmp_path):
    result = run(tmp_path, "http://api.olhovivo.sptrans.com.br/v2.1", "SPTRANS_TOKEN=segredo\n")
    assert result.returncode != 0
    assert "HTTPS" in result.stderr
    assert "segredo" not in result.stderr


def test_env_invalido_nao_expoe_conteudo(api, tmp_path):
    base, state = api
    result = run(tmp_path, base, f"linha invalida {TOKEN}\n")
    assert result.returncode != 0
    assert TOKEN not in result.stdout + result.stderr
    assert state["calls"] == []


def test_403_no_login_identifica_etapa_e_metadados_sem_expor_resposta(api, tmp_path):
    base, state = api
    state.update(auth_status=403, content_type="text/html; charset=utf-8", server="Microsoft-IIS/10.0",
                 auth_body=f"<html><h1>403 Forbidden</h1>{TOKEN} apiCredentials=sessao-local</html>".encode())
    result = run(tmp_path, base, f'SPTRANS_TOKEN="{TOKEN}"\n')
    output = result.stdout + result.stderr
    assert result.returncode == 1
    assert "etapa=login" in output
    assert "HTTP 403" in output
    assert "tipo=text/html" in output
    assert "servidor=IIS" in output
    assert "categoria=HTML_403_GENERICO" in output
    assert "bytes_lidos=" in output
    assert len(state["calls"]) == 1
    for segredo in (TOKEN, "sessao-local", "apiCredentials", "token=", "X-Request-ID"):
        assert segredo not in output


def test_403_na_consulta_preserva_evidencia_de_login_valido(api, tmp_path):
    base, state = api
    state.update(get_status=403, content_type="text/html", get_body=b"<h1>403 Forbidden</h1>")
    result = run(tmp_path, base, f"SPTRANS_TOKEN={TOKEN}\n")
    output = result.stdout + result.stderr
    assert result.returncode == 1
    assert "etapa=login; HTTP 200; autenticacao=OK" in output
    assert "etapa=consulta_linhas; HTTP 403" in output
    assert state["calls"][1][2] == "apiCredentials=sessao-local"


def test_nao_segue_redirecionamento_nem_expoe_location(api, tmp_path):
    base, state = api
    state.update(auth_status=302, redirect=base + "/outro?token=" + TOKEN)
    result = run(tmp_path, base, f"SPTRANS_TOKEN={TOKEN}\n")
    output = result.stdout + result.stderr
    assert result.returncode == 1
    assert "etapa=login; HTTP 302" in output
    assert "redirecionamento=presente" in output
    assert TOKEN not in output and "token=" not in output and "/outro" not in output
    assert len(state["calls"]) == 1


def test_normaliza_so_espacos_externos_do_token(api, tmp_path):
    base, state = api
    result = run(tmp_path, base, f'SPTRANS_TOKEN="  {TOKEN}  "\n')
    assert result.returncode == 0
    assert "ajuste_externo=sim" in result.stdout
    assert parse_qs(urlsplit(state["calls"][0][1]).query)["token"] == [TOKEN]


def test_rejeita_espaco_interno_sem_enviar_token(api, tmp_path):
    base, state = api
    result = run(tmp_path, base, 'SPTRANS_TOKEN="chave com espaco"\n')
    assert result.returncode == 1
    assert "espacos internos" in result.stderr
    assert state["calls"] == []


def test_json_invalido_nao_imprime_corpo_remoto(api, tmp_path):
    base, state = api
    state.update(auth_body=f"<html>{TOKEN} sessao-local</html>".encode(), content_type="text/html")
    result = run(tmp_path, base, f"SPTRANS_TOKEN={TOKEN}\n")
    output = result.stdout + result.stderr
    assert result.returncode == 1
    assert "etapa=login; HTTP 200" in output
    assert "categoria=JSON_INVALIDO" in output
    assert TOKEN not in output and "sessao-local" not in output

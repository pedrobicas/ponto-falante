"""Cliente no contrato do MVP (Spring Boot): rotas /api/..., chave X-API-Key e linha nula quando não leu."""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from cliente_api import ClienteAPI

RECEBIDAS: list = []


class MvpFalso(BaseHTTPRequestHandler):
    linhas_cadastro: list = [{"letreiro": "875A-10"}, {"letreiro": "6450-10"}]

    def log_message(self, *a):
        pass

    def _json(self, codigo, corpo):
        dados = json.dumps(corpo).encode()
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(dados)))
        self.end_headers()
        self.wfile.write(dados)

    def do_GET(self):
        if self.path == "/api/pontos/70016916/linhas":
            return self._json(200, {"fonte": "GTFS_SPTRANS", "codigo": 70016916, "linhas": self.linhas_cadastro})
        if self.path == "/api/pontos/70016916/previsoes":
            return self._json(200, {"onibus": [{"letreiro": "8000-10", "minutos": 3}]})
        self._json(404, {})

    def do_POST(self):
        corpo = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if self.path != "/api/integracoes/visao/deteccoes":
            return self._json(404, {})
        if self.headers.get("X-API-Key") != "chave-visao":
            return self._json(401, {"codigo": "CHAVE_INVALIDA"})
        RECEBIDAS.append(corpo)
        self._json(202, {"id": len(RECEBIDAS), "frase_falada": "ok"})


@pytest.fixture()
def mvp():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), MvpFalso)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    RECEBIDAS.clear()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def test_linhas_do_ponto_pelo_cadastro(mvp):
    api = ClienteAPI(mvp, contrato="mvp", chave="chave-visao")
    assert api.linhas_do_ponto("70016916") == ["6450-10", "875A-10"]


def test_sem_cadastro_usa_as_previsoes(mvp, monkeypatch):
    monkeypatch.setattr(MvpFalso, "linhas_cadastro", [])
    assert ClienteAPI(mvp, contrato="mvp", chave="chave-visao").linhas_do_ponto("70016916") == ["8000-10"]


def test_envia_no_formato_do_mvp(mvp, tmp_path):
    api = ClienteAPI(mvp, contrato="mvp", chave="chave-visao", dispositivo="camera-teste", fila=tmp_path / "f.jsonl")
    assert api.enviar_deteccao("70016916", "875A-10", 0.812) is True
    assert api.enviar_deteccao("70016916", None, 0.7) is True       # "não consegui ler a linha"
    assert RECEBIDAS[0]["ponto"] == 70016916 and RECEBIDAS[0]["linha_reconhecida"] == "875A-10"
    assert RECEBIDAS[0]["dispositivo"] == "camera-teste" and "capturado_em" in RECEBIDAS[0]
    assert RECEBIDAS[1]["linha_reconhecida"] is None


def test_chave_errada_vai_para_a_fila(mvp, tmp_path):
    api = ClienteAPI(mvp, contrato="mvp", chave="errada", fila=tmp_path / "f.jsonl", tentativas=1)
    assert api.enviar_deteccao("70016916", "875A-10", 0.8) is False
    assert (tmp_path / "f.jsonl").exists() and RECEBIDAS == []
    api.chave = "chave-visao"
    assert api.reenviar_fila() == 1 and RECEBIDAS[0]["linha_reconhecida"] == "875A-10"


def test_contrato_desconhecido():
    with pytest.raises(ValueError):
        ClienteAPI("http://x", contrato="outro")

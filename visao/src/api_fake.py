"""
API falsa do Ponto Falante, só para testar a Visão sem depender do MVP do grupo.
Implementa o mesmo contrato do contrato comum (partes usadas pela Visão). Sem dependências.

  python src/api_fake.py            # sobe em http://localhost:8000
  python src/api_fake.py --porta 8010
  python src/api_fake.py --linhas 647P-10,576C-10   # linhas que "passam" no ponto

Quando o MVP real estiver no ar, basta apontar PONTO_FALANTE_API para ele.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

LINHAS_DEMO = ["8000-10", "875A-10", "6450-10", "N101-11", "609J-10"]
DETECCOES: list[dict] = []


class Handler(BaseHTTPRequestHandler):
    def _json(self, status: int, corpo):
        dados = json.dumps(corpo, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(dados)))
        self.end_headers()
        self.wfile.write(dados)

    def do_GET(self):
        if self.path == "/health":
            return self._json(200, {"status": "ok"})
        m = re.fullmatch(r"/pontos/([^/]+)/previsoes", self.path)
        if m:
            agora = datetime.now(timezone.utc).isoformat()
            prev = [{"ponto": m.group(1), "linha": l, "sentido": "1", "programado_em": "--:--",
                     "previsto_em": "--:--", "minutos": 2 + i * 3, "acessivel": True,
                     "fonte": "simulador", "atualizado_em": agora} for i, l in enumerate(LINHAS_DEMO)]
            return self._json(200, prev)
        if self.path == "/deteccoes":
            return self._json(200, DETECCOES)
        self._json(404, {"erro": "não encontrado"})

    def do_POST(self):
        if self.path != "/deteccoes":
            return self._json(404, {"erro": "não encontrado"})
        tamanho = int(self.headers.get("Content-Length", 0))
        try:
            corpo = json.loads(self.rfile.read(tamanho) or b"{}")
        except json.JSONDecodeError:
            return self._json(400, {"erro": "JSON inválido"})
        if "ponto" not in corpo or "confianca" not in corpo:
            return self._json(422, {"erro": "campos obrigatórios: ponto, confianca"})
        DETECCOES.append(corpo)
        print("Detecção recebida:", corpo, flush=True)
        self._json(201, {"ok": True, "total": len(DETECCOES)})

    def log_message(self, *args):  # silencia o log padrão do http.server
        pass


def criar_servidor(porta: int = 8000) -> ThreadingHTTPServer:
    return ThreadingHTTPServer(("127.0.0.1", porta), Handler)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--porta", type=int, default=8000)
    ap.add_argument("--linhas", default="", help="linhas do ponto separadas por vírgula")
    args = ap.parse_args()
    porta = args.porta
    if args.linhas:
        LINHAS_DEMO[:] = [l.strip() for l in args.linhas.split(",") if l.strip()]
    print(f"API falsa em http://localhost:{porta}  (Ctrl+C para sair)")
    criar_servidor(porta).serve_forever()

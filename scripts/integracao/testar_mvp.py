"""Smoke test HTTP do MVP publicado ou local, sem modificar dados."""
import argparse
import base64
import hashlib
import json
import re
import sys
from urllib.parse import urlencode, urljoin, urlsplit
from urllib.request import urlopen


def verificar(base: str, timeout: float = 20, angular: bool = True) -> None:
    base = base.rstrip("/")

    def texto(caminho):
        with urlopen(base + caminho, timeout=timeout) as r:  # nosemgrep -- URL do MVP informada pelo operador
            return r.read().decode("utf-8")

    def pagina(caminho):
        with urlopen(base + caminho, timeout=timeout) as r:  # nosemgrep -- URL do MVP informada pelo operador
            html = r.read().decode("utf-8")
            politica = r.headers.get("Content-Security-Policy", "")
        diretivas = {d.split()[0]: d.split()[1:] for d in politica.split(";") if d.split()}
        fontes = diretivas.get("script-src-elem", diretivas.get("script-src", diretivas.get("default-src")))
        if fontes is not None:
            for atributos, codigo in re.findall(r"<script\b([^>]*)>([\s\S]*?)</script>", html, re.I):
                if re.search(r"\bsrc\s*=", atributos) or not codigo.strip():
                    continue
                digest = base64.b64encode(hashlib.sha256(codigo.encode()).digest()).decode()
                if "'unsafe-inline'" not in fontes and f"'sha256-{digest}'" not in fontes:
                    raise ValueError("A CSP bloqueia um script inline do build Angular.")
        return html

    def dado(caminho):
        return json.loads(texto(caminho))

    if dado("/actuator/health").get("status") != "UP":
        raise ValueError("Saude do backend/banco nao esta UP.")
    estado = dado("/api/status")
    if estado.get("sptrans") not in {"DEMO", "REAL", "INDISPONIVEL"}:
        raise ValueError("Contrato de status SPTrans invalido.")
    if estado.get("assistente") not in {"DISPONIVEL", "INDISPONIVEL"}:
        raise ValueError("Contrato de status GenAI invalido.")
    pontos = dado("/api/pontos?" + urlencode({"busca": "paulista", "modo": "demo"}))
    if pontos.get("fonte") != "SIMULADO" or not pontos.get("pontos"):
        raise ValueError("Busca demonstrativa sem pontos identificados como SIMULADO.")
    codigo = pontos["pontos"][0]["codigo"]
    previsoes = dado(f"/api/pontos/{codigo}/previsoes?modo=demo")
    if (previsoes.get("fonte") != "SIMULADO" or previsoes.get("tipo") != "PREVISAO"
            or not isinstance(previsoes.get("onibus"), list) or not previsoes.get("frase_falada")):
        raise ValueError("Contrato das previsoes demonstrativas invalido.")
    if angular:
        for rota in ("/", "/sobre"):
            html = pagina(rota)
            if "<app-root" not in html.lower():
                raise ValueError("Angular compilado ou fallback de navegacao ausente.")
        scripts = re.findall(r'<script\b[^>]*\bsrc=[\"\']([^\"\']+)[\"\']', html, re.I)
        if not scripts:
            raise ValueError("HTML do Angular sem arquivos JavaScript.")
        for script in scripts:
            destino = urljoin(base + "/", script)
            if urlsplit(destino).netloc != urlsplit(base).netloc:
                raise ValueError("Arquivo JavaScript fora da origem do MVP.")
            with urlopen(destino, timeout=timeout) as r:  # nosemgrep -- URL do MVP informada pelo operador
                if "javascript" not in r.headers.get("Content-Type", "") or not r.read():
                    raise ValueError("Arquivo JavaScript ausente ou servido como HTML.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://localhost:8080")
    parser.add_argument("--api-only", action="store_true")
    parser.add_argument("--timeout", type=float, default=20)
    args = parser.parse_args()
    try:
        verificar(args.url, args.timeout, not args.api_only)
        print("MVP: saude, contratos e previsoes OK" + ("; Angular e navegacao OK." if not args.api_only else "."))
        return 0
    except ValueError as erro:
        print(f"MVP: {erro}", file=sys.stderr)
        return 1
    except Exception:
        print("MVP: verificacao falhou. Confira saude, contratos, build Angular e conectividade; detalhes omitidos.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

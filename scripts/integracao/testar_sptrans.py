"""Autentica na SPTrans e confirma uma consulta com a mesma sessao HTTP."""
import argparse
import http.cookiejar
import json
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPCookieProcessor, HTTPRedirectHandler, Request, build_opener

from ambiente import carregar

RAIZ = Path(__file__).resolve().parents[2]
BASE = "https://api.olhovivo.sptrans.com.br/v2.1"


class SemRedirecionamento(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def testar(token: str, base: str, busca: str, timeout: float) -> int:
    url = urlsplit(base)
    local = url.hostname in {"127.0.0.1", "localhost", "::1"}
    if url.scheme != "https" and not (url.scheme == "http" and local):
        raise ValueError("Use HTTPS para a SPTrans; HTTP somente em testes locais.")
    if not url.hostname or url.username or url.password or url.query or url.fragment:
        raise ValueError("SPTRANS_BASE_URL invalida.")
    cookies = http.cookiejar.CookieJar()
    cliente = build_opener(HTTPCookieProcessor(cookies), SemRedirecionamento())
    base = base.rstrip("/")
    login = Request(base + "/Login/Autenticar?" + urlencode({"token": token}), data=b"", method="POST")
    with cliente.open(login, timeout=timeout) as resposta:
        autorizado = json.load(resposta)
    if autorizado is not True:
        raise ValueError("Autenticacao recusada. Confirme cadastro e token no portal da SPTrans.")
    if not list(cookies):
        raise ValueError("Autenticacao sem cookie de sessao; nao foi possivel confirmar o acesso.")
    consulta = base + "/Linha/Buscar?" + urlencode({"termosBusca": busca})
    with cliente.open(consulta, timeout=timeout) as resposta:
        linhas = json.load(resposta)
    if not isinstance(linhas, list):
        raise ValueError("A consulta autenticada nao retornou uma lista de linhas.")
    return len(linhas)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=RAIZ / ".env")
    parser.add_argument("--base-url", help="Padrao: SPTRANS_BASE_URL ou HTTPS oficial.")
    parser.add_argument("--busca", default="8000")
    parser.add_argument("--timeout", type=float, default=15)
    args = parser.parse_args()
    try:
        env = carregar(args.env_file)
        token = env.get("SPTRANS_TOKEN", "").strip()
        if not token:
            raise ValueError("Configure SPTRANS_TOKEN no .env local ou no ambiente seguro.")
        if args.timeout <= 0:
            raise ValueError("Timeout deve ser positivo.")
        quantidade = testar(token, args.base_url or env.get("SPTRANS_BASE_URL") or BASE,
                            args.busca, args.timeout)
        print(f"SPTrans: autenticacao OK; cookie confirmado; {quantidade} linha(s) recebida(s).")
        return 0
    except HTTPError as erro:
        print(f"SPTrans: falha HTTP {erro.code}; token, cookies e URL omitidos.", file=sys.stderr)
    except (URLError, TimeoutError, OSError):
        print("SPTrans: falha de rede/TLS ou leitura local; detalhes sensiveis omitidos.", file=sys.stderr)
    except json.JSONDecodeError:
        print("SPTrans: resposta JSON invalida; corpo omitido.", file=sys.stderr)
    except ValueError as erro:
        print(f"SPTrans: {erro}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

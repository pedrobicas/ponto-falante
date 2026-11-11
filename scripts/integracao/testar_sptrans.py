"""Autentica e consulta a SPTrans com diagnostico por etapa, sem expor credenciais."""
import argparse
import http.cookiejar
from http.client import HTTPException
import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPCookieProcessor, HTTPRedirectHandler, Request, build_opener, getproxies

from ambiente import carregar, normalizar_sptrans_token

RAIZ = Path(__file__).resolve().parents[2]
BASE = "https://api.olhovivo.sptrans.com.br/v2.1"
LIMITE_ERRO = 8192
LIMITE_JSON = 2_000_000
# Identifica a aplicação; clientes HTTP sem User-Agent próprio podem ser barrados por WAF.
USER_AGENT = "PontoFalante/1.0 (+https://github.com/pedrobicas/ponto-falante)"


class FalhaSptrans(Exception):
    """Contem exclusivamente metadados ja reduzidos a valores seguros."""


class SemRedirecionamento(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def resumo_resposta(status, headers, corpo, classificacao=None):
    tipo = (headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
    if tipo not in {"text/html", "text/plain", "application/json", "application/xml", "text/xml"}:
        tipo = "outro"
    banner = " ".join(headers.get_all("Server", [])).lower()
    servidor = next((nome for padrao, nome in (("microsoft-iis", "IIS"), ("cloudflare", "CLOUDFLARE"),
                    ("awselb", "AWS_ELB"), ("nginx", "NGINX"), ("apache", "APACHE"), ("envoy", "ENVOY"))
                    if padrao in banner), "outro")
    amostra = corpo[:LIMITE_ERRO].lower()
    categoria = "HTTP_ERRO"
    if status in {301, 302, 303, 307, 308}:
        categoria = "REDIRECIONAMENTO_NAO_SEGUIDO"
    elif any(m in amostra for m in (b"request blocked", b"requested url was rejected", b"mod_security", b"web application firewall")):
        categoria = "POLITICA_ACESSO_INDICADA"
    elif b"403.14" in amostra:
        categoria = "IIS_403_14"
    elif status == 403 and (tipo == "text/html" or b"<html" in amostra or b"<h1" in amostra):
        categoria = "HTML_403_GENERICO"
    elif tipo == "application/json":
        categoria = "JSON_ERRO"
    if classificacao is not None:
        categoria = classificacao
    codigo_cf = ""
    if tipo == "application/json":
        try:
            dados = json.loads(corpo[:LIMITE_ERRO])
            # Campos públicos do erro JSON do Cloudflare (código numérico e nome da regra), nunca o corpo inteiro.
            if isinstance(dados, dict) and isinstance(dados.get("error_code"), int):
                nome = str(dados.get("error_name", ""))[:40]
                codigo_cf = f"cloudflare_erro={dados['error_code']}; cloudflare_nome={nome}; "
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass
    return (f"categoria={categoria}; {codigo_cf}tipo={tipo}; servidor={servidor}; "
            f"bytes_lidos={min(len(corpo), LIMITE_ERRO)}; amostra_limitada={'sim' if len(corpo) > LIMITE_ERRO else 'nao'}; "
            f"redirecionamento={'presente' if headers.get('Location') else 'ausente'}; corpo=omitido")


def obter_json(cliente, requisicao, etapa, timeout):
    try:
        with cliente.open(requisicao, timeout=timeout) as resposta:
            status, headers = resposta.status, resposta.headers
            corpo = resposta.read(LIMITE_JSON + 1)
    except HTTPError as erro:
        try:
            corpo = erro.read(LIMITE_ERRO + 1)
        except (OSError, TimeoutError, HTTPException):
            corpo = b""
        finally:
            erro.close()
        raise FalhaSptrans(f"etapa={etapa}; HTTP {erro.code}; {resumo_resposta(erro.code, erro.headers, corpo)}") from None
    except (URLError, TimeoutError, OSError, HTTPException):
        raise FalhaSptrans(f"etapa={etapa}; categoria=REDE_OU_TLS; verificacao_TLS=ativa; detalhes=omitidos") from None
    if len(corpo) > LIMITE_JSON:
        raise FalhaSptrans(f"etapa={etapa}; HTTP {status}; categoria=RESPOSTA_EXCESSIVA; corpo=omitido")
    try:
        return json.loads(corpo), status, headers
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise FalhaSptrans(f"etapa={etapa}; HTTP {status}; "
                           f"{resumo_resposta(status, headers, corpo, 'JSON_INVALIDO')}") from None


def testar(token: str, base: str, busca: str, timeout: float, user_agent: str = USER_AGENT) -> int:
    token = normalizar_sptrans_token(token)
    url = urlsplit(base)
    local = url.hostname in {"127.0.0.1", "localhost", "::1"}
    if url.scheme != "https" and not (url.scheme == "http" and local):
        raise ValueError("Use HTTPS para a SPTrans; HTTP somente em testes locais.")
    if not url.hostname or url.username or url.password or url.query or url.fragment:
        raise ValueError("SPTRANS_BASE_URL invalida.")
    cookies = http.cookiejar.CookieJar()
    cliente = build_opener(HTTPCookieProcessor(cookies), SemRedirecionamento())
    base = base.rstrip("/")
    login = Request(base + "/Login/Autenticar?" + urlencode({"token": token}),
                    data=b"", method="POST", headers={"Accept": "application/json", "User-Agent": user_agent})
    autorizado, status, _ = obter_json(cliente, login, "login", timeout)
    if autorizado is not True:
        raise FalhaSptrans(f"etapa=login; HTTP {status}; categoria=AUTENTICACAO_RECUSADA; "
                           "confirme cadastro e chave no portal SPTrans; corpo=omitido")
    if not list(cookies):
        raise FalhaSptrans(f"etapa=login; HTTP {status}; categoria=SESSAO_AUSENTE; corpo=omitido")
    print(f"SPTrans: etapa=login; HTTP {status}; autenticacao=OK; sessao=preservada.", flush=True)
    consulta = Request(base + "/Linha/Buscar?" + urlencode({"termosBusca": busca}),
                       headers={"Accept": "application/json", "User-Agent": user_agent})
    linhas, status, _ = obter_json(cliente, consulta, "consulta_linhas", timeout)
    if not isinstance(linhas, list):
        raise FalhaSptrans(f"etapa=consulta_linhas; HTTP {status}; categoria=CONTRATO_INVALIDO; corpo=omitido")
    print(f"SPTrans: etapa=consulta_linhas; HTTP {status}; sessao=confirmada.", flush=True)
    return len(linhas)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=RAIZ / ".env")
    parser.add_argument("--base-url", help="Padrao: SPTRANS_BASE_URL ou HTTPS oficial.")
    parser.add_argument("--busca", default="8000")
    parser.add_argument("--timeout", type=float, default=15)
    parser.add_argument("--user-agent", default=USER_AGENT, help="Padrao: identificacao da aplicacao.")
    args = parser.parse_args()
    try:
        env = carregar(args.env_file)
        bruto = env.get("SPTRANS_TOKEN", "")
        token = normalizar_sptrans_token(bruto)
        if not token:
            raise ValueError("Configure SPTRANS_TOKEN no .env local ou no ambiente seguro.")
        if args.timeout <= 0:
            raise ValueError("Timeout deve ser positivo.")
        origem = "ambiente" if "SPTRANS_TOKEN" in os.environ else "arquivo"
        print(f"SPTrans: etapa=configuracao; origem={origem}; configurado=sim; "
              f"ajuste_externo={'sim' if bruto != token else 'nao'}; "
              f"proxy_https={'sim' if getproxies().get('https') else 'nao'}; verificacao_TLS=ativa.", flush=True)
        quantidade = testar(token, args.base_url or env.get("SPTRANS_BASE_URL") or BASE,
                            args.busca, args.timeout, args.user_agent)
        print(f"SPTrans: autenticacao OK; cookie confirmado; {quantidade} linha(s) recebida(s).")
        return 0
    except FalhaSptrans as erro:
        print(f"SPTrans: {erro}", file=sys.stderr)
    except (OSError, UnicodeError):
        print("SPTrans: etapa=configuracao; falha de leitura local; detalhes omitidos.", file=sys.stderr)
    except ValueError as erro:
        print(f"SPTrans: etapa=configuracao; {erro}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

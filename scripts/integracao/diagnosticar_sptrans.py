"""Matriz de variações do login Olho Vivo, sem expor a chave.

Lê SPTRANS_TOKEN (e SPTRANS_TOKEN_2, se existir) do .env, descreve só o formato da chave e testa
host, protocolo, versão e forma de envio. Nada da chave aparece na saída: apenas comprimento, alfabeto
e o resultado de cada tentativa (status HTTP e corpo quando é true/false).
"""
import argparse
import http.cookiejar
import string
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener

RAIZ = Path(__file__).resolve().parents[2]
UA = "PontoFalante/1.0 (+https://github.com/pedrobicas/ponto-falante)"


def ler_env(caminho: Path) -> dict[str, str]:
    bruto = caminho.read_bytes()
    valores = {"_bom": "sim" if bruto.startswith(b"\xef\xbb\xbf") else "nao"}
    for linha in bruto.decode("utf-8-sig").splitlines():
        if "=" in linha and not linha.lstrip().startswith("#"):
            k, v = linha.split("=", 1)
            valores[k.strip()] = v
    return valores


def formato(v: str) -> str:
    limpo = v.strip().strip('"').strip("'")
    alfabeto = ("hex_minusculo" if limpo and all(c in "0123456789abcdef" for c in limpo) else
                "hex_maiusculo" if limpo and all(c in "0123456789ABCDEF" for c in limpo) else "outro")
    return (f"comprimento={len(limpo)}; alfabeto={alfabeto}; aspas={'sim' if limpo != v.strip() else 'nao'}; "
            f"espacos_nas_bordas={'sim' if v != v.strip() else 'nao'}; "
            f"nao_imprimiveis={sum(c not in string.printable for c in v)}")


def tentar(rotulo: str, url: str, token: str, modo: str, timeout: float) -> str:
    jar = http.cookiejar.CookieJar()
    cliente = build_opener(HTTPCookieProcessor(jar))
    cab = {"User-Agent": UA, "Accept": "application/json"}
    if modo == "query":
        req = Request(f"{url}/Login/Autenticar?{urlencode({'token': token})}", data=b"", headers=cab, method="POST")
    elif modo == "form":
        req = Request(f"{url}/Login/Autenticar", data=urlencode({"token": token}).encode(),
                      headers={**cab, "Content-Type": "application/x-www-form-urlencoded"}, method="POST")
    else:  # get
        req = Request(f"{url}/Login/Autenticar?{urlencode({'token': token})}", headers=cab, method="GET")
    try:
        with cliente.open(req, timeout=timeout) as r:
            corpo = r.read(200).strip()
            status = r.status
    except HTTPError as e:
        corpo, status = e.read(200).strip(), e.code
    except (URLError, TimeoutError, OSError) as e:
        return f"{rotulo:<46} falha_rede={type(e).__name__}"
    texto = corpo.decode("utf-8", "replace").lower()
    resumo = texto if texto in ("true", "false") else f"corpo_omitido({len(corpo)} bytes)"
    cookie = "sim" if any(c.name == "apiCredentials" for c in jar) else "nao"
    return f"{rotulo:<46} http={status} corpo={resumo} cookie_sessao={cookie}"


GATEWAY = "https://gateway.apilib.prefeitura.sp.gov.br"


def testar_gateway(env: dict[str, str], timeout: float) -> int:
    """OAuth2 client_credentials no gateway da Prefeitura e uma consulta real; só imprime metadados."""
    import base64
    import json
    chave, segredo = env.get("SPTRANS_GATEWAY_CHAVE", "").strip(), env.get("SPTRANS_GATEWAY_SEGREDO", "").strip()
    if not chave or not segredo:
        print("gateway: SPTRANS_GATEWAY_CHAVE/SEGREDO ausentes no .env (cadastre a aplicação no apilib)")
        return 2
    basic = base64.b64encode(f"{chave}:{segredo}".encode()).decode()
    req = Request(f"{GATEWAY}/token", data=b"grant_type=client_credentials", method="POST",
                  headers={"User-Agent": UA, "Authorization": f"Basic {basic}",
                           "Content-Type": "application/x-www-form-urlencoded"})
    try:
        with build_opener().open(req, timeout=timeout) as r:
            dados = json.loads(r.read(4096))
    except HTTPError as e:
        print(f"gateway /token: http={e.code} (credenciais recusadas)")
        return 1
    acesso = dados.get("access_token", "")
    print(f"gateway /token: http=200 access_token={'presente' if acesso else 'ausente'} expires_in={dados.get('expires_in')}")
    if not acesso:
        return 1

    tentativas_extras = [0]

    def get(caminho: str):
        # O gateway devolve 500 intermitente ("Transport error: 411 Length Required" na chamada interna à SPTrans);
        # GET é idempotente, então repete até 3 vezes, como o OlhoVivoProvider.
        for tentativa in range(3):
            req = Request(f"{GATEWAY}/sptrans/olhovivo/v2.1{caminho}",
                          headers={"User-Agent": UA, "Authorization": f"Bearer {acesso}", "Accept": "application/json"})
            try:
                with build_opener().open(req, timeout=timeout) as r:
                    return r.status, json.loads(r.read(5_000_000) or b"null")
            except HTTPError as e:
                if e.code < 500 or tentativa == 2:
                    return e.code, None
                tentativas_extras[0] += 1
                time.sleep(0.2)

    falhas = 0
    st, linhas = get("/Linha/Buscar?termosBusca=8000")
    ok = st == 200 and isinstance(linhas, list) and linhas and {"cl", "lt", "tl", "sl"} <= set(linhas[0])
    print(f"/Linha/Buscar?termosBusca=8000: http={st} itens={len(linhas) if isinstance(linhas, list) else '-'} campos_ok={bool(ok)}")
    falhas += not ok
    st, paradas = get("/Parada/Buscar?termosBusca=paulista")
    ok = st == 200 and isinstance(paradas, list) and paradas and {"cp", "np", "py", "px"} <= set(paradas[0])
    print(f"/Parada/Buscar?termosBusca=paulista: http={st} itens={len(paradas) if isinstance(paradas, list) else '-'} campos_ok={bool(ok)}")
    falhas += not ok
    # Previsão: procura a primeira parada da busca com ônibus previstos (horário noturno pode não ter nenhum).
    com_previsao = None
    for p in (paradas or [])[:15]:
        st, prev = get(f"/Previsao/Parada?codigoParada={p['cp']}")
        if st != 200 or not isinstance(prev, dict):
            print(f"/Previsao/Parada: http={st} formato_ok=False")
            falhas += 1
            break
        veiculos = sum(len(l.get("vs") or []) for l in ((prev.get("p") or {}).get("l") or []))
        if veiculos:
            com_previsao = (prev.get("hr"), len((prev.get("p") or {}).get("l") or []), veiculos)
            break
    if com_previsao:
        print(f"/Previsao/Parada: http=200 hr={com_previsao[0]} linhas={com_previsao[1]} veiculos_previstos={com_previsao[2]}")
    else:
        print("/Previsao/Parada: nenhuma das paradas testadas tinha ônibus previstos agora")
    print(f"novas tentativas por 500 do gateway: {tentativas_extras[0]}")
    return 1 if falhas else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--env-file", default=str(RAIZ / ".env"))
    ap.add_argument("--timeout", type=float, default=15)
    ap.add_argument("--gateway", action="store_true", help="Testa o gateway OAuth da Prefeitura em vez do login direto.")
    a = ap.parse_args()
    env = ler_env(Path(a.env_file))
    if a.gateway:
        return testar_gateway(env, a.timeout)
    print(f".env com BOM: {env['_bom']}")
    chaves = [(n, env[n]) for n in ("SPTRANS_TOKEN", "SPTRANS_TOKEN_2") if env.get(n, "").strip()]
    if not chaves:
        print("SPTRANS_TOKEN ausente no .env")
        return 2
    bases = [("https api.olhovivo v2.1", "https://api.olhovivo.sptrans.com.br/v2.1"),
             ("http  api.olhovivo v2.1", "http://api.olhovivo.sptrans.com.br/v2.1"),
             ("https api.olhovivo v2", "https://api.olhovivo.sptrans.com.br/v2")]
    for nome, bruto in chaves:
        token = bruto.strip().strip('"').strip("'")
        print(f"\nvariavel {nome} -> {formato(bruto)}")
        for rotulo_base, base in bases:
            for modo in ("query", "form", "get"):
                print(tentar(f"{rotulo_base} {modo}", base, token, modo, a.timeout))
        print(tentar("https v2.1 query (chave em MAIUSCULAS)", bases[0][1], token.upper(), "query", a.timeout))
    print(tentar("controle: chave invalida", bases[0][1], "0" * 64, "query", a.timeout))
    return 0


if __name__ == "__main__":
    sys.exit(main())

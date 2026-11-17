"""
Passo 1 do dataset: baixa fotos de ônibus da cidade de São Paulo do Wikimedia Commons.

- Percorre categorias do Commons sobre ônibus da capital paulista.
- Aceita só licenças livres (domínio público, CC0, CC BY, CC BY-SA).
- Baixa uma versão reduzida (1280 px de largura) para economizar banda.
- Registra autor, licença e URL de cada foto em docs/creditos_imagens.csv
  (exigência das licenças CC BY e CC BY-SA: atribuição).

Nenhuma conta ou chave é necessária: a API do Commons é pública.

  python ferramentas/baixar_commons.py --saida dados/commons
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://commons.wikimedia.org/w/api.php"
CABECALHO = {"User-Agent": "PontoFalante-FIAP/1.0 (projeto academico; visao computacional)"}

# Categorias da capital (ônibus urbanos em operação). Ficam de fora: museu, mapas,
# ônibus escolares e outras cidades do estado.
CATEGORIAS = [
    "Category:Buses in São Paulo",
    "Category:São Paulo Transporte",
    "Category:Articulated buses in São Paulo",
    "Category:Bi-articulated buses in São Paulo",
    "Category:Trolleybuses in São Paulo",
    "Category:Terminal Bandeira",
    "Category:Corredor Metropolitano São Mateus–Jabaquara",
]
LICENCAS_OK = re.compile(r"^(public domain|pd|cc0|cc[- ]by([- ]sa)?([- ][\d.]+)?)", re.I)


def chamar_api(**params) -> dict:
    params["format"] = "json"
    url = API + "?" + urllib.parse.urlencode(params)
    for tentativa in range(6):
        try:
            # URL fixa da API do Commons (https) + parâmetros codificados por urlencode.
            with urllib.request.urlopen(urllib.request.Request(url, headers=CABECALHO), timeout=40) as r:  # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429:  # limite de requisições: espera e tenta de novo
                time.sleep(5 * (tentativa + 1))
                continue
            raise
    raise RuntimeError("API do Commons indisponível")


def arquivos_da_categoria(categoria: str) -> list[str]:
    titulos, cont = [], {}
    while True:
        r = chamar_api(action="query", list="categorymembers", cmtitle=categoria,
                       cmtype="file", cmlimit=500, **cont)
        titulos += [m["title"] for m in r["query"]["categorymembers"]]
        time.sleep(1)
        if "continue" not in r:
            return titulos
        cont = r["continue"]


def limpar_html(texto: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", texto or "")).strip()


def metadados(titulos: list[str]) -> dict[str, dict]:
    """Licença, autor e URL da miniatura de até 50 arquivos por chamada."""
    saida = {}
    for i in range(0, len(titulos), 50):
        r = chamar_api(action="query", prop="imageinfo", titles="|".join(titulos[i:i + 50]),
                       iiprop="url|extmetadata|mime", iiurlwidth=1280)
        for pagina in r["query"]["pages"].values():
            info = (pagina.get("imageinfo") or [{}])[0]
            meta = info.get("extmetadata", {})
            saida[pagina["title"]] = {
                "mime": info.get("mime", ""),
                "url_arquivo": info.get("thumburl") or info.get("url"),
                "pagina": info.get("descriptionurl", ""),
                "licenca": limpar_html(meta.get("LicenseShortName", {}).get("value", "")),
                "autor": limpar_html(meta.get("Artist", {}).get("value", "")) or "desconhecido",
            }
        time.sleep(1)
    return saida


def baixar(url: str, destino: Path) -> bool:
    """Baixa respeitando o limite do Commons: pausa entre arquivos e espera
    crescente quando o servidor responde 429 (muitas requisições)."""
    # Só https: os endereços vêm da própria API do Commons (upload.wikimedia.org); file:// e http:// são recusados.
    if urllib.parse.urlparse(url).scheme != "https":
        return False
    for tentativa in range(5):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=CABECALHO), timeout=60) as r:  # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected
                dados = r.read()
            # Segurança: só grava se o conteúdo for realmente JPEG ou PNG (assinatura do arquivo).
            if not (dados[:3] == b"\xff\xd8\xff" or dados[:8] == b"\x89PNG\r\n\x1a\n"):
                return False
            destino.write_bytes(dados)
            time.sleep(1.5)
            return True
        except urllib.error.HTTPError as e:
            if e.code != 429:
                return False
            time.sleep(15 * (tentativa + 1))
        except OSError:
            time.sleep(5)
    return False


def nome_seguro(titulo: str, i: int) -> str:
    base = re.sub(r"[^A-Za-z0-9]+", "_", Path(titulo.removeprefix("File:")).stem)[:60].strip("_")
    return f"sp_{i:04d}_{base}.jpg"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--saida", default="dados/commons")
    ap.add_argument("--creditos", default="docs/creditos_imagens.csv")
    args = ap.parse_args()
    pasta = Path(args.saida) / "images"
    pasta.mkdir(parents=True, exist_ok=True)

    titulos = []
    for cat in CATEGORIAS:
        achados = arquivos_da_categoria(cat)
        print(f"{cat}: {len(achados)} arquivos")
        titulos += [t for t in achados if t not in titulos]
    print("Total de arquivos únicos:", len(titulos))

    meta = metadados(titulos)
    linhas_credito, recusadas = [], 0
    for i, titulo in enumerate(sorted(meta)):
        m = meta[titulo]
        if m["mime"] not in ("image/jpeg", "image/png") or not m["url_arquivo"]:
            continue
        if not LICENCAS_OK.match(m["licenca"]):
            recusadas += 1
            continue
        nome = nome_seguro(titulo, i)
        destino = pasta / nome
        if not destino.exists():
            if not baixar(m["url_arquivo"], destino):  # uma foto com problema não interrompe a coleta
                print("Falhou:", titulo)
                continue
        linhas_credito.append({"arquivo": nome, "autor": m["autor"], "licenca": m["licenca"],
                               "url_original": m["pagina"], "observacao": "Wikimedia Commons"})

    with open(args.creditos, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["arquivo", "autor", "licenca", "url_original", "observacao"])
        w.writeheader()
        w.writerows(linhas_credito)
    print(f"Baixadas: {len(linhas_credito)} | recusadas por licença: {recusadas}")
    print("Créditos em", args.creditos)


if __name__ == "__main__":
    main()

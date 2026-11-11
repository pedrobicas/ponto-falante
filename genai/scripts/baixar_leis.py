"""Baixa os artigos de transporte das leis federais e grava em base/brutos e base/textos.

Fonte: portal de legislação da Câmara dos Deputados (texto oficial, versão "norma atualizada").
O site do Planalto não respondeu a requisições automáticas durante a coleta (timeouts),
por isso usamos a Câmara; se a versão atualizada falhar, cai para a publicação original
e registra isso em fontes.csv.

    python scripts/baixar_leis.py
"""
from __future__ import annotations

import csv
import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE = Path(__file__).resolve().parents[1] / "base"
UA = {"User-Agent": "Mozilla/5.0 (projeto academico FIAP Ponto Falante)"}

LEIS = [
    {
        "id": "lei-10741-transporte",
        "titulo": "Lei 10.741/2003 (Estatuto da Pessoa Idosa) · Do Transporte",
        "urls": ["https://www2.camara.leg.br/legin/fed/lei/2003/lei-10741-1-outubro-2003-497511-normaatualizada-pl.html",
                 "https://www2.camara.leg.br/legin/fed/lei/2003/lei-10741-1-outubro-2003-497511-publicacaooriginal-1-pl.html"],
        "artigos": [1, 39, 40, 41, 42],
    },
    {
        "id": "lei-13146-transporte",
        "titulo": "Lei 13.146/2015 (Lei Brasileira de Inclusão) · Do Direito ao Transporte e à Mobilidade",
        "urls": ["https://www2.camara.leg.br/legin/fed/lei/2015/lei-13146-6-julho-2015-781174-normaatualizada-pl.html",
                 "https://www2.camara.leg.br/legin/fed/lei/2015/lei-13146-6-julho-2015-781174-publicacaooriginal-147468-pl.html"],
        "artigos": [2, 46, 47, 48, 49, 50, 51, 52],
    },
]


def baixar(urls: list[str]) -> tuple[str, str]:
    for url in urls:
        for tentativa in range(3):
            try:
                r = requests.get(url, headers=UA, timeout=40)
                r.encoding = r.apparent_encoding
                if r.status_code == 200 and len(r.text) > 20000:
                    return url, r.text
            except requests.RequestException:
                pass
            time.sleep(3 * (tentativa + 1))
    raise RuntimeError(f"não foi possível baixar: {urls}")


def extrair(html: str, artigos: list[int]) -> str:
    texto = BeautifulSoup(html, "lxml").get_text(" ")
    texto = re.sub(r"\s+", " ", texto)
    # Quebra antes de cada "Art. N" e de títulos de capítulo/parágrafo/inciso
    texto = re.sub(r" (?=Art\. ?\d+[º°]?[ .-])", "\n", texto)
    texto = re.sub(r" (?=(CAPÍTULO|TÍTULO|Parágrafo único|§ ?\d+[º°]?|[IVXL]+ ?[-–] ))", "\n", texto)
    blocos = re.split(r"\n(?=Art\. ?\d)", texto)
    saida = []
    for b in blocos:
        m = re.match(r"Art\. ?(\d+)", b)
        if m and int(m.group(1)) in artigos:
            # corta o fim do último artigo antes do próximo capítulo/título
            b = re.split(r"\n(?:CAPÍTULO|TÍTULO)", b)[0].strip()
            saida.append(b)
    vistos, unicos = set(), []
    for b in saida:                       # o 1º match de cada número é o artigo do corpo da lei
        n = int(re.match(r"Art\. ?(\d+)", b).group(1))
        if n not in vistos:
            vistos.add(n)
            unicos.append(b)
    return "\n".join(unicos)


def main() -> int:
    linhas_csv = list(csv.DictReader((BASE / "fontes.csv").open(encoding="utf-8-sig")))
    ids = {l["id"] for l in linhas_csv}
    for lei in LEIS:
        url, html = baixar(lei["urls"])
        (BASE / "brutos" / f"{lei['id']}.html").write_text(html, encoding="utf-8")
        corpo = extrair(html, lei["artigos"])
        achados = sorted({int(n) for n in re.findall(r"^Art\. ?(\d+)", corpo, re.M)})
        print(lei["id"], url, "artigos:", achados, "chars:", len(corpo))
        if set(achados) != set(lei["artigos"]):
            print("  ATENÇÃO: faltaram artigos", set(lei["artigos"]) - set(achados), file=sys.stderr)
        (BASE / "textos" / f"{lei['id']}.txt").write_text(
            f"{lei['titulo']}\nFonte: {url}\n{corpo}\n", encoding="utf-8")
        if lei["id"] not in ids:
            linhas_csv.append({
                "id": lei["id"], "titulo": lei["titulo"], "orgao": "Câmara dos Deputados (texto oficial da lei federal)",
                "url": url, "formato": "HTML",
                "licenca": "Domínio público (Lei 9.610/98, art. 8º, IV: textos de lei não são protegidos)",
                "data_acesso": "2026-11-11",
                "observacao": ("norma atualizada" if "normaatualizada" in url else "publicação original (atualizada indisponível)")
                              + f"; artigos {', '.join(map(str, lei['artigos']))}",
            })
    with (BASE / "fontes.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas_csv[0].keys()))
        w.writeheader()
        w.writerows(linhas_csv)
    return 0


if __name__ == "__main__":
    sys.exit(main())

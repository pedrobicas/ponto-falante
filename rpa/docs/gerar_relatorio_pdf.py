"""Gera rpa/docs/relatorio.pdf a partir de relatorio.md, sem dependências (Markdown simples -> HTML -> PDF pelo Edge).

    python rpa/docs/gerar_relatorio_pdf.py

Cobre o que o relatório usa: títulos, parágrafos, listas, tabelas, blocos de código, imagens, negrito, código e links.
"""
from __future__ import annotations

import html
import re
import shutil
import subprocess
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
EDGE = [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"]
CSS = """
body{font:11pt/1.5 'Segoe UI',Arial,sans-serif;color:#1a1a1a;margin:0}
h1{font-size:20pt;margin:0 0 4pt}h2{font-size:14pt;margin:18pt 0 6pt;border-bottom:1px solid #bbb;padding-bottom:3pt}
p{margin:6pt 0}table{border-collapse:collapse;width:100%;margin:8pt 0;font-size:9.5pt}
th,td{border:1px solid #999;padding:4pt 6pt;text-align:left;vertical-align:top}th{background:#eee}
code{font-family:Consolas,monospace;font-size:9.5pt;background:#f2f2f2;padding:0 2pt}
pre{background:#f2f2f2;padding:8pt;font-size:8.5pt;white-space:pre-wrap;word-break:break-word}
pre code{background:none;padding:0}img{max-width:100%;max-height:230mm;display:block;margin:8pt auto}
blockquote{margin:6pt 0;padding-left:10pt;border-left:3px solid #bbb;color:#444}
h2,tr,img,pre{break-inside:avoid}@page{size:A4;margin:18mm 16mm}
"""


def inline(t: str) -> str:
    t = html.escape(t, quote=False)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", r'<img alt="\1" src="\2">', t)
    t = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<![\w*])\*([^*]+)\*(?![\w*])", r"<em>\1</em>", t)
    return re.sub(r"(?<![\"'>=])\b(https?://[^\s<)]+)", r'<a href="\1">\1</a>', t)


def converter(md: str) -> str:
    saida, linhas, i = [], md.splitlines(), 0
    while i < len(linhas):
        l = linhas[i]
        if l.startswith("```"):
            bloco = []
            i += 1
            while i < len(linhas) and not linhas[i].startswith("```"):
                bloco.append(html.escape(linhas[i]))
                i += 1
            saida.append("<pre><code>" + "\n".join(bloco) + "</code></pre>")
        elif l.startswith("#"):
            n = len(l) - len(l.lstrip("#"))
            saida.append(f"<h{n}>{inline(l[n:].strip())}</h{n}>")
        elif l.startswith("|") and i + 1 < len(linhas) and re.match(r"^\|[\s:|-]+\|$", linhas[i + 1].strip()):
            celulas = lambda s: [c.strip() for c in s.strip().strip("|").split("|")]  # noqa: E731
            saida.append("<table><thead><tr>" + "".join(f"<th>{inline(c)}</th>" for c in celulas(l)) + "</tr></thead><tbody>")
            i += 2
            while i < len(linhas) and linhas[i].startswith("|"):
                saida.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in celulas(linhas[i])) + "</tr>")
                i += 1
            saida.append("</tbody></table>")
            continue
        elif l.startswith("- "):
            saida.append("<ul>")
            while i < len(linhas) and linhas[i].startswith("- "):
                saida.append(f"<li>{inline(linhas[i][2:])}</li>")
                i += 1
            saida.append("</ul>")
            continue
        elif l.startswith(">"):
            saida.append(f"<blockquote>{inline(l.lstrip('> '))}</blockquote>")
        elif l.strip():
            paragrafo = [l]
            while i + 1 < len(linhas) and linhas[i + 1].strip() and not re.match(r"^(#|\||- |```|>)", linhas[i + 1]):
                i += 1
                paragrafo.append(linhas[i])
            saida.append("<p>" + "<br>".join(inline(x) for x in paragrafo) + "</p>")
        i += 1
    return "\n".join(saida)


def main() -> None:
    md = (AQUI / "relatorio.md").read_text(encoding="utf-8")
    md = re.sub(r"^> Este arquivo é a base do PDF.*\n", "", md, flags=re.M)
    pagina = AQUI / "relatorio.html"
    pagina.write_text(f'<!doctype html><html lang="pt-BR"><meta charset="utf-8"><title>Relatório técnico RPA - Ponto Falante</title>'
                      f"<style>{CSS}</style><body>{converter(md)}</body></html>", encoding="utf-8")
    edge = next((e for e in EDGE if Path(e).exists()), None) or shutil.which("msedge")
    if not edge:
        sys.exit("Edge não encontrado; abra rpa/docs/relatorio.html no navegador e use Imprimir > Salvar como PDF.")
    destino = AQUI / "relatorio.pdf"
    subprocess.run([edge, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",  # nosemgrep -- executável e argumentos fixos
                    f"--print-to-pdf={destino}", pagina.as_uri()], check=True, timeout=120,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    pagina.unlink()
    print(f"gerado {destino} ({destino.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()

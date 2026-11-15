"""Compatibilidade do comando original; exporta os PDFs finais de RPA e GenAI.

    python rpa/docs/gerar_relatorio_pdf.py

Usa scripts/entrega/gerar_pdfs.py (mistune, Pillow, pypdf e Edge). Os conversores
antigos abaixo permanecem disponíveis para compatibilidade; não alteram os relatórios.
"""
from __future__ import annotations

import html
import re
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
    import runpy
    runpy.run_path(str(AQUI.parents[1] / 'scripts/entrega/gerar_pdfs.py'), run_name='__main__')


if __name__ == "__main__":
    main()

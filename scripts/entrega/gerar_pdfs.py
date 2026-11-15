"""Exporta os relatórios existentes para revisão/entrega, sem executar o produto.

Uso na raiz: .venv/Scripts/python.exe scripts/entrega/gerar_pdfs.py
Dependências locais: mistune, Pillow, pypdf e Microsoft Edge.
Não lê conjuntos de avaliação, credenciais ou histórico Git.
"""
from __future__ import annotations

import html
import re
import shutil
import subprocess
from pathlib import Path

import mistune
from PIL import Image
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / '.validation/entrega-final/pdfs'
OUT = ROOT / 'entregaveis'
CSS = """
@page{size:A4;margin:17mm 15mm 18mm;@bottom-center{content:'Ponto Falante · FIAP 2026.2 | ' counter(page);font:8pt 'Segoe UI';color:#52685f}}
body{font:10.5pt/1.43 'Segoe UI',Arial,sans-serif;color:#18352e;margin:0}
h1{font-size:22pt;line-height:1.15;margin:0 0 12pt;color:#123e34}
h2{font-size:14pt;margin:17pt 0 7pt;border-bottom:1px solid #a8c1b7;padding-bottom:4pt}
h3{font-size:11.5pt;margin:12pt 0 6pt}h1,h2,h3{break-after:avoid}h2+p{break-after:avoid}
p{margin:6pt 0;orphans:3;widows:3}a{color:#165d77;overflow-wrap:anywhere}
table{border-collapse:collapse;width:100%;font-size:8.5pt;line-height:1.35;margin:9pt 0;break-inside:avoid}
th,td{border:1px solid #c3cfc9;padding:4pt;text-align:left;vertical-align:top;overflow-wrap:normal}
th{hyphens:auto;overflow-wrap:anywhere}.number{white-space:nowrap}.metrics{table-layout:fixed}.metrics th:first-child{width:17%}
th{background:#e7efea}tr{break-inside:avoid}thead{display:table-header-group}
code{font:8.5pt Consolas,monospace;overflow-wrap:anywhere}
pre{background:#eff3f0;padding:9pt;white-space:pre-wrap;word-break:break-word;break-inside:avoid}
li{margin:3pt 0;break-inside:avoid}ul,ol{padding-left:18pt}
blockquote{border-left:3px solid #adbeb4;padding-left:10pt;margin:8pt 0;color:#50655d}
img{display:block;max-width:100%;max-height:215mm;object-fit:contain;margin:10pt auto;break-inside:avoid}
img[src*="boletim_producao"]{max-height:170mm}
.diagram{break-inside:avoid;margin:8pt 0}.diagram svg{width:100%;height:auto;max-height:205mm}
.appendix{break-before:page}.appendix img{width:100%;max-height:none}
.caption{font-size:8.5pt;color:#52685f}
"""


def flow(title: str, steps: list[tuple[str, str]]) -> str:
    """Representação de impressão dos diagramas Mermaid já documentados."""
    h = 56 + len(steps) * 76
    parts = [f'<div class="diagram"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 760 {h}">',
             '<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6" fill="#547669"/></marker></defs>',
             f'<text x="20" y="26" font-family="Segoe UI" font-size="20" font-weight="bold" fill="#123e34">{html.escape(title)}</text>']
    for i, (label, detail) in enumerate(steps):
        y = 44 + i * 76
        if i:
            parts.append(f'<path d="M380,{y-14} V{y-2}" stroke="#547669" stroke-width="2" marker-end="url(#arrow)"/>')
        parts.append(f'<rect x="20" y="{y}" width="720" height="61" rx="8" fill="#edf3ef" stroke="#9db7aa"/>')
        parts.append(f'<text x="38" y="{y+24}" font-family="Segoe UI" font-size="18" font-weight="bold" fill="#163c32">{html.escape(label)}</text>')
        parts.append(f'<text x="38" y="{y+46}" font-family="Segoe UI" font-size="15" fill="#324b40">{html.escape(detail)}</text>')
    parts.append('</svg></div>')
    return ''.join(parts)


def diagrams() -> list[str]:
    return [flow('Documentos oficiais → base recuperável', [
        ('1. Fontes oficiais e cópias locais', 'SPTrans: 5 FAQs e tarifas; Câmara: duas leis; fontes.csv registra proveniência.'),
        ('2. Extração e segmentação por tipo', 'HTML → texto; leis por artigo; FAQ por pergunta/resposta; tarifas por célula.'),
        ('3. 244 trechos identificados', 'base/trechos.jsonl: trecho_id e fonte; valores originais preservados.'),
        ('4. Embeddings multilingual-e5-large', 'Prefixo passage: documento. texto; vetores normalizados.'),
        ('5. Índice FAISS IndexFlatIP', 'base/indice.faiss: similaridade de cosseno para recuperação.')]),
        flow('Pergunta → agente → resposta com fontes', [
        ('1. Angular → Spring Boot → FastAPI', 'Texto via /api/chat; horários usam ferramentas; direitos seguem para a GenAI.'),
        ('2. Triagem e reescrita', 'O LLM transforma termos coloquiais em termos de busca oficiais.'),
        ('3. Busca dupla e limiar', 'Original + reescrita, top-4; score abaixo de 0,86 → recusa.'),
        ('4. Geração estruturada', 'JSON com citações entre os IDs recuperados; sem informação → recusa.'),
        ('5. Checagem dos números e evidências', 'Número ausente na citação ou falha do verificador → nova tentativa com aviso.'),
        ('6. Resposta validada ou recusa', 'Nova falha → recusa; resposta aceita → pydantic, fontes e confiança.'),
        ('7. Retorno ao produto', 'Spring → Angular; passageiro pode acionar a leitura em voz alta.')])]


def appendix() -> str:
    # Detalhes ampliados do BPMN original; nenhuma alteração do fluxo.
    original = Image.open(ROOT / 'rpa/docs/fluxo.png')
    parts = ['<section class="appendix"><h2>Anexo - BPMN ampliado</h2>',
             '<p class="caption">Recortes com sobreposição do diagrama original. A visão completa está na seção 4; fluxo.bpmn conserva o modelo editável.</p>']
    panels = [
        ('Coletor: consulta, seleção da fonte e montagem das amostras', (60, 0, 1360, 510)),
        ('Coletor: publicação, auditoria e recuperação', (1250, 0, 2550, 510)),
        ('Boletim: leitura, validação e recuperação da indisponibilidade', (70, 570, 1370, 1360)),
        ('Boletim: classificação e natureza dos dados', (1090, 570, 2390, 1360)),
        ('Boletim: publicação e auditoria', (2220, 570, 3520, 1360)),
    ]
    for i, (title, box) in enumerate(panels):
        if i in (2, 4):
            parts.append('</section><section class="appendix">')
        path = WORK / f'bpmn-detalhe-{i+1}.png'
        original.crop(box).save(path)
        parts.append(f'<h3>{title}</h3><img src="{path.as_uri()}" alt="{title}">')
    parts.append('</section>')
    return ''.join(parts)


def main() -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(exist_ok=True)
    edge = next((p for p in [Path('C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'),
                            Path('C:/Program Files/Microsoft/Edge/Application/msedge.exe')] if p.exists()), None)
    if not edge:
        raise RuntimeError('Microsoft Edge não encontrado.')
    render = mistune.create_markdown(escape=False, plugins=['table', 'url'])
    for name, source in [('RPA', ROOT/'rpa/docs/relatorio.md'), ('GenAI', ROOT/'genai/RELATORIO.md')]:
        md = source.read_text(encoding='utf-8')
        md = re.sub(r'^> Este arquivo é a base do PDF.*\n', '', md, flags=re.M)
        figures = diagrams() if name == 'GenAI' else []
        for i, match in reversed(list(enumerate(re.finditer(r'```mermaid\n.*?```', md, flags=re.S)))):
            md = md[:match.start()] + f'\n<div>DIAGRAMA_PF_{i}</div>\n' + md[match.end():]
        body = render(md)
        body = re.sub(r'<p>(<strong>[^<]+</strong>)</p>', r'<p style="break-after:avoid">\1</p>', body)
        # Colunas numéricas preservam unidade e valor na mesma linha; tabelas não se partem.
        body = re.sub(r'<td>((?:<strong>)?\d+[.,]?\d*%(?:</strong>)?)</td>', r'<td><span class="number">\1</span></td>', body)
        body = re.sub(r'<table>(.*?)</table>',
                      lambda m: '<table class="metrics">'+m[1]+'</table>' if 'Configuração' in m[1].split('</thead>')[0] else m[0],
                      body, flags=re.S)
        # Links de arquivos locais permanecem clicáveis no Markdown; o PDF só vincula URLs hospedadas.
        body = re.sub(r'<a href="(?!https?://|#)[^"]*">(.*?)</a>', r'\1', body, flags=re.S)
        for i, fig in enumerate(figures):
            body = body.replace(f'<div>DIAGRAMA_PF_{i}</div>', fig)
        if name == 'RPA':
            for heading in ('9. Integração com o MVP', '12. Links'):
                body = body.replace(f'<h2>{heading}</h2>', f'<h2 style="break-before:page">{heading}</h2>')
            body += appendix()
        page = WORK / f'{name}.html'
        page.write_text(f'<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">'
                        f'<base href="{source.parent.as_uri()}/"><title>Ponto Falante - {name}</title>'
                        f'<style>{CSS}</style></head><body>{body}</body></html>', encoding='utf-8')
        target = OUT / f'Relatorio_{name}.pdf'
        result = subprocess.run([str(edge), '--headless=new', '--disable-gpu', '--no-pdf-header-footer',
                                 '--allow-file-access-from-files', f'--user-data-dir={WORK / ("edge-"+name)}',
                                 f'--print-to-pdf={target}', page.as_uri()],
                                capture_output=True, timeout=90, creationflags=subprocess.CREATE_NO_WINDOW)
        (WORK/f'{name}-edge.log').write_bytes(result.stderr)
        if result.returncode or not target.exists():
            raise RuntimeError(f'Falha ao gerar {target}; consulte {WORK}.')
        pdf = PdfReader(target)
        if not all(p.extract_text().strip() for p in pdf.pages):
            raise RuntimeError(f'Página vazia em {target}')
        print(f'{name}: {len(pdf.pages)} páginas, {target.stat().st_size} bytes', flush=True)
        if name == 'RPA':
            shutil.copy2(target, ROOT/'rpa/docs/relatorio.pdf')


if __name__ == '__main__':
    main()

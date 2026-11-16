"""Gera os PDFs dos relatórios acadêmicos (GenAI e RPA) a partir do Markdown, sem executar o produto.

Uso na raiz: .venv/Scripts/python.exe scripts/entrega/gerar_pdfs.py
Dependências locais: mistune, Pillow, pypdf e Microsoft Edge.

Links externos: preencha docs/links_entrega.json. Cada link fica no Markdown entre marcadores
<!--link:CHAVE-->...<!--/link-->; este script troca o conteúdo pelos links preenchidos (ou pelo placeholder
[INSERIR LINK ...] enquanto estiver vazio), grava o Markdown e só então gera os PDFs.
Não lê conjuntos de avaliação, credenciais ou histórico Git.
"""
from __future__ import annotations

import html
import json
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
LINKS = ROOT / 'docs/links_entrega.json'
PLACEHOLDERS = {
    'repositorio': '[INSERIR LINK DO REPOSITÓRIO PÚBLICO]',
    'video_genai': '[INSERIR LINK DO VÍDEO GENAI]',
    'video_rpa': '[INSERIR LINK DO VÍDEO RPA]',
}
RELATORIOS = [
    ('GenAI', ROOT / 'genai/RELATORIO.md', 'Ponto Falante · Generative AI for Engineering'),
    ('RPA', ROOT / 'rpa/docs/relatorio.md', 'Ponto Falante · Robotic Process Automation'),
]

AZUL = '#0b4f6c'
CSS = f"""
@page{{size:A4;margin:20mm 18mm 19mm;
  @bottom-left{{content:'RODAPE_PF';font:7.5pt 'Segoe UI',Arial,sans-serif;color:#6b7c85}}
  @bottom-right{{content:counter(page);font:7.5pt 'Segoe UI',Arial,sans-serif;color:#6b7c85}}}}
@page :first{{@bottom-left{{content:none}}@bottom-right{{content:none}}}}
@page paisagem{{size:A4 landscape;margin:12mm 15mm 14mm}}
body{{font:10.4pt/1.52 Cambria,Georgia,'Times New Roman',serif;color:#1d2a31;margin:0;text-align:justify;hyphens:auto}}
h1,h2,h3,.legenda,table,figcaption{{font-family:'Segoe UI',Arial,sans-serif;text-align:left}}
h1{{font-size:25pt;line-height:1.18;color:{AZUL};margin:0 0 10pt;font-weight:600}}
h2{{font-size:14pt;color:{AZUL};font-weight:600;margin:20pt 0 8pt;padding-bottom:3pt;border-bottom:1.4px solid {AZUL};break-after:avoid}}
h3{{font-size:11.2pt;color:{AZUL};font-weight:600;margin:14pt 0 5pt;break-after:avoid}}
p{{margin:0 0 7pt;orphans:3;widows:3}}
a{{color:{AZUL};text-decoration:none;overflow-wrap:anywhere}}
strong{{font-weight:700}}
ul,ol{{margin:0 0 8pt;padding-left:17pt}}li{{margin:0 0 3.5pt;break-inside:avoid}}
code{{font:8.4pt Consolas,'Courier New',monospace;color:#25424f;background:#eef3f5;padding:0 2pt;border-radius:2pt}}
pre{{background:#f3f6f7;border-left:3px solid {AZUL};padding:7pt 9pt;margin:2pt 0 11pt;white-space:pre-wrap;word-break:break-word;break-inside:avoid;text-align:left}}
pre code{{background:none;padding:0;font-size:7.6pt;line-height:1.45}}
table{{border-collapse:collapse;width:100%;font-size:8.4pt;line-height:1.38;margin:2pt 0 13pt;break-inside:avoid}}
th{{background:{AZUL};color:#fff;font-weight:600;text-align:left;padding:4pt 5pt;border:1px solid {AZUL};vertical-align:bottom}}
td{{padding:3.6pt 5pt;border:1px solid #cfd9de;vertical-align:top}}
tbody tr:nth-child(even) td{{background:#f3f7f9}}
tr{{break-inside:avoid}}thead{{display:table-header-group}}table.longa{{break-inside:auto}}
table.duas{{table-layout:fixed}}table.duas th:first-child{{width:23%}}.capa table.duas{{table-layout:auto}}.capa table.duas th:first-child{{width:auto}}
.referencias{{list-style:none;padding-left:0;text-align:left}}.referencias li{{margin-bottom:5pt}}
td .num,td.num{{white-space:nowrap}}
.legenda{{font-size:8.6pt;font-weight:600;color:{AZUL};margin:10pt 0 3pt;break-after:avoid}}
p:has(>img)+.legenda,.diagram+.legenda{{margin:3pt 0 12pt;text-align:center;font-weight:400;color:#40525b}}
p:has(+pre),p:has(+table),p:has(+ul),p:has(+ol),p:has(+.diagram),p:has(+p>img){{break-after:avoid}}
img{{display:block;max-width:100%;max-height:120mm;object-fit:contain;margin:6pt auto 2pt;break-inside:avoid}}
img[src*="boletim_producao"]{{max-height:118mm;border:1px solid #cfd9de}}
.diagram{{break-inside:avoid;margin:4pt auto 0;max-width:150mm}}.diagram svg{{width:100%;height:auto}}
.pendente{{background:#fff3cd;color:#7a4b00;padding:0 3pt;font-weight:700}}
.capa{{min-height:250mm;display:flex;flex-direction:column;break-after:page;text-align:left}}
.capa .instituicao{{font:600 9pt 'Segoe UI',Arial,sans-serif;letter-spacing:.12em;text-transform:uppercase;color:#6b7c85;margin:6mm 0 46mm}}
.capa h1{{font-size:27pt}}
.capa .meta{{font:11pt/1.55 'Segoe UI',Arial,sans-serif;color:#40525b;margin:0 0 22mm;border-left:3px solid {AZUL};padding-left:9pt}}
.capa h2{{font-size:11pt;border:none;margin:0 0 4pt;padding:0}}
.capa table{{width:62%;font-size:9.5pt}}
.capa .local{{margin-top:auto;font:9.5pt 'Segoe UI',Arial,sans-serif;color:#6b7c85}}
.paisagem{{page:paisagem;break-before:page;break-after:page}}
.paisagem h3{{margin:0 0 4pt}}.paisagem img{{max-height:162mm;width:100%;margin:2pt 0}}
.paisagem .duplo img{{max-height:86mm;width:auto}}.paisagem .duplo img[alt^='Raia']{{max-height:50mm}}
.figura{{break-inside:avoid}}img.bpmn{{max-height:none;width:100%;border:1px solid #cfd9de}}
.paisagem .legenda{{text-align:left;font-weight:400;color:#40525b;margin:2pt 0 8pt}}
"""


def aplicar_links() -> dict[str, str]:
    """Troca o conteúdo entre <!--link:CHAVE--> e <!--/link--> pelo link preenchido ou pelo placeholder."""
    links = json.loads(LINKS.read_text(encoding='utf-8'))
    for _, fonte, _ in RELATORIOS:
        md = fonte.read_text(encoding='utf-8')
        novo = re.sub(r'<!--link:(\w+)-->(.*?)<!--/link-->',
                      lambda m: f'<!--link:{m[1]}-->{(links.get(m[1]) or "").strip() or PLACEHOLDERS[m[1]]}<!--/link-->',
                      md)
        if novo != md:
            fonte.write_text(novo, encoding='utf-8')
    return links


def flow(steps: list[tuple[str, str]], cor: str = AZUL) -> str:
    """Fluxo vertical em SVG que reproduz, para impressão, os diagramas Mermaid do Markdown."""
    altura = 20 + len(steps) * 74
    partes = [f'<div class="diagram"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 {altura}">',
              f'<defs><marker id="seta" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">'
              f'<path d="M0,0 L6,3 L0,6" fill="{cor}"/></marker></defs>']
    for i, (titulo, detalhe) in enumerate(steps):
        y = 10 + i * 74
        if i:
            partes.append(f'<path d="M320,{y-16} V{y-3}" stroke="{cor}" stroke-width="1.6" marker-end="url(#seta)"/>')
        partes.append(f'<rect x="10" y="{y}" width="620" height="56" rx="6" fill="#f1f6f8" stroke="#a9c3cf"/>'
                      f'<rect x="10" y="{y}" width="6" height="56" rx="2" fill="{cor}"/>')
        partes.append(f'<text x="30" y="{y+23}" font-family="Segoe UI" font-size="15" font-weight="600" '
                      f'fill="{cor}">{html.escape(titulo)}</text>')
        partes.append(f'<text x="30" y="{y+43}" font-family="Segoe UI" font-size="12.5" '
                      f'fill="#33464f">{html.escape(detalhe)}</text>')
    partes.append('</svg></div>')
    return ''.join(partes)


def diagramas_genai() -> list[str]:
    return [
        flow([('1. Fontes oficiais', 'SPTrans: 5 páginas de perguntas e respostas e a tabela de tarifas; duas leis federais.'),
              ('2. Extração e segmentação por tipo', 'Leis por artigo; perguntas e respostas por par; tarifas por célula.'),
              ('3. 244 trechos identificados', 'Cada trecho tem identificador estável e fonte registrada (URL, órgão, licença).'),
              ('4. Embeddings multilingual-e5-large', 'Vetores normalizados de cada trecho.'),
              ('5. Índice FAISS', 'Busca por similaridade de cosseno.')]),
        flow([('1. Pergunta no aplicativo', 'Angular envia ao backend Spring Boot, que chama a API de IA.'),
              ('2. Triagem e reescrita', 'O modelo reescreve termos coloquiais com os termos oficiais.'),
              ('3. Busca dupla e limiar', 'Pergunta original e reescrita; abaixo do limiar, recusa com orientação ao 156.'),
              ('4. Geração em JSON', 'Resposta curta citando apenas trechos recuperados; sem informação, recusa.'),
              ('5. Verificação', 'Números e afirmações precisam estar no trecho citado; senão, nova tentativa ou recusa.'),
              ('6. Resposta ao passageiro', 'Texto validado, fontes citadas e leitura em voz alta no aplicativo.')]),
    ]


def recortes_bpmn() -> dict[str, Path]:
    """Recortes do BPMN original (rpa/docs/fluxo.png), sem alterar o fluxo; cortes em espaços vazios entre tarefas."""
    original = Image.open(ROOT / 'rpa/docs/fluxo.png')
    caixas = {'geral': (0, 0, 3478, 1396), 'coletor': (0, 0, 2512, 496),
              'boletim1': (0, 548, 1905, 1394), 'boletim2': (1880, 548, 3478, 1394)}
    caminhos = {}
    for nome, caixa in caixas.items():
        caminho = WORK / f'bpmn-{nome}.png'
        original.crop(caixa).save(caminho)
        caminhos[nome] = caminho
    return caminhos


def bpmn_html() -> tuple[str, str]:
    r = recortes_bpmn()
    geral = (f'<div class="figura"><p><img class="bpmn" src="{r["geral"].as_uri()}" alt="Fluxo BPMN completo"></p>'
             '<p class="legenda">Figura 1. Fluxo BPMN da automação. Raia superior: coletor, oito vezes por dia; raia '
             'inferior: robô do boletim, diariamente às 6h. Versão legível em página inteira no Anexo A.</p></div>')
    anexo = (f'<section class="paisagem"><h2>Anexo A. BPMN ampliado</h2>'
             f'<h3>A.1 Visão geral</h3><img src="{r["geral"].as_uri()}" alt="Fluxo BPMN completo">'
             '<p class="legenda">Modelo editável em BPMN 2.0 no arquivo rpa/docs/fluxo.bpmn do repositório.</p></section>'
             f'<section class="paisagem"><div class="duplo"><h3>A.2 Coletor</h3>'
             f'<img src="{r["coletor"].as_uri()}" alt="Raia do coletor">'
             f'<h3>A.3 Boletim: leitura, validação e decisão</h3><img src="{r["boletim1"].as_uri()}" alt="Boletim, parte 1">'
             '<p class="legenda">As três saídas da decisão sobre amostras reais continuam em A.4; a republicação do '
             'último boletim segue até a publicação, também em A.4.</p></div></section>'
             f'<section class="paisagem"><h3>A.4 Boletim: geração, publicação e auditoria</h3>'
             f'<img src="{r["boletim2"].as_uri()}" alt="Boletim, parte 2"></section>')
    return geral, anexo


def montar_html(nome: str, fonte: Path, rodape: str) -> str:
    md = fonte.read_text(encoding='utf-8')
    figuras = diagramas_genai() if nome == 'GenAI' else []
    for i, achado in reversed(list(enumerate(re.finditer(r'```mermaid\n.*?```', md, flags=re.S)))):
        md = md[:achado.start()] + f'\n<div>DIAGRAMA_PF_{i}</div>\n' + md[achado.end():]
    corpo = mistune.create_markdown(escape=False, plugins=['table', 'url'])(md)
    for i, figura in enumerate(figuras):
        corpo = corpo.replace(f'<div>DIAGRAMA_PF_{i}</div>', figura)
    # Percentuais e decimais não quebram entre número e unidade.
    corpo = re.sub(r'<td>((?:<strong>)?[\d.,]+ ?(?:%|s)(?:</strong>)?)</td>', r'<td class="num">\1</td>', corpo)
    # Arquivos locais citados no Markdown não viram links no PDF; só URLs públicas continuam clicáveis.
    corpo = re.sub(r'<a href="(?!https?://|#)[^"]*">(.*?)</a>', r'\1', corpo, flags=re.S)
    for texto in PLACEHOLDERS.values():
        corpo = corpo.replace(texto, f'<span class="pendente">{texto}</span>')
    # Capa: título, identificação e integrantes (tudo antes da seção 2).
    inicio = corpo.index('<h2>2.')
    capa = corpo[:inicio].replace('<p>', '<p class="meta">', 1)
    capa = ('<section class="capa"><div class="instituicao">FIAP · Engenharia de Software · Global Solution 2026.2</div>'
            + capa + '<div class="local">São Paulo · Novembro de 2026</div></section>')
    corpo = capa + corpo[inicio:]
    # Tabelas longas podem continuar na página seguinte (cabeçalho repetido); tabelas de duas colunas têm rótulo fixo.
    def classe(m: re.Match) -> str:
        linhas = m[1].count('<tr>') - 1
        colunas = len(re.findall(r'<th[ >]', m[1].split('</tr>')[0]))
        nomes = (['longa'] if linhas >= 7 else []) + (['duas'] if colunas == 2 else [])
        return (f'<table class="{" ".join(nomes)}">' if nomes else '<table>') + m[1] + '</table>'
    corpo = re.sub(r'<table>(.*?)</table>', classe, corpo, flags=re.S)
    corpo = re.sub(r'(<h2>Referências</h2>\s*)<ul>', r'\1<ul class="referencias">', corpo)
    if nome == 'RPA':
        geral, anexo = bpmn_html()
        # A imagem do BPMN no Markdown vira a figura recortada com legenda; o anexo traz as versões ampliadas.
        corpo = re.sub(r'<p><img src="fluxo\.png"[^>]*></p>', lambda _: geral, corpo) + anexo
    return (f'<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">'
            f'<base href="{fonte.parent.as_uri()}/"><title>Ponto Falante - {nome}</title>'
            f'<style>{CSS.replace("RODAPE_PF", rodape)}</style></head><body>{corpo}</body></html>')


def main() -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(exist_ok=True)
    edge = next((p for p in [Path('C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'),
                             Path('C:/Program Files/Microsoft/Edge/Application/msedge.exe')] if p.exists()), None)
    if not edge:
        raise RuntimeError('Microsoft Edge não encontrado.')
    links = aplicar_links()
    faltando = [PLACEHOLDERS[k] for k in PLACEHOLDERS if not (links.get(k) or '').strip()]
    for nome, fonte, rodape in RELATORIOS:
        pagina = WORK / f'{nome}.html'
        pagina.write_text(montar_html(nome, fonte, rodape), encoding='utf-8')
        alvo = OUT / f'Relatorio_{nome}.pdf'
        resultado = subprocess.run([str(edge), '--headless=new', '--disable-gpu', '--no-pdf-header-footer',
                                    '--allow-file-access-from-files', f'--user-data-dir={WORK / ("edge-" + nome)}',
                                    f'--print-to-pdf={alvo}', pagina.as_uri()],
                                   capture_output=True, timeout=120, creationflags=subprocess.CREATE_NO_WINDOW)
        (WORK / f'{nome}-edge.log').write_bytes(resultado.stderr)
        if resultado.returncode or not alvo.exists():
            raise RuntimeError(f'Falha ao gerar {alvo}; consulte {WORK}.')
        pdf = PdfReader(alvo)
        if not all(p.extract_text().strip() for p in pdf.pages):
            raise RuntimeError(f'Página vazia em {alvo}')
        print(f'{nome}: {len(pdf.pages)} páginas, {alvo.stat().st_size} bytes', flush=True)
        if nome == 'RPA':
            shutil.copy2(alvo, ROOT / 'rpa/docs/relatorio.pdf')
    print('Links ainda pendentes: ' + (', '.join(faltando) if faltando else 'nenhum'))
    # Hashes, páginas, links e placeholders sempre conferidos sobre os PDFs recém-gerados.
    from validar_documentos import main as validar
    validar()


if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')  # console do Windows em cp1252
    main()

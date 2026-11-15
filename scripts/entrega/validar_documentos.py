"""Gera entregaveis/VALIDACAO_DOCUMENTOS.json a partir dos PDFs que existem no disco.

Uso na raiz: .venv/Scripts/python.exe scripts/entrega/validar_documentos.py
Também é chamado no fim de gerar_pdfs.py. Registra páginas, tamanho, SHA-256, links clicáveis, presença dos RMs
e dos placeholders padronizados [PENDENTE: ...] que ainda precisam ser trocados pelas URLs reais.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'entregaveis'
RMS = ['99534', '551305', '99405', '98630', '98607']


def validar(pdf: Path) -> dict:
    dados = pdf.read_bytes()
    leitor = PdfReader(pdf)
    texto = '\n'.join(p.extract_text() or '' for p in leitor.pages)
    urls = []
    for pagina in leitor.pages:
        for anotacao in pagina.get('/Annots') or []:
            acao = anotacao.get_object().get('/A') or {}
            uri = acao.get('/URI')
            if uri and uri not in urls:
                urls.append(str(uri))
    planos = re.sub(r'\s+', ' ', texto)
    return {
        'arquivo': pdf.name,
        'paginas': len(leitor.pages),
        'paginas_paisagem': [i + 1 for i, p in enumerate(leitor.pages) if p.mediabox.width > p.mediabox.height],
        'bytes': len(dados),
        'sha256': hashlib.sha256(dados).hexdigest(),
        'urls': urls,
        'rms_presentes': all(rm in planos for rm in RMS),
        'pendencias': sorted(set(re.findall(r'\[PENDENTE: [A-Z_]+\]', planos))),
        'paginas_sem_texto': [i + 1 for i, p in enumerate(leitor.pages) if not (p.extract_text() or '').strip()],
    }


def main() -> None:
    resultado = {'gerado_em': datetime.now(timezone.utc).isoformat(timespec='seconds')}
    for nome in ('RPA', 'GenAI'):
        pdf = OUT / f'Relatorio_{nome}.pdf'
        resultado[nome] = validar(pdf) if pdf.exists() else {'arquivo': pdf.name, 'erro': 'não encontrado'}
    copia = ROOT / 'rpa/docs/relatorio.pdf'
    if copia.exists() and 'sha256' in resultado['RPA']:
        resultado['RPA']['copia_rpa_docs_identica'] = (
            hashlib.sha256(copia.read_bytes()).hexdigest() == resultado['RPA']['sha256'])
    (OUT / 'VALIDACAO_DOCUMENTOS.json').write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding='utf-8')
    for nome in ('RPA', 'GenAI'):
        r = resultado[nome]
        print(f"{nome}: {r.get('paginas')} páginas, {r.get('bytes')} bytes, sha256 {str(r.get('sha256'))[:12]}…, "
              f"RMs {r.get('rms_presentes')}, pendências {r.get('pendencias')}")


if __name__ == '__main__':
    main()

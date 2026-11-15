"""Monta entregaveis/ENTREGA_FINAL/ a partir dos arquivos já gerados (PDFs, vídeos, roteiros e validações).

Uso na raiz: .venv/Scripts/python.exe scripts/entrega/montar_entrega_final.py
Rode de novo depois de narrar os vídeos e de trocar os placeholders: o vídeo narrado (*_narrado.mp4), quando existe,
substitui o silencioso. Nada de credenciais, .env, modelos ou caches entra na pasta.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
E = ROOT / 'entregaveis'
DEST = E / 'ENTREGA_FINAL'


def video(nome: str) -> Path:
    narrado = E / f'{nome}_narrado.mp4'
    return narrado if narrado.exists() else E / f'{nome}.mp4'


ITENS = [
    ('01_GenAI/Relatorio_GenAI.pdf', lambda: E / 'Relatorio_GenAI.pdf'),
    ('01_GenAI/Ponto_Falante_GenAI.mp4', lambda: video('Ponto_Falante_GenAI')),
    ('01_GenAI/ROTEIRO_GENAI.md', lambda: E / 'ROTEIRO_GENAI.md'),
    ('02_RPA/Relatorio_RPA.pdf', lambda: E / 'Relatorio_RPA.pdf'),
    ('02_RPA/Ponto_Falante_RPA.mp4', lambda: video('Ponto_Falante_RPA')),
    ('02_RPA/ROTEIRO_RPA.md', lambda: E / 'ROTEIRO_RPA.md'),
    ('02_RPA/fluxo.bpmn', lambda: ROOT / 'rpa/docs/fluxo.bpmn'),
    ('03_Conferencia/MATRIZ_CRITERIOS_FIAP.md', lambda: ROOT / 'docs/MATRIZ_CRITERIOS_FIAP.md'),
    ('03_Conferencia/VALIDACAO_DOCUMENTOS.json', lambda: E / 'VALIDACAO_DOCUMENTOS.json'),
    ('03_Conferencia/VALIDACAO_VIDEOS.json', lambda: E / 'VALIDACAO_VIDEOS.json'),
    ('O_QUE_FALTA_VOCE_FAZER.md', lambda: E / 'O_QUE_FALTA_VOCE_FAZER.md'),
]


def main() -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    manifesto = []
    for destino, origem in ITENS:
        src = origem()
        alvo = DEST / destino
        alvo.parent.mkdir(parents=True, exist_ok=True)
        if not src.exists():
            print(f'FALTA: {src.relative_to(ROOT)}')
            continue
        shutil.copy2(src, alvo)
        manifesto.append({'arquivo': destino, 'origem': str(src.relative_to(ROOT)).replace('\\', '/'),
                          'bytes': alvo.stat().st_size, 'sha256': hashlib.sha256(alvo.read_bytes()).hexdigest()})
    (DEST / 'MANIFESTO.json').write_text(json.dumps({'montado_em': datetime.now().isoformat(timespec='seconds'),
                                                    'arquivos': manifesto}, ensure_ascii=False, indent=2),
                                         encoding='utf-8')
    # ZIP só com documentos (os vídeos vão por link do YouTube; anexá-los deixaria o pacote grande demais).
    pacote = DEST / 'Ponto_Falante_documentos.zip'
    with zipfile.ZipFile(pacote, 'w', zipfile.ZIP_DEFLATED) as z:
        for item in manifesto:
            if not item['arquivo'].endswith('.mp4'):
                z.write(DEST / item['arquivo'], item['arquivo'])
        z.write(DEST / 'README_ENTREGA.md', 'README_ENTREGA.md') if (DEST / 'README_ENTREGA.md').exists() else None
    for item in manifesto:
        print(f"{item['arquivo']:45s} {item['bytes']:>11,d} bytes  ← {item['origem']}")
    print(f'ZIP de documentos: {pacote.name} ({pacote.stat().st_size:,d} bytes)')


if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')  # console do Windows em cp1252
    main()

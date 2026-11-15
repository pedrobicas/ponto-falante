"""Monta o vídeo RPA sem trilha de áudio, preservando todos os brutos.

Uso: .venv/Scripts/python.exe scripts/video/montar_rpa_final.py
As pausas finais são quadros da própria gravação, identificadas na timeline.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / '.validation/video-rpa-final'
RAW = ROOT / 'output/playwright/rpa-video-final'
FF = ROOT / '.validation/video-tools/imageio_ffmpeg/binaries/ffmpeg-win-x86_64-v9.0.2.exe'
OUT = ROOT / 'entregaveis/Ponto_Falante_RPA.mp4'
sys.stdout.reconfigure(encoding='utf-8')

SCENES = [
    ('01_problema', RAW/'producao-live.webm', 7, 10, 'Do trabalho repetitivo ao boletim acessível', 'SITE PUBLICADO  •  ponto-falante.onrender.com/boletim  •  carregamento inicial removido'),
    ('02_fluxo', ROOT/'rpa/docs/fluxo.png', 0, 10, 'Coletar → validar → decidir → publicar → auditar', 'BPMN DO REPOSITÓRIO  •  detalhe ampliado do fluxo diário; diagrama completo no PDF técnico'),
    ('03_regras', RAW/'regras.webm', 0.4, 16, 'Regras configuráveis; dados reais e simulados separados', 'ARQUIVO REAL  •  leitura da configuração YAML; nenhuma regra foi alterada na gravação'),
    ('04_repeticao', RAW/'codigo.webm', 0.4, 12, 'A repetição percorre linhas, pontos e amostras', 'CÓDIGO REAL  •  trechos com números de linha; mínimo de amostras antes de decidir'),
    ('05_coleta', RAW/'coleta.webm', 0.4, 16, 'Coleta real: seis pontos e seis amostras gravadas', 'EVIDÊNCIA ANTERIOR  •  GitHub Actions 43615927347, 14/11/2026 às 13h30 BRT; log original'),
    ('06_execucao', ROOT/'output/playwright/rpa-video/sucesso.webm', 10, 18, 'Execução completa do robô no ambiente local', 'MOCK LOCAL / SIMULADO  •  espera inicial removida; pausa final de leitura  •  sem envio à produção'),
    ('07_resultado', RAW/'sucesso.webm', 0.4, 14, 'Validação, decisão por linha e publicação pela API', 'RESULTADO DA CENA ANTERIOR  •  código 0, JSON e HTML gerados, boletim recebido no mock local'),
    ('08_integracao', RAW/'producao-live.webm', 14, 25, 'O MVP publicado consome o boletim real', 'PRODUÇÃO  •  13/11/2026: 17 consultas, 35,4% de cobertura  •  estimativas, não atrasos medidos'),
    ('09_falha', RAW/'falha.webm', 0.4, 25, 'HTTP 503: três tentativas e recuperação explícita', 'FALHA LOCAL CONTROLADA  •  esperas reais de 2 s e 4 s preservadas  •  pausa final para leitura'),
    ('10_auditoria', RAW/'auditoria.webm', 0.4, 16, 'Auditoria gravada; resultado confirmado por GET', 'MOCK LOCAL / SIMULADO  •  código 2 registrado e boletim anterior marcado como desatualizado'),
    ('11_fim', RAW/'producao-live.webm', 41.9, 8, 'Informação acessível, com fonte, data e limites', 'PONTO FALANTE  •  FIAP / GLOBAL SOLUTION 2026.2  •  vídeo sem áudio para narração humana'),
]


def run(args: list[str], log: Path) -> None:
    with log.open('w', encoding='utf-8') as handle:
        proc = subprocess.run([str(FF), '-hide_banner', '-y', *args], cwd=ROOT, stdout=handle, stderr=subprocess.STDOUT)
    if proc.returncode:
        raise RuntimeError(f'FFmpeg falhou: {log}')


def banner(name: str, title: str, note: str, index: int) -> Path:
    im = Image.new('RGBA', (1600,900), (0,0,0,0))
    d = ImageDraw.Draw(im)
    bold = ImageFont.truetype('C:/Windows/Fonts/segoeuib.ttf', 24)
    normal = ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf', 18)
    small = ImageFont.truetype('C:/Windows/Fonts/segoeuib.ttf', 16)
    d.rectangle((0,0,1600,45), fill='#123E34')
    d.rectangle((0,856,1600,900), fill='#123E34')
    d.text((80,6),title,font=bold,fill='#F7FAF6')
    d.text((1448,13),f'{index:02}/11',font=small,fill='#BDD8CB')
    if d.textbbox((0,0),note,font=normal)[2] > 1440:
        raise ValueError('Legenda muito longa: '+note)
    d.text((80,866),note,font=normal,fill='#ECF3EE')
    d.rectangle((0,897,round(1600*index/11),899),fill='#E6B950')
    target = WORK/(name+'-faixa.png'); im.save(target)
    return target


def main() -> None:
    WORK.mkdir(parents=True,exist_ok=True); OUT.parent.mkdir(exist_ok=True)
    timeline=[]; elapsed=0.0; segments=[]
    for index, (name, source, start, duration, title, note) in enumerate(SCENES,1):
        overlay=banner(name,title,note,index)
        segment=WORK/(name+'.mp4'); segments.append(segment)
        if source.suffix=='.png':
            args=['-loop','1','-framerate','25','-i',str(source)]
            base="crop=1600:900:x='250+140*t':y=550,"
        else:
            args=['-ss',str(start),'-i',str(source)]
            base=''
        filters=(f'[0:v]setpts=PTS-STARTPTS,{base}fps=25,scale=1440:810:flags=lanczos,'
                 f'pad=1600:900:80:46:color=0x0e1922,tpad=stop_mode=clone:stop_duration=30,trim=duration={duration}[base];'
                 '[base][1:v]overlay=0:0:format=auto,format=yuv420p[v]')
        run([*args,'-loop','1','-i',str(overlay),'-filter_complex',filters,'-map','[v]','-an',
             '-t',str(duration),'-r','25','-c:v','libx264','-preset','veryfast','-crf','18','-threads','2',
             '-movflags','+faststart',str(segment)],WORK/(name+'-ffmpeg.log'))
        timeline.append({'cena':name,'inicio_s':elapsed,'fim_s':elapsed+duration,'duracao_s':duration,
                         'fonte':source.relative_to(ROOT).as_posix(),'corte_inicial_s':start,'titulo':title,'faixa':note})
        elapsed+=duration
        print(f'{name}: {duration}s; total {elapsed:g}s',flush=True)
    concat=WORK/'concat.txt'
    concat.write_text('\n'.join("file '"+p.as_posix()+"'" for p in segments),encoding='utf-8')
    if OUT.exists():
        raise FileExistsError(f'Preservar vídeo final existente: {OUT}')
    run(['-f','concat','-safe','0','-i',str(concat),'-map','0:v:0','-c','copy','-an','-movflags','+faststart',str(OUT)],WORK/'montagem-ffmpeg.log')
    (WORK/'timeline.json').write_text(json.dumps({'duracao_s':elapsed,'resolucao':[1600,900],'fps':25,'audio':False,'cenas':timeline},ensure_ascii=False,indent=2),encoding='utf-8')
    run(['-v','error','-xerror','-i',str(OUT),'-map','0:v:0','-f','null','-'],WORK/'decodificacao.log')
    print(f'Vídeo montado e decodificado sem erros: {OUT} ({elapsed:g}s)',flush=True)


if __name__=='__main__':
    main()

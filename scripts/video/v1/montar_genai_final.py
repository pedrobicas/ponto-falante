"""Monta capturas reais e cartões editoriais, sem áudio. Não lê conjuntos de avaliação.

    python scripts/video/montar_genai_final.py <timeline.json>

Cada trecho referencia o bruto e os tempos exatos; cortes não substituem respostas.
"""
from pathlib import Path
import json, subprocess, sys, textwrap
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
FF = ROOT / '.validation/video-tools/imageio_ffmpeg/binaries/ffmpeg-win-x86_64-v9.0.2.exe'
WORK = ROOT / 'output/playwright/genai-montagem'
OUT = ROOT / 'entregaveis'
WORK.mkdir(parents=True, exist_ok=True)
OUT.mkdir(exist_ok=True)
BG, INK, GREEN, MUTED, GOLD = '#F4F7F3', '#163C32', '#123E34', '#527067', '#E6C86C'

def font(size, bold=False):
    return ImageFont.truetype('C:/Windows/Fonts/segoeui'+('b' if bold else '')+'.ttf', size)

def text(d,xy,t,size=30,fill=INK,bold=False):
    d.text(xy,t,font=font(size,bold),fill=fill)

def lines(d,xy,t,size=30,width=66,fill=INK,bold=False):
    x,y=xy
    for line in textwrap.wrap(t,width):
        text(d,(x,y),line,size,fill,bold);y+=size+13
    return y

def card(s, dest):
    im=Image.new('RGB',(1600,900),BG);d=ImageDraw.Draw(im)
    d.rectangle((0,0,1600,72),fill=GREEN)
    text(d,(58,18),'ponto. falante',28,'white',True)
    text(d,(1130,23),'GENAI · FIAP 2026.2',23,GOLD,True)
    text(d,(70,136),s.get('eyebrow','DEMONSTRAÇÃO REAL'),23,MUTED,True)
    lines(d,(66,191),s['title'],56,45,INK,True)
    y=340
    for n,item in enumerate(s['lines']):
        d.rounded_rectangle((68,y-8,1532,y+70),radius=12,fill='white')
        text(d,(91,y+9),f'{n+1:02d}',27,GREEN,True)
        lines(d,(160,y+7),item,29,86)
        y+=100
    text(d,(70,841),s.get('note','ponto-falante.onrender.com · Capturas de 14/11/2026'),22,MUTED)
    im.save(dest)

def frame(s,dest):
    im=Image.new('RGBA',(1600,900),(0,0,0,0));d=ImageDraw.Draw(im)
    d.rectangle((0,0,1600,55),fill=GREEN)
    text(d,(36,11),s['title'],25,'white',True)
    d.rectangle((0,855,1600,900),fill=GREEN)
    text(d,(36,865),s.get('note','Produção real · 14/11/2026 · sem áudio para narração própria'),20,'white')
    im.save(dest)

def run(args):
    r=subprocess.run([str(FF),'-hide_banner','-loglevel','error','-y',*map(str,args)],capture_output=True)
    if r.returncode:raise RuntimeError(r.stderr.decode('utf-8',errors='replace')[-2500:])

timeline=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
cursor=0
for n,s in enumerate(timeline['cenas']):
    dest=WORK/f'{n:02d}.mp4'
    dur=float(s['duration'])
    if s.get('source'):
        source=(ROOT/s['source']).resolve()
        over=WORK/f'{n:02d}-frame.png';frame(s,over)
        start=float(s.get('start',0));end=float(s['end'])
        factor=dur/(end-start)
        fc=f'[0:v]trim=start={start}:end={end},setpts=(PTS-STARTPTS)*{factor},scale=1422:800,pad=1600:900:89:55:color=0x123E34,setsar=1[v];[v][1:v]overlay=0:0,fps=25,format=yuv420p[out]'
        run(['-i',source,'-i',over,'-filter_complex',fc,'-map','[out]','-an','-t',dur,'-c:v','libx264','-preset','fast','-crf','18',dest])
    else:
        png=WORK/f'{n:02d}-card.png';card(s,png)
        run(['-loop','1','-i',png,'-t',dur,'-r','25','-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p','-an',dest])
    s['inicio_final']=cursor;s['fim_final']=cursor+dur;cursor+=dur
    print(n,s['title'],dur,flush=True)
(WORK/'concat.txt').write_text('\n'.join("file '"+str((WORK/f'{i:02d}.mp4').resolve()).replace('\\','/')+"'" for i in range(len(timeline['cenas']))),encoding='utf-8')
run(['-f','concat','-safe','0','-i',WORK/'concat.txt','-c','copy','-an','-movflags','+faststart',OUT/'Ponto_Falante_GenAI.mp4'])
timeline['duracao_segundos']=cursor
(OUT/'Ponto_Falante_GenAI.timeline.json').write_text(json.dumps(timeline,ensure_ascii=False,indent=2),encoding='utf-8')
print('FINAL',cursor,flush=True)

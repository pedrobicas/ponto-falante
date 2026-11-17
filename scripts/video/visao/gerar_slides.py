"""Gera os slides 1920x1080 do vídeo de Visão a partir dos arquivos reais do repositório (métricas, gráficos, fotos).

    python scripts/video/visao/gerar_slides.py . scripts/video/visao

Fonte Inter (Linux); sem ela, usa Segoe UI (Windows). Os slides são montados com as cenas reais por
scripts/video/compor.py usando scripts/video/visao/edl_visao.json.
"""
import json, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

REPO = Path(sys.argv[1]); OUT = Path(sys.argv[2]); OUT.mkdir(parents=True, exist_ok=True)
V = REPO / "visao"; R = V / "resultados"
W, H = 1920, 1080
BG, INK, MUTED, ACC, ACC2, LINE = (247, 245, 240), (30, 30, 36), (96, 98, 110), (19, 102, 79), (194, 24, 91), (216, 214, 206)
FD = "/usr/share/fonts/opentype/inter/"
SEGOE = {"Regular": "segoeui.ttf", "Medium": "segoeui.ttf", "SemiBold": "seguisb.ttf", "Bold": "segoeuib.ttf"}
def F(size, w="Regular"):
    try:
        return ImageFont.truetype(FD + f"Inter-{w}.otf", size)
    except OSError:
        return ImageFont.truetype("C:/Windows/Fonts/" + SEGOE[w], size)
def FDsp(size, w="Bold"):
    try:
        return ImageFont.truetype(FD + f"InterDisplay-{w}.otf", size)
    except OSError:
        return F(size, w)

def base(kicker=None):
    im = Image.new("RGB", (W, H), BG); d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W, 10], fill=ACC)
    if kicker:
        d.text((120, 92), kicker.upper(), font=F(26, "SemiBold"), fill=ACC)
    d.text((120, H - 70), "Ponto Falante · Applied Computer Vision · GS 2026.2 · FIAP", font=F(22), fill=MUTED)
    return im, d

def wrap(d, text, font, maxw):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if d.textlength(t, font=font) <= maxw: cur = t
        else: lines.append(cur); cur = w
    if cur: lines.append(cur)
    return lines

def para(d, xy, text, font, maxw, fill=INK, gap=1.35):
    x, y = xy
    for ln in wrap(d, text, font, maxw):
        d.text((x, y), ln, font=font, fill=fill); y += int(font.size * gap)
    return y

def fit(path, box_w, box_h, radius=18, border=True):
    img = Image.open(path).convert("RGB")
    s = min(box_w / img.width, box_h / img.height)
    img = img.resize((int(img.width * s), int(img.height * s)), Image.LANCZOS)
    mask = Image.new("L", img.size, 0); ImageDraw.Draw(mask).rounded_rectangle([0, 0, *img.size], radius, fill=255)
    return img, mask

def paste(im, path, x, y, bw, bh, center=True, radius=18):
    img, mask = fit(path, bw, bh, radius)
    ox = x + (bw - img.width) // 2 if center else x
    oy = y + (bh - img.height) // 2 if center else y
    sh = Image.new("L", (img.width + 40, img.height + 40), 0)
    ImageDraw.Draw(sh).rounded_rectangle([20, 24, img.width + 20, img.height + 24], radius, fill=70)
    sh = sh.filter(ImageFilter.GaussianBlur(12))
    im.paste((0, 0, 0), (ox - 20, oy - 20), sh)
    im.paste(img, (ox, oy), mask)
    return ox, oy, img.width, img.height

def credit(d, x, y, text):
    d.text((x, y), text, font=F(18), fill=MUTED)

m = json.loads((R / "metricas.json").read_text(encoding="utf-8"))

# 1 abertura
im, d = base()
d.text((120, 200), "GLOBAL SOLUTION 2026.2 · CITIZENTECH · ENGENHARIA DE SOFTWARE", font=F(28, "SemiBold"), fill=ACC)
d.text((112, 260), "Ponto Falante", font=FDsp(150), fill=INK)
d.text((120, 440), "Applied Computer Vision", font=F(46, "Medium"), fill=INK)
d.text((120, 500), "Atividade “Enxergando o mundo real”", font=F(34), fill=INK)
para(d, (120, 565), "Detecção de ônibus e leitura da linha no letreiro para passageiros com deficiência visual",
     F(32), 900, MUTED)
d.line([120, 680, 960, 680], fill=LINE, width=2)
mem = ["Pedro Henrique Bicas Couto · RM99534", "Bryan Willian · RM551305", "Felipe Masera Terra · RM99405",
       "Gabriel Fernandes Doms · RM98630", "Lucas Vassão Braga · RM98607"]
y = 710
for t in mem: d.text((120, y), t, font=F(30), fill=INK); y += 46
ox, oy, iw, ih = paste(im, Path(__file__).parent / "quadro_647P.png", 1080, 300, 740, 560)
credit(d, ox, oy + ih + 14, "Saída real do modelo (src/demo.py). Foto: Rafael Delazari (CC BY 2.0), Wikimedia Commons")
im.save(OUT / "01_abertura.jpg", quality=92)

# 2 problema
im, d = base("O problema")
d.text((120, 150), "Qual ônibus está parando?", font=FDsp(78), fill=INK)
y = 290
for t in ["A linha está no letreiro: uma informação só visual.",
          "Quem é cego, tem baixa visão ou é idoso precisa pedir ajuda, fazer sinal para todos os ônibus ou perde a condução.",
          "Apps de previsão dizem quando um ônibus deve chegar, não qual está de fato à frente da pessoa.",
          "Objetivo: transformar a imagem do letreiro em uma frase falada, sem nunca anunciar a linha errada."]:
    d.ellipse([124, y + 16, 140, y + 32], fill=ACC)
    y = para(d, (170, y), t, F(36), 700) + 26
ox, oy, iw, ih = paste(im, V / "amostras/imagens/demo/04_2100-10.jpg", 1000, 170, 800, 780)
credit(d, ox, oy + ih + 14, "Foto: Meliassp (CC BY 3.0), Wikimedia Commons")
im.save(OUT / "02_problema.jpg", quality=92)

# 3 dataset
im, d = base("Dataset próprio · 100% São Paulo")
d.text((120, 150), "Fotos livres + modelos professores + revisão humana", font=FDsp(62), fill=INK)
steps = [("342", "fotos de ônibus da capital\nWikimedia Commons\n(licença livre)"),
         ("211", "com ônibus, pré-rotuladas\npor YOLO11x e\nGrounding DINO"),
         ("−13", "descartadas na revisão\nhumana (maquetes, fotos\nantigas, rótulos errados)"),
         ("198", "imagens finais:\n225 ônibus e\n152 letreiros")]
x = 120
for i, (n, t) in enumerate(steps):
    d.rounded_rectangle([x, 290, x + 380, 580], 22, fill=(255, 255, 255), outline=LINE, width=2)
    d.text((x + 34, 316), n, font=FDsp(92), fill=ACC2 if n.startswith("−") else ACC)
    yy = 440
    for ln in t.split("\n"): d.text((x + 36, yy), ln, font=F(26), fill=INK); yy += 36
    if i < 3: d.text((x + 392, 395), "→", font=F(54, "Bold"), fill=MUTED)
    x += 440
y = para(d, (120, 640), "Não existe dataset público de letreiros de ônibus paulistanos rotulados. Autor, licença e URL de cada foto "
         "ficam registrados em docs/creditos_imagens.csv; cada descarte tem o motivo em ferramentas/revisao_descartes.txt.",
         F(32), 1000, INK)
para(d, (120, y + 20), "Divisão com semente fixa: 138 treino · 39 validação · 21 teste (nunca usado no treino).", F(32, "SemiBold"), 1000, ACC)
demo = sorted((V / "amostras/imagens/demo").glob("0*.jpg"))
for k, f in enumerate(demo[:4]):
    paste(im, f, 1200 + (k % 2) * 310, 630 + (k // 2) * 190, 290, 170, radius=10)
credit(d, 1200, 1012, "Exemplos de fotos de SP do Wikimedia Commons (créditos no repositório)")
im.save(OUT / "03_dataset.jpg", quality=92)

# 4 treino
im, d = base("Treinamento customizado")
d.text((120, 150), "YOLO11 nano · 2 classes: ônibus e letreiro", font=FDsp(62), fill=INK)
y = 280
for t in ["Transfer learning a partir do YOLO11n (COCO), 640 px, até 80 épocas, parada antecipada (paciência 20).",
          "Aumento de dados: brilho e saturação, pequenas rotações, deslocamento, zoom e mosaico.",
          "Sem espelhamento horizontal: letreiro espelhado não existe no mundo real.",
          "“Letreiro” não existe no COCO: por isso o treino customizado."]:
    d.ellipse([124, y + 14, 138, y + 28], fill=ACC)
    y = para(d, (165, y), t, F(31), 560) + 22
paste(im, R / "results.png", 760, 250, 1060, 640)
credit(d, 760, 905, "Curvas de perda e métricas por época (resultados/results.png)")
im.save(OUT / "04_treino.jpg", quality=92)

# 5 metricas
im, d = base("Resultados no conjunto de teste")
d.text((120, 150), "Imagens que o modelo nunca viu", font=FDsp(62), fill=INK)
pc = m["por_classe"]
rows = [("Classe", "Precisão", "Recall", "mAP50", "mAP50-95"),
        ("ônibus", pc["onibus"]["precisao"], pc["onibus"]["recall"], pc["onibus"]["map50"], pc["onibus"]["map50_95"]),
        ("letreiro", pc["letreiro"]["precisao"], pc["letreiro"]["recall"], pc["letreiro"]["map50"], pc["letreiro"]["map50_95"]),
        ("todas", m["precisao"], m["recall"], m["map50"], m["map50_95"])]
cols = [120, 340, 520, 680, 840]; y = 270
for i, r in enumerate(rows):
    if i == 0: d.rectangle([110, y - 10, 1030, y + 52], fill=ACC)
    elif i == 3: d.rectangle([110, y - 10, 1030, y + 52], fill=(232, 240, 236))
    for c, val in zip(cols, r):
        txt = val if isinstance(val, str) else f"{val:.3f}".replace(".", ",")
        d.text((c, y), txt, font=F(32, "Bold" if i in (0, 3) else "Regular"), fill=(255, 255, 255) if i == 0 else INK)
    y += 70
o = m["ocr"]
d.text((120, 590), "Leitura da linha (OCR, um único quadro)", font=F(34, "SemiBold"), fill=INK)
cards = [(f"{o['acertos']}/{o['total']}", "letreiros com código\nlidos corretamente", ACC),
         (str(o["erros"]), "linhas erradas\nanunciadas", ACC2),
         (f"{o['absteve_corretamente']}/{o['letreiros_so_destino']}", "só destino: avisou\n“não consegui ler”", ACC)]
x = 120
for n, t, c in cards:
    d.rounded_rectangle([x, 650, x + 290, 900], 20, fill=(255, 255, 255), outline=LINE, width=2)
    d.text((x + 26, 668), n, font=FDsp(80), fill=c)
    yy = 790
    for ln in t.split("\n"): d.text((x + 28, yy), ln, font=F(25), fill=INK); yy += 34
    x += 315
paste(im, R / "confusion_matrix_normalized.png", 1100, 230, 720, 560)
credit(d, 1100, 810, "Matriz de confusão normalizada (teste)")
d.text((1100, 860), f"Inferência: {m['velocidade_ms']['inference']} ms por imagem (GPU de treino)".replace(".", ","), font=F(26), fill=MUTED)
im.save(OUT / "05_metricas.jpg", quality=92)

# 10 conclusao
im, d = base("Conclusão")
d.text((120, 150), "Imagem que vira informação falada", font=FDsp(66), fill=INK)
y = 290
for t in ["LGPD: nenhuma foto é guardada. O serviço devolve só o resultado; o que é exibido tem rostos e placas borrados.",
          "Segurança: só afirma uma linha que passa no ponto. Na dúvida, avisa que não conseguiu ler.",
          "Integrado ao MVP publicado: conferência do letreiro pelo celular no embarque assistido.",
          "Próximos passos: fotos de noite e chuva, leitor específico para letreiro de LED e piloto com câmera real."]:
    d.ellipse([124, y + 16, 140, y + 32], fill=ACC)
    y = para(d, (170, y), t, F(34), 1550) + 24
d.line([120, 790, 1800, 790], fill=LINE, width=2)
d.text((120, 820), "github.com/pedrobicas/ponto-falante  ·  pasta visao/", font=F(40, "SemiBold"), fill=ACC)
d.text((120, 885), "ponto-falante.onrender.com/embarque", font=F(34), fill=INK)
para(d, (120, 950), "Fotos: Wikimedia Commons (CC BY / CC BY-SA / CC0), créditos em visao/docs/creditos_imagens.csv. "
     "Modelos: YOLO11 (Ultralytics), Grounding DINO, EasyOCR, YuNet.", F(20), 1680, MUTED)
im.save(OUT / "10_conclusao.jpg", quality=92)
print("ok")

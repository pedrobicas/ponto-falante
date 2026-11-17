"""
Passo 2 do dataset: pré-rotulagem automática das fotos de São Paulo.

Não há dataset público com letreiros de ônibus de SP já rotulados, e não havia
tempo para rotular à mão. Então usamos dois modelos "professores":

  - onibus   -> YOLO11 grande pré-treinado no COCO (classe 'bus' = 5). É preciso, mas
                pesado demais para rodar num ponto de ônibus.
  - letreiro -> Grounding DINO (detector de vocabulário aberto, IDEA-Research):
                recebe uma descrição em texto ("bus destination sign") e procura isso
                na imagem. Ele não foi treinado para letreiros de SP e também marca
                papéis colados no para-brisa e o número de frota; por isso filtramos:
                o letreiro precisa estar DENTRO de um ônibus, no TOPO dele, e ter
                formato de faixa (bem mais largo que alto). Fica 1 letreiro por ônibus.
                (Testamos antes o YOLO-World: ele marcava o ônibus inteiro como
                letreiro, então foi descartado.)

Os rótulos gerados passam por REVISÃO HUMANA (folhas de miniaturas em
dados/revisao/) antes do treino. O modelo final (YOLO nano, 2 classes) é treinado
com esses rótulos revisados: rápido, leve e especializado no nosso problema.

  python ferramentas/pre_rotular.py --entrada dados/commons/images --saida dados/rotulado
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import cv2
import numpy as np

CLASSE_BUS_COCO = 5
TEXTO_LETREIRO = "bus destination sign. electronic sign. route number display."
MODELO_DINO = "IDEA-Research/grounding-dino-base"


def dentro(cx: float, cy: float, caixa) -> bool:
    x1, y1, x2, y2 = caixa
    return x1 <= cx <= x2 and y1 <= cy <= y2


def filtrar_letreiros(candidatos, onibus):
    """Mantém 1 letreiro plausível por ônibus: dentro dele, no topo, formato de faixa."""
    aceitos = []
    for bx1, by1, bx2, by2 in onibus:
        bw, bh = bx2 - bx1, by2 - by1
        bons = []
        for conf, (x1, y1, x2, y2) in candidatos:
            w, h = x2 - x1, y2 - y1
            cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
            if h <= 0 or w / h < 2.2:                      # faixa horizontal
                continue
            if not dentro(cx, cy, (bx1, by1, bx2, by2)):
                continue
            if (cy - by1) / bh > 0.35:                     # só o topo do ônibus
                continue
            if not (0.08 * bw <= w <= 0.8 * bw) or w < 40:  # nem o ônibus todo, nem ilegível
                continue
            bons.append((conf, (x1, y1, x2, y2)))
        if bons:
            melhor = max(bons)
            if all(iou(melhor[1], a[1]) < 0.3 for a in aceitos):
                aceitos.append(melhor)
    return aceitos


def iou(a, b) -> float:
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    uniao = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / uniao if uniao else 0.0


def para_yolo(caixa, w, h) -> str:
    x1, y1, x2, y2 = caixa
    return f"{(x1 + x2) / 2 / w:.6f} {(y1 + y2) / 2 / h:.6f} {(x2 - x1) / w:.6f} {(y2 - y1) / h:.6f}"


def folha_revisao(itens, destino: Path, por_folha: int = 20):
    """Monta grades 5x4 com as caixas desenhadas e o número de cada foto."""
    destino.mkdir(parents=True, exist_ok=True)
    for f in destino.glob("folha_*.jpg"):
        f.unlink()
    for n in range(0, len(itens), por_folha):
        quadros = []
        for idx, img_path, onibus, letreiros in itens[n:n + por_folha]:
            img = cv2.imread(str(img_path))
            for _, (x1, y1, x2, y2) in onibus:
                cv2.rectangle(img, (int(x1), int(y1)), (int(x2), int(y2)), (255, 170, 0), 4)
            for _, (x1, y1, x2, y2) in letreiros:
                cv2.rectangle(img, (int(x1), int(y1)), (int(x2), int(y2)), (0, 0, 255), 4)
            img = cv2.resize(img, (400, 300))
            cv2.rectangle(img, (0, 0), (70, 34), (0, 0, 0), -1)
            cv2.putText(img, str(idx), (6, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)
            quadros.append(img)
        while len(quadros) % 5:
            quadros.append(np.zeros((300, 400, 3), np.uint8))
        linhas = [np.hstack(quadros[i:i + 5]) for i in range(0, len(quadros), 5)]
        cv2.imwrite(str(destino / f"folha_{n // por_folha:02d}.jpg"), np.vstack(linhas), [cv2.IMWRITE_JPEG_QUALITY, 80])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--entrada", default="dados/commons/images")
    ap.add_argument("--saida", default="dados/rotulado")
    ap.add_argument("--revisao", default="dados/revisao")
    ap.add_argument("--conf-onibus", type=float, default=0.45)
    ap.add_argument("--conf-letreiro", type=float, default=0.2)
    args = ap.parse_args()

    import torch
    from PIL import Image
    from transformers import AutoModelForZeroShotObjectDetection, AutoProcessor
    from ultralytics import YOLO
    professor_onibus = YOLO("yolo11x.pt")
    disp = "cuda" if torch.cuda.is_available() else "cpu"
    proc = AutoProcessor.from_pretrained(MODELO_DINO)
    dino = AutoModelForZeroShotObjectDetection.from_pretrained(MODELO_DINO, use_safetensors=True).to(disp)

    def candidatos_letreiro(img_bgr):
        pil = Image.fromarray(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB))
        ent = proc(images=pil, text=TEXTO_LETREIRO, return_tensors="pt").to(disp)
        with torch.no_grad():
            out = dino(**ent)
        r = proc.post_process_grounded_object_detection(
            out, ent.input_ids, threshold=args.conf_letreiro, text_threshold=args.conf_letreiro,
            target_sizes=[pil.size[::-1]])[0]
        return [(float(sc), tuple(b.tolist())) for sc, b in zip(r["scores"], r["boxes"])]

    saida = Path(args.saida)
    if saida.exists():
        shutil.rmtree(saida)
    (saida / "images").mkdir(parents=True)
    (saida / "labels").mkdir(parents=True)

    itens, sem_onibus, ilegiveis = [], 0, 0
    for idx, img_path in enumerate(sorted(Path(args.entrada).glob("*.jpg"))):
        img = cv2.imread(str(img_path))
        if img is None:              # arquivo corrompido ou que não é imagem
            ilegiveis += 1
            continue
        h, w = img.shape[:2]
        r = professor_onibus.predict(img, conf=args.conf_onibus, classes=[CLASSE_BUS_COCO], verbose=False)[0]
        onibus = [(float(b.conf), tuple(b.xyxy[0].tolist())) for b in r.boxes]
        # ônibus muito pequenos (ao fundo) não ajudam: menos de 3% da imagem
        onibus = [o for o in onibus if (o[1][2] - o[1][0]) * (o[1][3] - o[1][1]) > 0.03 * w * h]
        if not onibus:
            sem_onibus += 1
            continue
        letreiros = filtrar_letreiros(candidatos_letreiro(img), [c for _, c in onibus])

        shutil.copy(img_path, saida / "images" / img_path.name)
        linhas = [f"0 {para_yolo(c, w, h)}" for _, c in onibus] + [f"1 {para_yolo(c, w, h)}" for _, c in letreiros]
        (saida / "labels" / (img_path.stem + ".txt")).write_text("\n".join(linhas) + "\n")
        itens.append((idx, img_path, onibus, letreiros))

    folha_revisao(itens, Path(args.revisao))
    indice = {i: p.name for i, p, *_ in itens}
    (Path(args.revisao) / "indice.json").write_text(json.dumps(indice, indent=0), encoding="utf-8")
    n_let = sum(len(l) for *_, l in itens)
    print(f"Rotuladas: {len(itens)} | sem ônibus (descartadas): {sem_onibus} | ilegíveis: {ilegiveis}")
    print(f"Caixas: onibus={sum(len(o) for _, _, o, _ in itens)} letreiro={n_let}")


if __name__ == "__main__":
    main()

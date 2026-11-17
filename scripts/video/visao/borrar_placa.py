"""Borra a placa do ônibus na miniatura da foto enviada, nas cenas do site gravadas por scripts/video/cap_visao.js.

    python scripts/video/visao/borrar_placa.py <pasta das cenas>

Para cada cena (visao_confere, visao_outra_linha, visao_inconclusivo) cria <cena>_borrada com o mesmo indice.json.
Em cada quadro, a miniatura é localizada por template matching (OpenCV) usando a própria foto de
visao/amostras/imagens/demo/ como modelo:
  1. a escala da miniatura é medida uma vez por cena, no último quadro (foto inteira na tela), em várias escalas;
  2. em cada quadro, procura-se nessa escala o trecho da foto em volta da placa (funciona mesmo com a miniatura
     parcialmente fora da tela);
  3. o retângulo da placa, definido uma vez nas coordenadas da foto original, é projetado pela escala/posição
     encontrada e recebe pixelização + desfoque gaussiano, com margem.
Quadros com correspondência fraca (ainda sem foto na tela) são copiados sem alteração.
O vídeo é depois montado por scripts/video/compor.py com scripts/video/visao/edl_visao.json.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import cv2
import numpy as np

REPO = Path(__file__).resolve().parents[3]
FOTOS = REPO / "visao" / "amostras" / "imagens" / "demo"

# Coordenadas na foto original (1280x960): placa (x0, y0, x1, y1) e o trecho em volta usado para localizar.
CENAS = {
    "visao_confere": ("01_647P-10.jpg", (272, 768, 372, 814), (150, 660, 520, 900)),
    "visao_outra_linha": ("01_647P-10.jpg", (272, 768, 372, 814), (150, 660, 520, 900)),
    "visao_inconclusivo": ("03_destino_sacoma.jpg", (207, 628, 307, 674), (120, 560, 470, 760)),
}
LIMIAR_ESCALA = 0.80   # correlação mínima da foto inteira no último quadro
LIMIAR_QUADRO = 0.70   # correlação mínima do trecho em volta da placa em cada quadro
MARGEM = 0.25          # margem extra em volta da placa (fração da largura/altura)


def cinza(img: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def medir_escala(quadro: np.ndarray, foto: np.ndarray) -> tuple[float, float]:
    """Escala da miniatura no quadro: busca grossa e depois fina, pela foto inteira."""
    q = cinza(quadro)
    f = cinza(foto)
    melhor = (0.0, 0.0)
    for passo, faixa in ((0.01, np.arange(0.20, 0.80, 0.01)), (0.002, None)):
        if faixa is None:
            faixa = np.arange(melhor[1] - 0.012, melhor[1] + 0.012, passo)
        for s in faixa:
            m = cv2.resize(f, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
            if m.shape[0] >= q.shape[0] or m.shape[1] >= q.shape[1]:
                continue
            _, v, _, _ = cv2.minMaxLoc(cv2.matchTemplate(q, m, cv2.TM_CCOEFF_NORMED))
            if v > melhor[0]:
                melhor = (v, float(s))
    return melhor[1], melhor[0]


def borrar(img: np.ndarray, x0: int, y0: int, x1: int, y1: int) -> None:
    h, w = img.shape[:2]
    x0, y0, x1, y1 = max(0, x0), max(0, y0), min(w, x1), min(h, y1)
    if x1 - x0 < 2 or y1 - y0 < 2:
        return
    reg = img[y0:y1, x0:x1]
    pequeno = cv2.resize(reg, (max(1, (x1 - x0) // 8), max(1, (y1 - y0) // 8)), interpolation=cv2.INTER_AREA)
    reg = cv2.resize(pequeno, (x1 - x0, y1 - y0), interpolation=cv2.INTER_NEAREST)
    img[y0:y1, x0:x1] = cv2.GaussianBlur(reg, (0, 0), 6)


def processar(cenas: Path, nome: str) -> dict:
    arq_foto, placa, trecho = CENAS[nome]
    foto = cv2.imread(str(FOTOS / arq_foto))
    orig, dest = cenas / nome, cenas / (nome + "_borrada")
    indice = json.loads((orig / "indice.json").read_text(encoding="utf-8"))
    quadros = sorted(indice["quadros"], key=lambda x: x["t"])
    if dest.exists():
        shutil.rmtree(dest)
    (dest / "q").mkdir(parents=True)
    shutil.copy2(orig / "indice.json", dest / "indice.json")

    escala, conf = medir_escala(cv2.imread(str(orig / "q" / quadros[-1]["a"])), foto)
    if conf < LIMIAR_ESCALA:
        raise SystemExit(f"{nome}: miniatura não encontrada no último quadro (correlação {conf:.2f})")
    tx0, ty0, tx1, ty1 = trecho
    modelo = cv2.resize(cinza(foto[ty0:ty1, tx0:tx1]), None, fx=escala, fy=escala, interpolation=cv2.INTER_AREA)
    px0, py0, px1, py1 = placa
    mx, my = (px1 - px0) * MARGEM, (py1 - py0) * MARGEM

    borrados = 0
    for item in sorted(p.name for p in (orig / "q").glob("*.jpg")):
        img = cv2.imread(str(orig / "q" / item))
        _, v, _, (lx, ly) = cv2.minMaxLoc(cv2.matchTemplate(cinza(img), modelo, cv2.TM_CCOEFF_NORMED))
        if v < LIMIAR_QUADRO:
            shutil.copy2(orig / "q" / item, dest / "q" / item)
            continue
        x0 = int(lx + (px0 - tx0 - mx) * escala)
        y0 = int(ly + (py0 - ty0 - my) * escala)
        x1 = int(np.ceil(lx + (px1 - tx0 + mx) * escala))
        y1 = int(np.ceil(ly + (py1 - ty0 + my) * escala))
        borrar(img, x0, y0, x1, y1)
        cv2.imwrite(str(dest / "q" / item), img, [cv2.IMWRITE_JPEG_QUALITY, 95])
        borrados += 1
    total = len(list((orig / "q").glob("*.jpg")))
    return {"cena": nome, "escala_miniatura": round(escala, 3), "correlacao_escala": round(conf, 3),
            "quadros": total, "borrados": borrados}


def main() -> None:
    cenas = Path(sys.argv[1])
    relatorio = [processar(cenas, n) for n in CENAS]
    for r in relatorio:
        print(json.dumps(r, ensure_ascii=False))
    (cenas / "borrar_placa.json").write_text(json.dumps(relatorio, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()

"""
Passos 3 e 4: monta o dataset (70/20/10), treina o YOLO nano e avalia no conjunto de teste.

Entrada: dados/rotulado/{images,labels} (saída de pre_rotular.py) menos as fotos
descartadas na revisão humana (ferramentas/revisao_descartes.txt).

Saídas:
  dataset/                      train/val/test no formato YOLO + data.yaml (fora do Git)
  modelos/best.pt               pesos do modelo final
  resultados/metricas.json      mAP, precisão, recall (geral e por classe), velocidade, dataset
  resultados/dataset.json       composição do dataset
  resultados/*.png              curvas, matriz de confusão, evolução do treino

  python ferramentas/treinar.py
"""
from __future__ import annotations

import argparse
import json
import random
import shutil
from pathlib import Path

SEMENTE = 42
CLASSES = ["onibus", "letreiro"]
RAIZ = Path(__file__).resolve().parents[1]


def descartes() -> set[str]:
    arq = RAIZ / "ferramentas" / "revisao_descartes.txt"
    if not arq.exists():
        return set()
    return {l.split("#")[0].strip() for l in arq.read_text(encoding="utf-8").splitlines() if l.split("#")[0].strip()}


def montar_dataset(origem: Path, destino: Path) -> dict:
    fora = descartes()
    itens = sorted(p for p in (origem / "images").glob("*.jpg") if p.name not in fora)
    random.Random(SEMENTE).shuffle(itens)
    n = len(itens)
    n_tr, n_va = int(n * 0.7), int(n * 0.2)
    partes = {"train": itens[:n_tr], "val": itens[n_tr:n_tr + n_va], "test": itens[n_tr + n_va:]}
    if destino.exists():
        shutil.rmtree(destino)
    conta = {0: 0, 1: 0}
    for split, lista in partes.items():
        (destino / split / "images").mkdir(parents=True)
        (destino / split / "labels").mkdir(parents=True)
        for img in lista:
            rot = origem / "labels" / (img.stem + ".txt")
            shutil.copy(img, destino / split / "images" / img.name)
            shutil.copy(rot, destino / split / "labels" / rot.name)
            for linha in rot.read_text().splitlines():
                if linha.strip():
                    conta[int(linha.split()[0])] += 1
    (destino / "data.yaml").write_text(
        f"path: {destino.resolve().as_posix()}\ntrain: train/images\nval: val/images\ntest: test/images\n"
        f"names:\n  0: onibus\n  1: letreiro\n", encoding="utf-8")
    return {"origem": "Wikimedia Commons (ônibus da cidade de São Paulo) — pré-rotulado + revisão humana",
            "imagens": n, "descartadas_na_revisao": len(fora), "caixas_onibus": conta[0], "caixas_letreiro": conta[1],
            "train": len(partes["train"]), "val": len(partes["val"]), "test": len(partes["test"]),
            "licenca": "CC BY / CC BY-SA / domínio público — ver docs/creditos_imagens.csv"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--origem", default=str(RAIZ / "dados" / "rotulado"))
    ap.add_argument("--dataset", default=str(RAIZ / "dataset"))
    ap.add_argument("--base", default="yolo11n.pt")
    ap.add_argument("--epocas", type=int, default=80)
    ap.add_argument("--img", type=int, default=640)
    ap.add_argument("--lote", type=int, default=16)
    args = ap.parse_args()

    res = RAIZ / "resultados"
    res.mkdir(exist_ok=True)
    (RAIZ / "modelos").mkdir(exist_ok=True)
    dataset = Path(args.dataset)
    comp = montar_dataset(Path(args.origem), dataset)
    (res / "dataset.json").write_text(json.dumps([comp], ensure_ascii=False, indent=2), encoding="utf-8")
    print("Dataset:", comp)

    from ultralytics import YOLO
    modelo = YOLO(args.base)
    treino = modelo.train(data=str(dataset / "data.yaml"), epochs=args.epocas, imgsz=args.img, batch=args.lote,
                          patience=20, seed=SEMENTE, project=str(RAIZ / "runs"), name="ponto_falante", exist_ok=True,
                          workers=2, hsv_v=0.5, hsv_s=0.6, degrees=5, translate=0.1, scale=0.5,
                          fliplr=0.0,  # espelhar inverteria o texto do letreiro
                          mosaic=1.0, close_mosaic=10, plots=True, verbose=False)
    pasta = Path(treino.save_dir) if treino else RAIZ / "runs" / "ponto_falante"
    shutil.copy(pasta / "weights" / "best.pt", RAIZ / "modelos" / "best.pt")
    for f in ["results.png", "labels.jpg"]:
        if (pasta / f).exists():
            shutil.copy(pasta / f, res / f)

    melhor = YOLO(str(RAIZ / "modelos" / "best.pt"))
    m = melhor.val(data=str(dataset / "data.yaml"), split="test", imgsz=args.img,
                   project=str(RAIZ / "runs"), name="teste", exist_ok=True, plots=True)
    por_classe = {}
    for i, idx in enumerate(m.box.ap_class_index):
        p, r, ap50, ap5095 = m.box.class_result(i)
        por_classe[CLASSES[int(idx)]] = {"precisao": round(float(p), 3), "recall": round(float(r), 3),
                                         "map50": round(float(ap50), 3), "map50_95": round(float(ap5095), 3)}
    metricas = {"modelo_base": args.base, "epocas": args.epocas, "tamanho_img": args.img,
                "map50": round(float(m.box.map50), 3), "map50_95": round(float(m.box.map), 3),
                "precisao": round(float(m.box.mp), 3), "recall": round(float(m.box.mr), 3),
                "por_classe": por_classe, "dataset": [comp],
                "velocidade_ms": {k: round(float(v), 1) for k, v in m.speed.items()},
                "hardware": "NVIDIA GeForce RTX 4060 Ti (treino local)"}
    for f in ["confusion_matrix.png", "confusion_matrix_normalized.png", "BoxPR_curve.png", "PR_curve.png"]:
        if (Path(m.save_dir) / f).exists():
            shutil.copy(Path(m.save_dir) / f, res / f)
    (res / "metricas.json").write_text(json.dumps(metricas, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(metricas, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

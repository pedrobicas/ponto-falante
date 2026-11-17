"""
Passo 5: avalia o pipeline completo (YOLO -> recorte -> EasyOCR -> validação da linha)
contra o gabarito resultados/gabarito_ocr.csv, preenchido olhando os letreiros.

O gabarito usa as imagens de VALIDAÇÃO e TESTE (o detector não aprendeu os pesos com elas).
Dois tipos de letreiro:
  - codigo : o letreiro mostra o código da linha (ex.: 695H-10) -> esperamos ler a linha certa;
  - destino: o letreiro mostra só o destino (ex.: SACOMA)      -> o certo é NÃO anunciar linha
             (os letreiros de SP alternam código e destino; a câmera vê vários quadros).

As linhas permitidas (que viriam de GET /pontos/{codigo}/previsoes) são todas as linhas do
gabarito: ~20 linhas, como num corredor movimentado. Isso deixa a validação mais difícil
do que num ponto com 3 ou 4 linhas.

  python ferramentas/avaliar_ocr.py
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import cv2

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from demo import desenhar  # noqa: E402
from detector import DetectorOnibus  # noqa: E402
from privacidade import anonimizar  # noqa: E402


def main():
    res_dir = RAIZ / "resultados"
    gabarito = list(csv.DictReader(open(res_dir / "gabarito_ocr.csv", encoding="utf-8")))
    linhas_ponto = sorted({g["linha_correta"] for g in gabarito if g["linha_correta"]})
    det = DetectorOnibus(str(RAIZ / "modelos" / "best.pt"), conf=0.25, gpu=True)

    detalhes, cont = [], {"acerto": 0, "erro": 0, "nao_leu": 0, "absteve": 0, "falso_anuncio": 0}
    for f in res_dir.glob("exemplo_*.jpg"):
        f.unlink()
    for f in res_dir.glob("falha_*.jpg"):
        f.unlink()
    n_ex = n_fa = 0
    for g in gabarito:
        caminho = RAIZ / "dataset" / g["split"] / "images" / g["imagem"]
        frame = cv2.imread(str(caminho))
        r = det.detectar(frame, linhas_ponto)
        lida = r.leitura.linha if r.leitura else None
        texto = r.leitura.texto_bruto if r.leitura else ""
        if g["tipo"] == "codigo":
            status = "nao_leu" if lida is None else ("acerto" if lida == g["linha_correta"] else "erro")
        else:
            status = "absteve" if lida is None else "falso_anuncio"
        cont[status] += 1
        detalhes.append({"imagem": g["imagem"], "split": g["split"], "tipo": g["tipo"],
                         "correta": g["linha_correta"] or "-", "lida": lida or "-",
                         "confianca": r.leitura.confianca if r.leitura else 0, "status": status,
                         "texto_ocr": texto})
        # Figuras para o relatório (anonimizadas: rostos e placas borrados).
        caixas_onibus = [(x1, y1, x2, y2) for c, _, x1, y1, x2, y2 in r.caixas if c == "onibus"]
        vis = desenhar(anonimizar(frame.copy(), caixas_onibus), r, "")
        if status == "acerto" and n_ex < 6:
            n_ex += 1
            cv2.imwrite(str(res_dir / f"exemplo_{n_ex}.jpg"), vis)
        elif status in ("erro", "nao_leu", "falso_anuncio") and n_fa < 3:
            n_fa += 1
            cv2.imwrite(str(res_dir / f"falha_{n_fa}.jpg"), vis)
        print(f"{status:14s} {g['linha_correta'] or g['tipo']:8s} lida={lida} ocr='{texto}'")

    n_cod = cont["acerto"] + cont["erro"] + cont["nao_leu"]
    n_dest = cont["absteve"] + cont["falso_anuncio"]
    ocr = {"total": n_cod, "acertos": cont["acerto"], "erros": cont["erro"], "nao_leu": cont["nao_leu"],
           "taxa_acerto": round(cont["acerto"] / n_cod, 3) if n_cod else None,
           "taxa_erro": round(cont["erro"] / n_cod, 3) if n_cod else None,
           "letreiros_so_destino": n_dest, "absteve_corretamente": cont["absteve"],
           "falsos_anuncios": cont["falso_anuncio"], "linhas_no_ponto_simulado": len(linhas_ponto),
           "imagens": "validação + teste (não usadas para ajustar os pesos)"}
    with open(res_dir / "ocr_detalhes.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(detalhes[0].keys()))
        w.writeheader()
        w.writerows(detalhes)
    metricas_path = res_dir / "metricas.json"
    m = json.loads(metricas_path.read_text(encoding="utf-8")) if metricas_path.exists() else {}
    m["ocr"] = ocr
    metricas_path.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(ocr, ensure_ascii=False, indent=2))
    print(f"{n_ex} exemplos e {n_fa} falhas salvos em resultados/")


if __name__ == "__main__":
    main()

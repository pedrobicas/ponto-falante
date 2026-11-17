"""
LGPD by design: antes de MOSTRAR ou SALVAR qualquer frame, borramos rostos e a
região provável da placa do ônibus. Nenhuma imagem é enviada para a API — só o
resultado (linha lida e confiança).

- Rostos: YuNet (cv2.FaceDetectorYN, modelo oficial do opencv_zoo, ~230 KB, roda em CPU).
  Se o arquivo não existir e o OpenCV for 4.x, usa o detector Haar que vem com ele.
- Placa: heurística — borramos a faixa inferior da caixa do ônibus (para-choque),
  em toda a largura: com o ônibus de lado ou na diagonal, a placa pode estar à
  esquerda ou à direita, então borrar só o centro deixava placas legíveis.
  (A placa de um ônibus de frota não identifica uma pessoa, mas borramos por cautela.)
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

import cv2
import numpy as np

log = logging.getLogger("ponto_falante.privacidade")
ARQUIVO_YUNET = "face_detection_yunet_2023mar.onnx"
ARQUIVO_HAAR = "haarcascade_frontalface_default.xml"
_detector_rosto = None   # ("yunet", det) ou ("haar", det)
_carregado = False


def _rostos():
    """Carrega o detector de rostos uma única vez."""
    global _detector_rosto, _carregado
    if _carregado:
        return _detector_rosto
    _carregado = True
    pasta_modelos = Path(__file__).parent.parent / "modelos"
    yunet = Path(os.getenv("YUNET_ROSTO", "") or pasta_modelos / ARQUIVO_YUNET)
    if yunet.is_file() and hasattr(cv2, "FaceDetectorYN"):
        _detector_rosto = ("yunet", cv2.FaceDetectorYN.create(str(yunet), "", (320, 320), 0.6))
        return _detector_rosto
    if hasattr(cv2, "CascadeClassifier") and hasattr(cv2, "data"):   # OpenCV 4.x
        det = cv2.CascadeClassifier(os.path.join(cv2.data.haarcascades, ARQUIVO_HAAR))
        if not det.empty():
            _detector_rosto = ("haar", det)
            return _detector_rosto
    log.warning("Detector de rostos não encontrado (modelos/%s). Rostos NÃO serão borrados.", ARQUIVO_YUNET)
    return None


def borrar_regiao(img: np.ndarray, x1: int, y1: int, x2: int, y2: int) -> None:
    h, w = img.shape[:2]
    x1, y1, x2, y2 = max(0, x1), max(0, y1), min(w, x2), min(h, y2)
    if x2 - x1 < 2 or y2 - y1 < 2:
        return
    roi = img[y1:y2, x1:x2]
    k = max(15, ((min(roi.shape[:2]) // 3) | 1))  # kernel ímpar proporcional ao tamanho
    img[y1:y2, x1:x2] = cv2.GaussianBlur(roi, (k, k), 0)


def detectar_rostos(img: np.ndarray) -> list[tuple[int, int, int, int]]:
    """Caixas (x, y, w, h) dos rostos encontrados."""
    det = _rostos()
    if det is None:
        return []
    tipo, d = det
    if tipo == "yunet":
        h, w = img.shape[:2]
        d.setInputSize((w, h))
        _, faces = d.detect(img)
        return [tuple(int(v) for v in f[:4]) for f in (faces if faces is not None else [])]
    cinza = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return [tuple(r) for r in d.detectMultiScale(cinza, scaleFactor=1.1, minNeighbors=5, minSize=(24, 24))]


def borrar_rostos(img: np.ndarray) -> int:
    rostos = detectar_rostos(img)
    for (x, y, w, h) in rostos:
        m = int(0.2 * max(w, h))   # margem: borra também cabelo e contorno
        borrar_regiao(img, x - m, y - m, x + w + m, y + h + m)
    return len(rostos)


def borrar_placa_provavel(img: np.ndarray, caixa_onibus: tuple[int, int, int, int]) -> None:
    x1, y1, x2, y2 = caixa_onibus
    w, h = x2 - x1, y2 - y1
    borrar_regiao(img, x1, int(y1 + 0.72 * h), x2, int(y1 + 0.97 * h))


def anonimizar(img: np.ndarray, caixas_onibus: list[tuple[int, int, int, int]]) -> np.ndarray:
    """Devolve uma cópia anonimizada do frame."""
    saida = img.copy()
    borrar_rostos(saida)
    for c in caixas_onibus:
        borrar_placa_provavel(saida, c)
    return saida

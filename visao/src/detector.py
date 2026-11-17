"""
Detector do Ponto Falante: YOLO treinado (classes "onibus" e "letreiro") + OCR no letreiro.

Fluxo por frame:
  1. YOLO encontra ônibus e letreiros.
  2. O letreiro é recortado (com margem), ampliado e passado no OCR (EasyOCR) em
     3 versões: colorida, suavizada (junta os pontinhos do LED) e com contraste (CLAHE).
  3. O texto é validado contra as linhas do ponto (leitor_letreiro.ler_linha).
"""
from __future__ import annotations

import cv2
import numpy as np

from anunciador import ResultadoFrame
from leitor_letreiro import LeituraLinha, ler_linha

CLASSE_ONIBUS = "onibus"
CLASSE_LETREIRO = "letreiro"
CARACTERES_OCR = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789- "


def preparar_recorte(recorte: np.ndarray) -> np.ndarray:
    """Amplia e aumenta o contraste do letreiro (CLAHE)."""
    return versoes_recorte(recorte)[2]


def versoes_recorte(recorte: np.ndarray) -> list[np.ndarray]:
    """Três versões do letreiro para o OCR. Cada uma funciona melhor num tipo de letreiro:
    - colorida ampliada: letreiros nítidos;
    - brilho suavizado: LED de matriz de pontos (o desfoque junta os pontos em traços);
    - cinza com CLAHE: letreiros com pouco contraste ou contra a luz."""
    h = recorte.shape[0]
    escala = max(1.0, 160 / max(h, 1))  # letreiro pequeno -> amplia até ~160 px de altura
    ampliado = cv2.resize(recorte, None, fx=escala, fy=escala, interpolation=cv2.INTER_CUBIC)
    brilho = cv2.cvtColor(ampliado, cv2.COLOR_BGR2HSV)[:, :, 2]
    k = max(3, int(ampliado.shape[0] / 25) | 1)
    suavizado = cv2.GaussianBlur(brilho, (k, k), 0)
    cinza = cv2.cvtColor(ampliado, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(cinza)
    return [ampliado, suavizado, clahe]


def ler_resultados_ocr(resultados, linhas_permitidas, limiar=0.75, rejeitar_ambiguas=False,
                       ler_fora_da_lista=False) -> LeituraLinha:
    """Valida o OCR contra as linhas do ponto. Com ler_fora_da_lista, um código legível que não está na lista volta
    marcado como não validado (confiança reduzida), em vez de ser descartado ou forçado para a linha mais parecida:
    assim o celular pode avisar "parece ser outra linha" sem nunca afirmar uma linha que o letreiro não mostrou."""
    leitura = ler_linha(resultados, linhas_permitidas, limiar=limiar, rejeitar_ambiguas=rejeitar_ambiguas)
    if leitura.linha is None and linhas_permitidas and ler_fora_da_lista:
        fora = ler_linha(resultados, None)
        if fora.linha:
            fora.validada = False
            return fora
    return leitura


class DetectorOnibus:
    def __init__(self, pesos: str = "modelos/best.pt", conf: float = 0.35, usar_ocr: bool = True, gpu: bool = False,
                 rejeitar_ambiguas: bool = False, limiar: float = 0.75, ler_fora_da_lista: bool = False):
        """Os três últimos parâmetros mudam a leitura só para a conferência pelo celular (servico/app.py); os
        padrões reproduzem o comportamento avaliado no relatório."""
        from ultralytics import YOLO  # import aqui para os testes não exigirem a biblioteca
        self.modelo = YOLO(pesos)
        self.conf = conf
        self.rejeitar_ambiguas = rejeitar_ambiguas
        self.limiar = limiar
        self.ler_fora_da_lista = ler_fora_da_lista
        self.ocr = None
        if usar_ocr:
            import easyocr
            self.ocr = easyocr.Reader(["pt", "en"], gpu=gpu, verbose=False)

    def ler_letreiro(self, frame: np.ndarray, caixa, linhas_permitidas) -> LeituraLinha:
        x1, y1, x2, y2 = caixa
        mx, my = int(0.06 * (x2 - x1)), int(0.15 * (y2 - y1))   # margem: a caixa às vezes corta o texto
        recorte = frame[max(0, y1 - my):y2 + my, max(0, x1 - mx):x2 + mx]
        if self.ocr is None or recorte.size == 0:
            return LeituraLinha(None, 0.0, "")
        resultados = []
        for versao in versoes_recorte(recorte):
            resultados += [(texto, float(conf)) for _, texto, conf in
                           self.ocr.readtext(versao, allowlist=CARACTERES_OCR, detail=1)]
        # ler_linha valida cada leitura contra as linhas do ponto e fica com a mais confiável
        return ler_resultados_ocr(resultados, linhas_permitidas, self.limiar, self.rejeitar_ambiguas,
                                  self.ler_fora_da_lista)

    def detectar(self, frame: np.ndarray, linhas_permitidas: list[str] | None = None) -> ResultadoFrame:
        res = self.modelo.predict(frame, conf=self.conf, verbose=False)[0]
        nomes = res.names
        caixas, onibus, letreiros = [], [], []
        for box in res.boxes:
            classe = nomes[int(box.cls)]
            conf = float(box.conf)
            x1, y1, x2, y2 = (int(v) for v in box.xyxy[0].tolist())
            caixas.append((classe, conf, x1, y1, x2, y2))
            if classe == CLASSE_ONIBUS:
                onibus.append((conf, (x1, y1, x2, y2)))
            elif classe == CLASSE_LETREIRO:
                letreiros.append((conf, (x1, y1, x2, y2)))

        # Lê o letreiro de maior confiança (normalmente o do ônibus mais próximo).
        leitura = None
        if letreiros:
            conf_l, caixa_l = max(letreiros, key=lambda t: t[0])
            leitura = self.ler_letreiro(frame, caixa_l, linhas_permitidas)
            leitura.confianca = round(leitura.confianca * conf_l, 3)

        # Letreiro visível também indica ônibus, mesmo se a caixa do ônibus não saiu.
        tem_onibus = bool(onibus) or bool(letreiros)
        conf_onibus = max([c for c, _ in onibus] + [c for c, _ in letreiros] + [0.0])
        return ResultadoFrame(tem_onibus, conf_onibus, leitura, caixas)

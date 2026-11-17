"""
Demonstração em "tempo real" da câmera do ponto (simulada por vídeo, pasta de imagens ou webcam).

Exemplos:
  python src/demo.py --fonte amostras/onibus.mp4 --ponto 260015039 --saida resultados/demo.mp4
  python src/demo.py --fonte amostras/imagens/ --sem-api
  python src/demo.py --fonte 0 --mostrar            # webcam

Para cada anúncio: mostra a frase na tela e envia {"ponto","linha_lida","confianca"}
para POST /deteccoes. Os frames exibidos/salvos passam por anonimização (LGPD).
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
import unicodedata
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from anunciador import Anunciador, ResultadoFrame  # noqa: E402
from cliente_api import ClienteAPI  # noqa: E402
from privacidade import anonimizar  # noqa: E402

CORES = {"onibus": (255, 170, 0), "letreiro": (0, 200, 255)}
EXTENSOES_IMG = {".jpg", ".jpeg", ".png", ".webp"}
TAMANHO_QUADRO = (1280, 720)   # fotos de tamanhos diferentes viram quadros iguais (vídeo exige)


def enquadrar(img, tamanho=TAMANHO_QUADRO):
    """Redimensiona mantendo a proporção e completa com faixas pretas."""
    w, h = tamanho
    escala = min(w / img.shape[1], h / img.shape[0])
    nova = cv2.resize(img, (int(img.shape[1] * escala), int(img.shape[0] * escala)))
    quadro = np.zeros((h, w, 3), np.uint8)
    y, x = (h - nova.shape[0]) // 2, (w - nova.shape[1]) // 2
    quadro[y:y + nova.shape[0], x:x + nova.shape[1]] = nova
    return quadro


def configurar_log():
    Path("logs").mkdir(exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                        handlers=[logging.FileHandler("logs/visao.log", encoding="utf-8"), logging.StreamHandler()],
                        force=True)  # força mesmo se o Colab/pytest já tiver configurado o logging


def frames_da_fonte(fonte: str, repetir_imagem: int):
    """Gera frames de um vídeo, webcam ou pasta de imagens.
    Cada imagem é repetida algumas vezes para simular um ônibus parado diante da câmera."""
    caminho = Path(fonte)
    if caminho.is_dir():
        for img_path in sorted(p for p in caminho.iterdir() if p.suffix.lower() in EXTENSOES_IMG):
            img = cv2.imread(str(img_path))
            if img is None:
                continue
            img = enquadrar(img)
            for _ in range(repetir_imagem):
                yield img
            for _ in range(repetir_imagem):   # "ponto vazio" entre uma imagem e outra
                yield None
        return
    cap = cv2.VideoCapture(int(fonte) if fonte.isdigit() else fonte)
    if not cap.isOpened():
        raise SystemExit(f"Não consegui abrir a fonte: {fonte}")
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        yield frame
    cap.release()


def desenhar(frame, resultado, faixa_texto: str):
    for classe, conf, x1, y1, x2, y2 in resultado.caixas:
        cor = CORES.get(classe, (0, 255, 0))
        cv2.rectangle(frame, (x1, y1), (x2, y2), cor, 2)
        cv2.putText(frame, f"{classe} {conf:.2f}", (x1, max(15, y1 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, cor, 2)
    if resultado.leitura and resultado.leitura.linha:
        cv2.putText(frame, f"OCR: {resultado.leitura.linha} ({resultado.leitura.confianca:.2f})",
                    (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 200, 255), 2)
    if faixa_texto:
        h, w = frame.shape[:2]
        cv2.rectangle(frame, (0, h - 50), (w, h), (20, 20, 20), -1)
        # OpenCV não desenha acentos: tiramos só o acento ("Ônibus" -> "Onibus").
        # A tela/voz do MVP recebe a frase completa, com acentos.
        texto = unicodedata.normalize("NFKD", faixa_texto).encode("ascii", "ignore").decode()
        cv2.putText(frame, texto, (12, h - 16), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
    return frame


def main():
    ap = argparse.ArgumentParser(description="Câmera do Ponto Falante (detecção + leitura da linha)")
    ap.add_argument("--fonte", required=True, help="vídeo, pasta de imagens ou índice da webcam")
    ap.add_argument("--pesos", default="modelos/best.pt")
    ap.add_argument("--ponto", default="PONTO-DEMO", help="código do ponto no MVP")
    ap.add_argument("--api", default=None, help="URL da API (padrão: env PONTO_FALANTE_API ou localhost:8000)")
    ap.add_argument("--sem-api", action="store_true", help="não chama a API (modo offline)")
    ap.add_argument("--linhas", default="", help="linhas do ponto separadas por vírgula, se a API estiver fora")
    ap.add_argument("--saida", default=None, help="salva o vídeo anotado (anonimizado)")
    ap.add_argument("--mostrar", action="store_true", help="abre janela com o vídeo")
    ap.add_argument("--conf", type=float, default=0.35)
    ap.add_argument("--repetir-imagem", type=int, default=10)
    ap.add_argument("--gpu", action="store_true", help="usa a GPU no OCR")
    args = ap.parse_args()

    configurar_log()
    log = logging.getLogger("ponto_falante.demo")

    from detector import DetectorOnibus  # import tardio: só aqui precisamos do YOLO
    detector = DetectorOnibus(args.pesos, conf=args.conf, gpu=args.gpu)
    api = None if args.sem_api else ClienteAPI(args.api)
    linhas_fixas = [l.strip() for l in args.linhas.split(",") if l.strip()]
    anunciador = Anunciador()

    escritor, faixa, faixa_ate = None, "", 0.0
    inicio, n = time.time(), 0
    for frame in frames_da_fonte(args.fonte, args.repetir_imagem):
        agora = time.time()
        if frame is None:  # intervalo sem ônibus (modo pasta)
            anunciador.processar(ResultadoFrame(False), agora)
            continue
        n += 1
        linhas = (api.linhas_do_ponto(args.ponto) if api else []) or linhas_fixas
        resultado = detector.detectar(frame, linhas)
        anuncio = anunciador.processar(resultado, agora)
        if anuncio:
            log.info("ANÚNCIO: %s (confiança %.2f)", anuncio.texto, anuncio.confianca)
            faixa, faixa_ate = anuncio.texto, agora + 4
            if api:
                api.enviar_deteccao(args.ponto, anuncio.linha, anuncio.confianca)
        if agora > faixa_ate:
            faixa = ""

        caixas_onibus = [(x1, y1, x2, y2) for c, _, x1, y1, x2, y2 in resultado.caixas if c == "onibus"]
        visivel = desenhar(anonimizar(frame, caixas_onibus), resultado, faixa)
        if args.saida:
            if escritor is None:
                Path(args.saida).parent.mkdir(parents=True, exist_ok=True)
                h, w = visivel.shape[:2]
                escritor = cv2.VideoWriter(args.saida, cv2.VideoWriter_fourcc(*"mp4v"), 15, (w, h))
            escritor.write(visivel)
        if args.mostrar:
            cv2.imshow("Ponto Falante - camera", visivel)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    if api:
        reenviados = api.reenviar_fila()
        if reenviados:
            log.info("Reenviadas %d detecções que estavam na fila", reenviados)
    if escritor:
        escritor.release()
    if args.mostrar:  # só fecha janela se abriu uma (OpenCV "headless" não tem janelas)
        cv2.destroyAllWindows()
    dur = time.time() - inicio
    log.info("Fim: %d frames em %.1f s (%.1f FPS)", n, dur, n / dur if dur else 0)


if __name__ == "__main__":
    main()

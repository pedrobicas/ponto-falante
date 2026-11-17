"""Teste ponta a ponta do demo.py: vídeo -> detector -> anunciador -> API.
Usa um detector falso (não precisa de YOLO/GPU) e a API falsa de verdade."""
import sys
import threading
import types

import cv2
import numpy as np
import pytest

import api_fake
from anunciador import ResultadoFrame
from leitor_letreiro import ler_linha


class DetectorFalso:
    """Simula o YOLO + OCR: 'vê' um ônibus da linha 8000-10 nos quadros claros."""
    def __init__(self, *a, **k):
        pass

    def detectar(self, frame, linhas):
        if frame.mean() < 50:   # quadro escuro = ponto vazio
            return ResultadoFrame(False)
        leitura = ler_linha([("8OOO-10 LAPA", 0.9)], linhas)
        return ResultadoFrame(True, 0.9, leitura, [("onibus", 0.9, 10, 10, 150, 110)])


@pytest.fixture()
def video(tmp_path):
    caminho = tmp_path / "entrada.mp4"
    w = cv2.VideoWriter(str(caminho), cv2.VideoWriter_fourcc(*"mp4v"), 10, (160, 120))
    for i in range(30):
        w.write(np.full((120, 160, 3), 0 if i < 5 or i > 20 else 200, np.uint8))
    w.release()
    return caminho


def test_demo_envia_anuncio_para_api(video, tmp_path, monkeypatch):
    srv = api_fake.criar_servidor(0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    api_fake.DETECCOES.clear()
    url = f"http://127.0.0.1:{srv.server_address[1]}"

    monkeypatch.setitem(sys.modules, "detector", types.SimpleNamespace(DetectorOnibus=DetectorFalso))
    monkeypatch.chdir(tmp_path)
    saida = tmp_path / "saida.mp4"
    monkeypatch.setattr(sys, "argv", ["demo.py", "--fonte", str(video), "--ponto", "P1",
                                      "--api", url, "--saida", str(saida)])
    import demo
    demo.main()
    srv.shutdown()

    assert len(api_fake.DETECCOES) == 1
    assert api_fake.DETECCOES[0]["linha_lida"] == "8000-10"
    assert api_fake.DETECCOES[0]["ponto"] == "P1"
    assert saida.exists() and saida.stat().st_size > 0
    assert "ANÚNCIO" in (tmp_path / "logs" / "visao.log").read_text(encoding="utf-8")

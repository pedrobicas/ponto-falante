"""Contrato do serviço HTTP (contratos/openapi-visao-letreiro.yaml) com um detector falso: roda na CI sem YOLO/GPU."""
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from anunciador import ResultadoFrame  # noqa: E402
from detector import ler_resultados_ocr  # noqa: E402
from servico import app as servico  # noqa: E402

CHAVE = "chave-de-teste-com-32-caracteres!"


class DetectorFalso:
    """Simula YOLO + OCR: o 'OCR' devolve o texto configurado; registra as linhas recebidas."""
    dispositivo = "cpu"

    def __init__(self, texto="875A-10 METRO", conf_ocr=0.9, com_letreiro=True, demora=0.0):
        self.texto, self.conf_ocr, self.com_letreiro, self.demora = texto, conf_ocr, com_letreiro, demora
        self.linhas_recebidas = "nao chamado"

    def detectar(self, frame, linhas):
        time.sleep(self.demora)
        self.linhas_recebidas = linhas
        caixas = [("onibus", 0.9, 10, 10, 300, 200)]
        if not self.com_letreiro:
            return ResultadoFrame(True, 0.9, None, caixas)
        caixas.append(("letreiro", 0.8, 40, 20, 240, 60))
        leitura = ler_resultados_ocr([(self.texto, self.conf_ocr)], linhas, limiar=1.0, rejeitar_ambiguas=True,
                                     ler_fora_da_lista=True)
        leitura.confianca = round(leitura.confianca * 0.8, 3)
        return ResultadoFrame(True, 0.9, leitura, caixas)


def jpeg(w=320, h=240):
    ok, buf = cv2.imencode(".jpg", np.full((h, w, 3), 128, np.uint8))
    return buf.tobytes()


@pytest.fixture()
def cliente_com():
    def criar(det):
        app = servico.criar_app(lambda: det, chave=CHAVE)
        c = TestClient(app)
        c.__enter__()
        for _ in range(100):  # o modelo carrega numa thread
            if c.get("/health").status_code == 200:
                break
            time.sleep(0.01)
        return c
    return criar


def enviar(c, dados=None, linhas=None, chave=CHAVE, nome="quadro.jpg"):
    form = {"linhas": linhas} if linhas is not None else {}
    return c.post("/v1/letreiro", headers={"X-API-Key": chave} if chave else {},
                  files={"imagem": (nome, dados if dados is not None else jpeg(), "image/jpeg")}, data=form)


def test_leitura_validada_segue_o_contrato(cliente_com):
    det = DetectorFalso("875A-10 METRO BARRA FUNDA")
    c = cliente_com(det)
    r = enviar(c, linhas="875a-10, 875C-10,lixo!!")
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["modelo"].startswith("pf-visao")
    assert isinstance(corpo["latencia_ms"], int)
    assert corpo["leituras"] == [{"texto": "875A-10", "confianca": 0.72, "validada": True, "caixa": [40, 20, 200, 40]}]
    assert corpo["deteccoes"] == {"onibus": 1, "letreiros": 1}
    assert det.linhas_recebidas == ["875A-10", "875C-10"]   # normalizadas, item inválido ignorado


def test_letreiro_so_com_numero_nao_ganha_sufixo(cliente_com):
    c = cliente_com(DetectorFalso("875A JD ANGELA"))
    assert enviar(c, linhas="875A-10,875A-21").json()["leituras"][0]["texto"] == "875A"


def test_linha_fora_da_lista_nao_vira_a_mais_parecida(cliente_com):
    # Achado do teste ponta a ponta: 647P-10 num ponto que só tem 478P-10 "casava" no limiar 0,75.
    corpo = enviar(cliente_com(DetectorFalso("647P-10 PQ EDU CHAVES")), linhas="478P-10,875A-10").json()
    assert corpo["leituras"][0]["texto"] == "647P-10"
    assert corpo["leituras"][0]["validada"] is False
    assert corpo["leituras"][0]["confianca"] < 0.72      # reduzida: não foi validada


def test_ocr_com_confusao_conhecida_continua_validando(cliente_com):
    # O/0, I/1, S/5, B/8, G/6: normalizados antes da comparação exata.
    corpo = enviar(cliente_com(DetectorFalso("G47P-10")), linhas="647P-10,478P-10").json()
    assert corpo["leituras"][0]["texto"] == "647P-10" and corpo["leituras"][0]["validada"] is True


def test_sem_leitura_confiavel_devolve_lista_vazia(cliente_com):
    c = cliente_com(DetectorFalso("TERM PINHEIROS"))
    corpo = enviar(c, linhas="875A-10").json()
    assert corpo["leituras"] == [] and corpo["deteccoes"]["letreiros"] == 1


def test_sem_letreiro_na_foto_informa_contagem(cliente_com):
    corpo = enviar(cliente_com(DetectorFalso(com_letreiro=False))).json()
    assert corpo["leituras"] == [] and corpo["deteccoes"] == {"onibus": 1, "letreiros": 0}


def test_sem_lista_de_linhas_usa_modo_sem_validacao(cliente_com):
    det = DetectorFalso("875A-10")
    corpo = enviar(cliente_com(det)).json()
    assert det.linhas_recebidas is None and corpo["linhas_validadas"] is False
    assert corpo["leituras"][0]["confianca"] < 0.6      # penalizada: o backend não afirma nada com ela


@pytest.mark.parametrize("chave", [None, "errada", CHAVE[:-1]])
def test_chave_obrigatoria(cliente_com, chave):
    assert enviar(cliente_com(DetectorFalso()), chave=chave).status_code == 401


def test_rejeita_arquivo_que_nao_e_imagem(cliente_com):
    r = enviar(cliente_com(DetectorFalso()), dados=b"GIF89a" + b"0" * 100, nome="x.jpg")
    assert r.status_code == 415


def test_rejeita_imagem_grande(cliente_com):
    r = enviar(cliente_com(DetectorFalso()), dados=b"\xff\xd8\xff" + b"0" * (2 * 1024 * 1024 + 10))
    assert r.status_code == 413


def test_ocupado_responde_503(cliente_com, monkeypatch):
    monkeypatch.setattr(servico, "ESPERA_MAX_S", 0.05)
    det = DetectorFalso(demora=0.5)
    c = cliente_com(det)
    import threading
    t = threading.Thread(target=enviar, args=(c,))
    t.start()
    time.sleep(0.1)
    assert enviar(c).status_code == 503
    t.join()


def test_health_e_identidade(cliente_com):
    c = cliente_com(DetectorFalso())
    assert c.get("/health").json()["status"] == "ok"
    desafio = "ab" * 32
    assert c.get("/identidade", params={"desafio": desafio}).json()["prova"] == servico.prova_identidade(CHAVE, desafio)
    assert c.get("/identidade", params={"desafio": "nao-hex"}).status_code == 400


def test_health_503_enquanto_carrega():
    def lento():
        time.sleep(1)
        return DetectorFalso()
    with TestClient(servico.criar_app(lento, chave=CHAVE)) as c:
        assert c.get("/health").status_code == 503
        assert enviar(c).status_code == 503


def test_sem_chave_configurada_nao_sobe():
    with pytest.raises(RuntimeError):
        with TestClient(servico.criar_app(DetectorFalso, chave="curta")):
            pass


def test_prova_identidade_igual_ao_backend():
    # Mesmo vetor de EnderecoVisaoControllerTest (Java): HMAC-SHA256(chave, "pf-visao-identidade:" + desafio).
    assert servico.prova_identidade("k" * 16, "00" * 8) == "15e824b3f92d100986132704c3b77fc10c24f1d93b940d7eb2384f5a1ae11c73"

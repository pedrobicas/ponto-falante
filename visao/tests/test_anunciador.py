from anunciador import Anunciador, ResultadoFrame
from leitor_letreiro import LeituraLinha


def frame(linha=None, conf=0.8, onibus=True):
    leitura = LeituraLinha(linha, conf, linha or "") if linha else None
    return ResultadoFrame(onibus, 0.9 if onibus else 0.0, leitura)


def rodar(anunciador, frames, t0=0.0, passo=0.1):
    anuncios = []
    for i, f in enumerate(frames):
        a = anunciador.processar(f, t0 + i * passo)
        if a:
            anuncios.append(a)
    return anuncios


def test_anuncia_linha_apos_votacao():
    a = Anunciador()
    anuncios = rodar(a, [frame("8000-10")] * 6)
    assert len(anuncios) == 1
    assert anuncios[0].linha == "8000-10"
    assert "8000-10" in anuncios[0].texto


def test_um_frame_isolado_nao_dispara():
    a = Anunciador()
    assert rodar(a, [frame("8000-10")] + [frame(onibus=False)] * 5) == []


def test_avisa_quando_nao_consegue_ler():
    a = Anunciador()
    anuncios = rodar(a, [frame()] * 10)
    assert len(anuncios) == 1
    assert anuncios[0].linha is None
    assert "Não consegui ler" in anuncios[0].texto


def test_leitura_fraca_nao_vira_anuncio_de_linha():
    a = Anunciador()
    anuncios = rodar(a, [frame("8000-10", conf=0.1)] * 10)
    assert all(x.linha is None for x in anuncios)


def test_nao_repete_mesma_linha_em_seguida():
    a = Anunciador(intervalo_repeticao_s=20)
    anuncios = rodar(a, [frame("8000-10")] * 30)  # 3 segundos com o mesmo ônibus
    assert len(anuncios) == 1


def test_dois_onibus_diferentes_geram_dois_anuncios():
    a = Anunciador()
    seq = [frame("8000-10")] * 6 + [frame(onibus=False)] * 8 + [frame("875A-10")] * 6
    assert [x.linha for x in rodar(a, seq)] == ["8000-10", "875A-10"]

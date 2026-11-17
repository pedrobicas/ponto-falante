import numpy as np

from privacidade import anonimizar, borrar_regiao


def test_borrar_regiao_altera_so_a_regiao():
    rng = np.random.default_rng(0)
    img = rng.integers(0, 255, (200, 200, 3), dtype=np.uint8)
    original = img.copy()
    borrar_regiao(img, 50, 50, 150, 150)
    assert not np.array_equal(img[50:150, 50:150], original[50:150, 50:150])
    assert np.array_equal(img[:40], original[:40])


def test_anonimizar_nao_altera_original():
    img = np.zeros((120, 160, 3), dtype=np.uint8)
    img[100:, 60:100] = 255
    saida = anonimizar(img, [(0, 0, 160, 120)])
    assert saida is not img
    assert img[110, 80, 0] == 255

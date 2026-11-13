"""Contratos da busca com vetores sintéticos, sem modelos e sem acessar o teste fechado."""
import json

import numpy as np
import pytest

from pf_genai import busca_v3 as busca
from pf_genai.trechos_v3 import TrechoV3, salvar


def trechos():
    return [TrechoV3(f"t{i}", doc, doc, "https://example.org", texto, [f"v1-{i}"])
            for i, (doc, texto) in enumerate([
                ("sptrans-gratuidade-65-mais", "Solicitação do cartão especial."),
                ("sptrans-gratuidade-60-64", "Ativação do benefício no cartão comum."),
                ("sptrans-bilhete-unico", "O cartão é pessoal e intransferível.")])]


def indice():
    return busca.IndiceV3(trechos(), np.array([[1., 0.], [.8, .6], [0., 1.]], dtype="float32"), "sintetico")


def test_filtro_antes_da_lista_de_candidatos_preserva_publico(monkeypatch):
    monkeypatch.setattr(busca, "embutir", lambda *a, **kw: np.array([[1., 0.]], dtype="float32"))
    vistos = []
    def rerank(q, textos):
        vistos.extend(textos)
        return [5.] * len(textos)
    monkeypatch.setattr(busca, "reordenar", rerank)
    achados = indice().buscar("benefício", k=1, n_cand=1, expansao=False, hibrida=False,
                              filtro=lambda t: t.documento_id == "sptrans-gratuidade-60-64")
    assert [a.trecho.trecho_id for a in achados] == ["t1"]
    assert len(vistos) == 1 and "60 a 64" in vistos[0]


def test_pergunta_e_expansao_embutidas_em_um_lote(monkeypatch):
    chamadas = []
    def embutir(textos, *a, **kw):
        chamadas.append(textos)
        return np.array([[1., 0.]] * len(textos), dtype="float32")
    monkeypatch.setattr(busca, "embutir", embutir)
    indice().buscar("Tenho 62 anos", rerank=False)
    assert len(chamadas) == 1 and len(chamadas[0]) == 2


def test_indice_detecta_texto_alterado_mesmo_com_id_igual(tmp_path):
    idx = indice()
    salvar(idx.trechos, tmp_path)
    idx.salvar(tmp_path)
    assert busca.IndiceV3.carregar(tmp_path).trechos[0].texto == idx.trechos[0].texto
    idx.trechos[0].texto = "Regra revisada."
    salvar(idx.trechos, tmp_path)
    with pytest.raises(ValueError, match="desatualizado"):
        busca.IndiceV3.carregar(tmp_path)


def test_indice_sem_assinatura_nao_e_aceito_como_verificado(tmp_path):
    idx = indice()
    salvar(idx.trechos, tmp_path)
    idx.salvar(tmp_path)
    path = tmp_path / "indice_v3_meta.json"
    meta = json.loads(path.read_text(encoding="utf-8"))
    del meta["conteudo_sha256"]
    path.write_text(json.dumps(meta), encoding="utf-8")
    with pytest.raises(ValueError, match="assinatura"):
        busca.IndiceV3.carregar(tmp_path)


def test_filtro_vazio_dispensa_modelos(monkeypatch):
    def proibido(*a, **kw):
        pytest.fail("Não deve carregar modelos sem documentos elegíveis")
    monkeypatch.setattr(busca, "embutir", proibido)
    assert indice().buscar("benefício", filtro=lambda _: False) == []

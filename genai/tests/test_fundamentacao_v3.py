"""Regressões de fundamentação. Fontes sintéticas; nenhum conjunto final é usado."""
from types import SimpleNamespace

import pytest

from pf_genai import agente_v3 as ag
from pf_genai.busca_v3 import Achado
from pf_genai.trechos_v3 import TrechoV3


def achado(texto, doc="sptrans-bilhete-unico", score=8.0):
    return Achado(TrechoV3(f"v3-{doc}-001", doc, "Documento de teste", "https://example.org", texto, ["v1-001"]), score, .9, score)


def executar(monkeypatch, texto, evidencia, *, pergunta="Posso emprestar o cartão?", resposta=None,
             doc="sptrans-bilhete-unico", usados=None, **extras):
    a = achado(texto, doc)
    g = {"resposta": resposta or "O cartão pode ser emprestado.", "nao_consta": False,
         "evidencia": evidencia, "trechos_usados": usados or [a.trecho.trecho_id], **extras}
    monkeypatch.setattr(ag.llm, "gerar_json", lambda *a, **kw: g)
    indice = SimpleNamespace(buscar=lambda *a, **kw: [a0])
    a0 = a
    return ag.responder(pergunta, indice).resposta


@pytest.mark.parametrize("evidencia", ["", "O cartão é de uso pessoal e transferível."])
def test_evidencia_ausente_ou_alterada_nao_autoriza_resposta(monkeypatch, evidencia):
    r = executar(monkeypatch, "O cartão é de uso pessoal e intransferível.", evidencia)
    assert r.nao_consta and r.fontes == []


def test_valor_sugerido_pelo_usuario_nao_e_fonte(monkeypatch):
    r = executar(monkeypatch, "A tarifa de ônibus é R$ 5,30.", "A tarifa de ônibus é R$ 5,30.",
                 pergunta="A passagem custa R$ 99,00?", resposta="Sim, a tarifa custa R$ 99,00.")
    assert r.nao_consta


def test_cabecalho_do_publico_nao_e_evidencia_numerica(monkeypatch):
    r = executar(monkeypatch, "A segunda via é gratuita.", "A segunda via é gratuita.",
                 pergunta="Quanto custa a segunda via do cartão da pessoa idosa?",
                 resposta="A segunda via custa R$ 65.", doc="sptrans-gratuidade-65-mais")
    assert r.nao_consta


def test_numero_em_outro_assunto_do_trecho_nao_comprova_prazo(monkeypatch):
    r = executar(monkeypatch, "A entrega leva 20 dias. A renovação pode ser solicitada 30 dias antes.",
                 "A entrega leva 20 dias.", pergunta="Qual o prazo de entrega?", resposta="A entrega leva 30 dias.")
    assert r.nao_consta


def test_idade_pessoal_pode_ser_repetida_sem_autorizar_outros_numeros(monkeypatch):
    r = executar(monkeypatch, "A gratuidade atende pessoas a partir de 65 anos.",
                 "A gratuidade atende pessoas a partir de 65 anos.", pergunta="Tenho 68 anos, tenho direito?",
                 resposta="Sim, aos 68 anos você atende ao requisito de 65 anos.")
    assert not r.nao_consta


def test_citacao_falsa_nao_e_silenciosamente_descartada(monkeypatch):
    r = executar(monkeypatch, "O cartão é pessoal.", "O cartão é pessoal.", resposta="O cartão é pessoal.",
                 usados=["v3-sptrans-bilhete-unico-001", "fonte-inventada"])
    assert r.nao_consta


def test_reavalia_limiar_depois_do_filtro_de_publico(monkeypatch):
    itens = [achado("A entrega leva 30 dias.", "sptrans-gratuidade-65-mais", 8),
             achado("O benefício é mensal.", "sptrans-gratuidade-60-64", -8)]
    def nao_gerar(*args, **kwargs):
        pytest.fail("Trecho do público correto abaixo do limiar não deve chegar ao LLM")
    monkeypatch.setattr(ag.llm, "gerar_json", nao_gerar)
    r = ag.responder("Tenho 62 anos, como obtenho o benefício?", SimpleNamespace(buscar=lambda *a, **kw: itens))
    assert r.resposta.nao_consta


def test_sem_publico_compativel_nao_reintroduz_documentos_excluidos(monkeypatch):
    def nao_gerar(*args, **kwargs):
        pytest.fail("Sem evidência compatível, não gerar com outro público")
    monkeypatch.setattr(ag.llm, "gerar_json", nao_gerar)
    r = ag.responder("Tenho 62 anos, como obtenho o benefício?", SimpleNamespace(
        buscar=lambda *a, **kw: [achado("A entrega leva 30 dias.", "sptrans-gratuidade-65-mais")]))
    assert r.resposta.nao_consta


def test_duas_fontes_precisam_de_evidencias_individuais(monkeypatch):
    a = achado("A entrega leva 20 dias.")
    b = achado("O cartão tem validade de 5 anos.", "sptrans-bilhete-pcd")
    g = {"resposta": "A entrega leva 20 dias e o cartão vale por 5 anos.", "nao_consta": False,
         "trechos_usados": [a.trecho.trecho_id, b.trecho.trecho_id],
         "evidencias": [{"trecho_id": a.trecho.trecho_id, "citacao": a.trecho.texto}]}
    monkeypatch.setattr(ag.llm, "gerar_json", lambda *a, **kw: g)
    indice = SimpleNamespace(buscar=lambda *args, **kw: [a, b])
    assert ag.responder("Qual o prazo de entrega e a validade?", indice).resposta.nao_consta
    g["evidencias"].append({"trecho_id": b.trecho.trecho_id, "citacao": b.trecho.texto})
    assert not ag.responder("Qual o prazo de entrega e a validade?", indice).resposta.nao_consta


def test_resposta_longa_nao_corta_condicao_no_meio(monkeypatch):
    texto = "A renovação está disponível " + "somente " * 60 + "quando o cadastro estiver atualizado."
    assert ag.para_voz(texto) == ""  # pede síntese/reparo ao gerador em vez de inventar final


@pytest.mark.parametrize("g", [[], None, {"resposta": 45, "nao_consta": False},
                                 {"resposta": "Sim.", "nao_consta": "false", "trechos_usados": "id"}])
def test_json_valido_com_formato_errado_falha_controladamente(monkeypatch, g):
    monkeypatch.setattr(ag.llm, "gerar_json", lambda *a, **kw: g)
    r = ag.responder("Posso usar o cartão?", SimpleNamespace(buscar=lambda *a, **kw: [achado("O cartão é pessoal.")]))
    assert r.resposta.nao_consta


def test_poda_remove_fonte_sem_evidencia_mas_audita_numeros(monkeypatch):
    a = achado("A entrega leva 20 dias.")
    b = achado("O cartão tem validade de 5 anos.", "sptrans-bilhete-pcd")
    g = {"resposta": "A entrega leva 20 dias.", "nao_consta": False,
         "trechos_usados": [a.trecho.trecho_id, b.trecho.trecho_id],
         "evidencias": [{"trecho_id": a.trecho.trecho_id, "citacao": a.trecho.texto}]}
    monkeypatch.setattr(ag.llm, "gerar_json", lambda *a, **kw: g)
    indice = SimpleNamespace(buscar=lambda *args, **kw: [a, b])
    cfg = ag.ConfigV3(podar_sem_evidencia=True)
    r = ag.responder("Qual o prazo de entrega?", indice, cfg).resposta
    assert not r.nao_consta and [f.trecho_id for f in r.fontes] == [a.trecho.trecho_id]
    # o número da fonte podada continua sem prova: recusa
    g["resposta"] = "A entrega leva 20 dias e o cartão vale por 5 anos."
    assert ag.responder("Qual o prazo de entrega e a validade?", indice, cfg).resposta.nao_consta


def test_padrao_recusa_fonte_usada_sem_evidencia_mesmo_sem_numero(monkeypatch):
    # Revisão adversarial de 13/11: a afirmação qualitativa da fonte sem citação não pode passar.
    a = achado("A primeira via do cartão é gratuita.")
    b = achado("A segunda via exige pagamento de tarifa.", "sptrans-bilhete-pcd")
    g = {"resposta": "A primeira e a segunda via são gratuitas.", "nao_consta": False,
         "trechos_usados": [a.trecho.trecho_id, b.trecho.trecho_id],
         "evidencias": [{"trecho_id": a.trecho.trecho_id, "citacao": a.trecho.texto}]}
    monkeypatch.setattr(ag.llm, "gerar_json", lambda *a, **kw: g)
    indice = SimpleNamespace(buscar=lambda *args, **kw: [a, b])
    assert ag.ConfigV3().podar_sem_evidencia is False
    assert ag.responder("A segunda via é gratuita?", indice, ag.ConfigV3()).resposta.nao_consta

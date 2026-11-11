"""Testes que não dependem do Ollama (rodam em segundos)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from pf_genai import avaliacao, trechos
from pf_genai.agente import numeros_sem_suporte
from pf_genai.esquemas import RESPOSTA_NAO_CONSTA, RespostaIA, recusa
from pf_genai.gerador import Resultado


def test_resposta_afirmativa_exige_fonte():
    with pytest.raises(ValidationError):
        RespostaIA(resposta="Sim, é grátis.", fontes=[], confianca="alta", nao_consta=False)


def test_recusa_nao_cita_fonte():
    r = RespostaIA(resposta="x", fontes=[{"documento": "d", "trecho_id": "t"}], confianca="baixa", nao_consta=True)
    assert r.fontes == []
    assert recusa().resposta == RESPOSTA_NAO_CONSTA


def test_confianca_so_aceita_tres_valores():
    with pytest.raises(ValidationError):
        RespostaIA(resposta="x", fontes=[], confianca="altissima", nao_consta=True)


def test_numeros_sem_suporte():
    trecho = "Art. 39. Aos maiores de 65 (sessenta e cinco) anos fica assegurada a gratuidade."
    assert numeros_sem_suporte("A partir de 65 anos é grátis.", [trecho], "") == []
    assert numeros_sem_suporte("A partir de 60 anos é grátis.", [trecho], "") == ["60"]
    assert numeros_sem_suporte("Com 62 anos você...", [trecho], "Tenho 62 anos") == []


def test_divisao_por_artigo():
    texto = "Art. 39. Primeiro artigo com texto suficiente para virar trecho.\nArt. 40. Segundo artigo também com texto."
    partes = trechos.dividir_lei(texto)
    assert len(partes) == 2 and partes[1].startswith("Art. 40")


def test_fatos_ok_ignora_acento_e_caixa():
    assert avaliacao.fatos_ok("A GRATUIDADE vale para 65 anos", [["gratuidade"], ["65 anos", "sessenta e cinco"]])
    assert not avaliacao.fatos_ok("Vale para 60 anos", [["65 anos"]])


def test_metricas_de_alucinacao():
    p_nc = {"id": "x", "nao_consta": True, "fatos": [], "trechos_esperados": []}
    resp = RespostaIA(resposta="Custa 10 reais.", fontes=[{"documento": "d", "trecho_id": "t"}],
                      confianca="alta", nao_consta=False)
    linha = avaliacao.avaliar_resposta(p_nc, Resultado("rag", resp))
    assert linha["alucinacao"] and not linha["acerto"]
    linha = avaliacao.avaliar_resposta(p_nc, Resultado("rag", recusa()))
    assert linha["acerto"] and not linha["alucinacao"]


def test_api_chat_contrato(monkeypatch):
    from api import app as modulo

    def falso(pergunta, indice):
        return Resultado("agente", RespostaIA(resposta="Sim.", fontes=[{"documento": "Lei", "trecho_id": "lei-1"}],
                                             confianca="alta", nao_consta=False))
    monkeypatch.setattr(modulo.agente, "responder", falso)
    monkeypatch.setattr(modulo, "indice", lambda: None)
    c = TestClient(modulo.app)
    r = c.post("/chat", json={"pergunta": "Idoso paga ônibus?"})
    assert r.status_code == 200
    corpo = r.json()
    assert set(corpo) >= {"resposta", "fontes", "confianca", "nao_consta"}
    assert corpo["fontes"][0] == {"documento": "Lei", "trecho_id": "lei-1"}
    assert c.post("/chat", json={"pergunta": ""}).status_code == 422


def test_api_degrada_quando_llm_cai(monkeypatch):
    from api import app as modulo

    def quebra(pergunta, indice):
        raise ConnectionError("ollama fora")
    monkeypatch.setattr(modulo.agente, "responder", quebra)
    monkeypatch.setattr(modulo, "indice", lambda: None)
    r = TestClient(modulo.app).post("/chat", json={"pergunta": "oi"})
    assert r.status_code == 503 and r.json()["nao_consta"] is True

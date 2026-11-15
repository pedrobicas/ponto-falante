"""Falhas adicionais pedidas na auditoria de 15/11/2026: timeout, resposta vazia, corpo inválido e reexecução.

Todos os cenários usam o mock local ou respostas fabricadas em memória; nada aqui é coleta real.
"""
from __future__ import annotations

import json

import pytest
import requests

from pf_rpa.cliente_mvp import ClienteMVP, MVPIndisponivel, RespostaInvalida
from pf_rpa.robo import SUCESSO, executar

DATA = "2026-11-12"


def _resposta(status: int, corpo: bytes) -> requests.Response:
    r = requests.Response()
    r.status_code = status
    r._content = corpo
    return r


def test_timeout_repetido_vira_indisponivel_com_backoff(monkeypatch):
    esperas: list[float] = []
    cliente = ClienteMVP("http://mvp.invalido", timeout=0.1, tentativas=3, backoff_inicial=2, dormir=esperas.append)

    def lento(*_a, **_k):
        raise requests.Timeout("tempo esgotado")

    monkeypatch.setattr(cliente.sessao, "get", lento)
    with pytest.raises(MVPIndisponivel, match="3 tentativas.*Timeout"):
        cliente.buscar_amostras(DATA)
    assert esperas == [2, 4]


def test_timeout_seguido_de_resposta_recupera_sem_erro(monkeypatch):
    chamadas = {"n": 0}
    cliente = ClienteMVP("http://mvp.invalido", timeout=0.1, tentativas=3, backoff_inicial=1, dormir=lambda _s: None)

    def instavel(*_a, **_k):
        chamadas["n"] += 1
        if chamadas["n"] == 1:
            raise requests.Timeout("primeira tentativa lenta")
        return _resposta(200, b"[]")

    monkeypatch.setattr(cliente.sessao, "get", instavel)
    assert cliente.buscar_amostras(DATA) == []
    assert chamadas["n"] == 2


@pytest.mark.parametrize("corpo", [b"", b"<html>erro</html>", b"{\"amostras\": 3}"])
def test_resposta_vazia_ou_invalida_nao_vira_dado(monkeypatch, corpo):
    cliente = ClienteMVP("http://mvp.invalido", tentativas=1, dormir=lambda _s: None)
    monkeypatch.setattr(cliente.sessao, "get", lambda *_a, **_k: _resposta(200, corpo))
    with pytest.raises(RespostaInvalida):
        cliente.buscar_amostras(DATA)


def test_503_seguido_de_200_recupera(monkeypatch):
    respostas = iter([_resposta(503, b"indisponivel"), _resposta(200, b"[]")])
    esperas: list[float] = []
    cliente = ClienteMVP("http://mvp.invalido", tentativas=3, backoff_inicial=2, dormir=esperas.append)
    monkeypatch.setattr(cliente.sessao, "get", lambda *_a, **_k: next(respostas))
    assert cliente.buscar_amostras(DATA) == []
    assert esperas == [2]


def test_reexecucao_no_mesmo_dia_e_idempotente(cfg, mock_url):
    """Rodar o robô duas vezes para a mesma data gera o mesmo boletim e não duplica nada no MVP."""
    primeira = executar(cfg, DATA)
    segunda = executar(cfg, DATA)
    assert primeira.codigo == segunda.codigo == SUCESSO
    assert primeira.boletim["linhas"] == segunda.boletim["linhas"]
    assert primeira.boletim["estatisticas"] == segunda.boletim["estatisticas"]
    publicado = requests.get(f"{mock_url}/boletim", timeout=5).json()
    assert publicado["data_referencia"] == DATA and publicado["linhas"] == segunda.boletim["linhas"]
    # Um arquivo por data: a segunda execução substitui o boletim local em vez de criar outro.
    assert len(list(cfg.pasta_saida.glob(f"boletim_{DATA}*.json"))) == 1
    auditoria = [json.loads(l) for l in (cfg.pasta_logs / "auditoria.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [a["status"] for a in auditoria[-2:]] == ["sucesso", "sucesso"]

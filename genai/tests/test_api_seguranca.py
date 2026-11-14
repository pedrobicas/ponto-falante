"""Contrato HTTP de seguranca, sem acesso ao Ollama ou aos embeddings."""
from __future__ import annotations

import logging
import threading
import time
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from api import app as modulo
from pf_genai.esquemas import RespostaIA
from pf_genai.gerador import Resultado

CHAVE = "chave-apenas-para-testes"
PERGUNTA = "Pergunta privada LGPD 793164, tenho direito ao passe?"


@pytest.fixture
def cliente(monkeypatch):
    monkeypatch.setenv("GENAI_API_KEY", CHAVE)
    monkeypatch.delenv("GENAI_AUTH_DESATIVADA", raising=False)
    monkeypatch.delenv("GENAI_TIMEOUT_S", raising=False)
    monkeypatch.setattr(modulo, "_requisicoes", {}, raising=False)
    monkeypatch.setattr(modulo, "_global", modulo.deque(), raising=False)
    monkeypatch.delenv("GENAI_LIMITE_GLOBAL_POR_MINUTO", raising=False)
    monkeypatch.setattr(modulo, "MODO", "agente")
    monkeypatch.setattr(modulo, "indice", lambda: None)
    monkeypatch.setattr(modulo.llm._cliente, "list", lambda: SimpleNamespace(models=[]))

    def responder(pergunta, indice):
        return Resultado("agente", RespostaIA(
            resposta="Sim.", fontes=[{"documento": "Lei", "trecho_id": "lei-1"}],
            confianca="alta", nao_consta=False))

    monkeypatch.setattr(modulo.agente, "responder", responder)
    # Sem lifespan: evita carregar embeddings reais na inicializacao.
    c = TestClient(modulo.app)
    yield c
    c.close()


def enviar(cliente, **kwargs):
    headers = {"X-API-Key": CHAVE, **kwargs.pop("headers", {})}
    return cliente.post("/chat", json={"pergunta": PERGUNTA}, headers=headers, **kwargs)


@pytest.mark.parametrize("chave_enviada", [None, CHAVE])
def test_sem_chave_configurada_falha_fechada(cliente, monkeypatch, chave_enviada):
    monkeypatch.delenv("GENAI_API_KEY")
    headers = {"X-API-Key": chave_enviada} if chave_enviada else {}
    r = cliente.post("/chat", json={"pergunta": PERGUNTA}, headers=headers)
    assert r.status_code == 503
    assert "GENAI_API_KEY" in r.json()["detail"]


@pytest.mark.parametrize("headers", [{}, {"X-API-Key": "errada"}])
def test_rejeita_chave_ausente_ou_errada(cliente, headers):
    r = cliente.post("/chat", json={"pergunta": PERGUNTA}, headers=headers)
    assert r.status_code == 401
    assert CHAVE not in r.text


def test_chave_certa_preserva_contrato(cliente):
    r = enviar(cliente)
    assert r.status_code == 200
    assert r.json() == {
        "resposta": "Sim.", "fontes": [{"documento": "Lei", "trecho_id": "lei-1"}],
        "confianca": "alta", "nao_consta": False, "modo": "rag_agente",
        "latencia_ms": r.json()["latencia_ms"],
    }
    assert r.json()["latencia_ms"] >= 0


def test_capacidade_ocupada_rejeita_sem_enfileirar(cliente, monkeypatch):
    vagas = threading.BoundedSemaphore(1)
    vagas.acquire()
    monkeypatch.setattr(modulo, "_vagas", vagas)
    r = enviar(cliente)
    assert r.status_code == 429
    assert r.headers["Retry-After"] == "5"
    vagas.release()
    assert enviar(cliente).status_code == 200


def test_auth_desativada_avisa_no_log(cliente, monkeypatch, caplog):
    monkeypatch.delenv("GENAI_API_KEY")
    monkeypatch.setenv("GENAI_AUTH_DESATIVADA", "1")
    with caplog.at_level(logging.WARNING, logger="pf_genai.api"):
        r = cliente.post("/chat", json={"pergunta": PERGUNTA})
    assert r.status_code == 200
    assert "GENAI_AUTH_DESATIVADA=1" in caplog.text
    assert PERGUNTA not in caplog.text


def test_auth_so_desativa_com_um(cliente, monkeypatch):
    monkeypatch.delenv("GENAI_API_KEY")
    monkeypatch.setenv("GENAI_AUTH_DESATIVADA", "true")
    assert enviar(cliente).status_code == 503


def test_limite_por_ip_cloudflare_e_expiracao(cliente, monkeypatch):
    agora = [1000.0]
    monkeypatch.setattr(modulo, "_agora", lambda: agora[0], raising=False)
    origem = {"CF-Connecting-IP": "203.0.113.10"}
    assert [enviar(cliente, headers=origem).status_code for _ in range(20)] == [200] * 20
    r = enviar(cliente, headers=origem)
    assert r.status_code == 429
    assert 1 <= int(r.headers["Retry-After"]) <= 60
    assert enviar(cliente, headers={"CF-Connecting-IP": "203.0.113.11"}).status_code == 200
    agora[0] += 60
    assert enviar(cliente, headers=origem).status_code == 200


def test_limite_sem_header_cloudflare(cliente):
    assert [enviar(cliente).status_code for _ in range(20)] == [200] * 20
    assert enviar(cliente).status_code == 429
    assert cliente.get("/health").status_code in (200, 503)


def test_rejeicao_auth_nao_gasta_cota(cliente):
    for _ in range(21):
        assert enviar(cliente, headers={"X-API-Key": "errada"}).status_code == 401
    assert enviar(cliente).status_code == 200


@pytest.mark.parametrize("etapa", ["geracao", "indice"])
def test_timeout_responde_antes_de_terminar_geracao(cliente, monkeypatch, caplog, etapa):
    liberar = threading.Event()
    terminou = threading.Event()

    def lento(*args):
        try:
            liberar.wait(3)
            raise RuntimeError(PERGUNTA)
        finally:
            terminou.set()

    monkeypatch.setenv("GENAI_TIMEOUT_S", "0.05")
    if etapa == "geracao":
        monkeypatch.setattr(modulo.agente, "responder", lento)
    else:
        monkeypatch.setattr(modulo, "indice", lento)
    try:
        with caplog.at_level(logging.INFO):
            inicio = time.perf_counter()
            r = enviar(cliente)
            decorrido = time.perf_counter() - inicio
        assert r.status_code == 504
        assert r.json() == {
            "resposta": "O assistente está indisponível agora. Tente de novo em instantes.",
            "fontes": [], "confianca": "baixa", "nao_consta": True, "modo": "indisponivel",
        }
        assert decorrido < 1
        assert not terminou.is_set()
    finally:
        liberar.set()
        assert terminou.wait(2)
    assert PERGUNTA not in caplog.text


@pytest.mark.parametrize("valor", ["invalido", "0", "-1", "nan", "inf"])
def test_timeout_invalido_falha_com_mensagem_clara(cliente, monkeypatch, valor):
    monkeypatch.setenv("GENAI_TIMEOUT_S", valor)
    r = enviar(cliente)
    assert r.status_code == 503
    assert "GENAI_TIMEOUT_S" in r.json()["detail"]


@pytest.mark.parametrize("falha", [False, True])
def test_log_nunca_contem_pergunta(cliente, monkeypatch, caplog, falha):
    if falha:
        def quebrar(pergunta, indice):
            raise RuntimeError(PERGUNTA)
        monkeypatch.setattr(modulo.agente, "responder", quebrar)
    with caplog.at_level(logging.INFO):
        r = enviar(cliente)
    assert r.status_code == (503 if falha else 200)
    assert "pf_genai.api" in {registro.name for registro in caplog.records}
    assert PERGUNTA not in caplog.text
    assert CHAVE not in caplog.text


@pytest.mark.parametrize("disponivel", [True, False])
def test_health_publico_sem_detalhes_internos(cliente, monkeypatch, disponivel):
    monkeypatch.delenv("GENAI_API_KEY")
    monkeypatch.setitem(modulo._estado, "indice", object() if disponivel else None)
    modelos = [SimpleNamespace(model=modulo.llm.MODELO)] if disponivel else []
    monkeypatch.setattr(modulo.llm._cliente, "list", lambda: SimpleNamespace(models=modelos))
    r = cliente.get("/health")
    assert r.status_code == (200 if disponivel else 503)
    assert r.json() == {
        "status": "ok" if disponivel else "degradado",
        "llm_ok": disponivel, "indice_ok": disponivel,
    }


def test_preserva_modo_rag(cliente, monkeypatch):
    monkeypatch.setattr(modulo, "MODO", "rag")
    monkeypatch.setattr(modulo.gerador, "rag", lambda pergunta, indice: Resultado("rag", None))
    r = enviar(cliente)
    assert r.status_code == 200
    assert r.json()["modo"] == "rag"
    assert r.json()["nao_consta"] is True


def test_timeout_nao_acumula_threads_ou_executa_fila_expirada(cliente, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor

    liberar = threading.Event()
    terminou = threading.Event()
    chamadas = []

    def lento(pergunta, indice):
        chamadas.append(pergunta)
        try:
            liberar.wait(3)
            return Resultado("agente", None)
        finally:
            terminou.set()

    with ThreadPoolExecutor(max_workers=1) as executor:
        monkeypatch.setattr(modulo, "_executor", executor, raising=False)
        monkeypatch.setattr(modulo.agente, "responder", lento)
        monkeypatch.setenv("GENAI_TIMEOUT_S", "0.05")
        try:
            assert [enviar(cliente).status_code for _ in range(3)] == [504] * 3
            assert chamadas == [PERGUNTA]
        finally:
            liberar.set()
            assert terminou.wait(2)
    assert chamadas == [PERGUNTA]


def test_cota_individual_por_cliente_do_spring(cliente):
    # Tres usuarios atras do mesmo Spring (mesmo IP do Tunnel) nao dividem a mesma cota.
    tunel = {"CF-Connecting-IP": "203.0.113.50"}
    for usuario in ("a1" * 8, "b2" * 8, "c3" * 8):
        h = {**tunel, "X-PF-Cliente": usuario}
        assert [enviar(cliente, headers=h).status_code for _ in range(15)] == [200] * 15
    assert enviar(cliente, headers={**tunel, "X-PF-Cliente": "a1" * 8}).status_code == 200


def test_cliente_invalido_cai_no_ip(cliente):
    h = {"CF-Connecting-IP": "203.0.113.60", "X-PF-Cliente": "nao-e-hex!"}
    assert [enviar(cliente, headers=h).status_code for _ in range(20)] == [200] * 20
    assert enviar(cliente, headers=h).status_code == 429


def test_limite_global_de_capacidade(cliente, monkeypatch):
    monkeypatch.setenv("GENAI_LIMITE_GLOBAL_POR_MINUTO", "5")
    for i in range(5):
        assert enviar(cliente, headers={"X-PF-Cliente": f"{i:016x}"}).status_code == 200
    r = enviar(cliente, headers={"X-PF-Cliente": "f" * 16})
    assert r.status_code == 429 and "Retry-After" in r.headers


def test_identidade_prova_a_chave_sem_revela_la(cliente):
    import hashlib
    import hmac as hm
    desafio = "ab" * 32
    r = cliente.get("/identidade", params={"desafio": desafio})
    assert r.status_code == 200
    esperada = hm.new(CHAVE.encode(), f"pf-genai-identidade:{desafio}".encode(), hashlib.sha256).hexdigest()
    assert r.json() == {"prova": esperada}
    assert CHAVE not in r.text


@pytest.mark.parametrize("desafio", ["", "curto", "ZZ" * 32, "a" * 200])
def test_identidade_recusa_desafio_invalido(cliente, desafio):
    assert cliente.get("/identidade", params={"desafio": desafio}).status_code == 400


def test_identidade_sem_chave_fica_indisponivel(cliente, monkeypatch):
    monkeypatch.delenv("GENAI_API_KEY")
    assert cliente.get("/identidade", params={"desafio": "ab" * 32}).status_code == 503

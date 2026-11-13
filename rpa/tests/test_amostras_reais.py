"""Dado REAL: coletor de amostras de previsão e boletim ESTIMADO (sucesso, decisão, falhas).

Rodar:  python -m pytest -v   (dentro da pasta rpa/)
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta

import requests

from pf_rpa import coletor
from pf_rpa.cliente_mvp import ClienteMVP
from pf_rpa.config import RegrasEstimadas
from pf_rpa.decisao import ATENCAO, CRITICA, OK, SEM_DADOS
from pf_rpa.estimativa import FUSO, avaliar_linhas_estimadas, classificar_estimada, validar_amostras
from pf_rpa.robo import MVP_INDISPONIVEL, SUCESSO, executar
from tools import mock_mvp

DATA = "2026-11-12"


def _previsao(fonte: str, onibus: list[tuple[str, int]], quando: str = "2026-11-12T10:00:00.123456-03:00") -> dict:
    """Resposta no formato de GET /api/pontos/{codigo}/previsoes do Spring."""
    return {
        "ponto": {"codigo": 1, "nome": "PONTO TESTE", "fonte": fonte},
        "fonte": fonte, "tipo": "PREVISAO", "horario_referencia": "10:00", "consultado_em": quando,
        "onibus": [{"letreiro": l, "destino": "CENTRO", "sentido": 1, "previsto_em": f"10:{m:02d}" if m < 60 else "11:00",
                    "minutos": m, "acessivel": True, "veiculo": f"v{l}{m}"} for l, m in onibus],
        "frase_falada": "x",
    }


def _amostra(ponto: str, hora: int, onibus: list[tuple[str, int]], fonte: str = "olhovivo") -> dict:
    """Amostra no formato de GET /api/rpa/amostras."""
    return {"ponto": ponto, "consultado_em": f"{DATA}T{hora:02d}:00:00-03:00", "horario_referencia": f"{hora:02d}:00",
            "fonte": fonte, "tipo_registro": "AMOSTRA_PREVISAO", "total_onibus": len(onibus),
            "onibus": [{"linha": l, "sentido": 1, "previsto_em": f"{hora:02d}:{m:02d}" if m < 60 else f"{hora + 1:02d}:00",
                        "minutos": m, "acessivel": i % 2 == 0, "veiculo": f"{l}-{hora}-{m}"}
                       for i, (l, m) in enumerate(onibus)]}


def _dia_real() -> list[dict]:
    """8 consultas em 2 pontos. A: espera 35 min (CRÍTICA). B: 22 min (ATENÇÃO). C: 8 min (OK).
    F: sem previsão em 5 de 8 consultas (ATENÇÃO). D: vista uma vez só (fica fora: poucas amostras)."""
    amostras = []
    for i, hora in enumerate(range(7, 22, 2)):
        p1 = [("A", 5), ("A", 40), ("B", 3), ("B", 25)] + ([("D", 7)] if i == 0 else [])
        p2 = [("C", 2), ("C", 10), ("C", 18)] + ([("F", 4), ("F", 12)] if i < 3 else [])
        amostras += [_amostra("P1", hora, p1), _amostra("P2", hora, p2)]
    return amostras


# ---------- Boletim ESTIMADO: sucesso ponta a ponta + decisão ----------
def test_boletim_estimado_com_amostras_reais(cfg, mock_url):
    cfg.coleta.pontos = ["P1", "P2"]
    mock_mvp.estado.update({"modo": "REAL", "amostras": _dia_real()})
    res = executar(cfg, DATA)
    assert res.codigo == SUCESSO and res.publicado
    b = res.boletim
    assert b["natureza_dados"] == "ESTIMADO" and b["dados_simulados"] is False
    assert b["fonte_dados"] == {"olhovivo": 16, "simulador": 0}
    assert b["periodo_referencia"]["inicio"] == "07:00" and b["periodo_referencia"]["fim"] == "21:00"
    assert b["ultima_atualizacao"].startswith(f"{DATA}T21:00")
    assert b["amostragem"]["classificacao"] == "VERIFICADO" and b["amostragem"]["cobertura_pct"] == 100.0
    status = {l["linha"]: l["status"] for l in b["linhas"]}
    assert status == {"A": CRITICA, "B": ATENCAO, "F": ATENCAO, "C": OK}
    assert b["estatisticas"]["linhas_poucas_amostras"] == 1          # linha D
    for l in b["linhas"]:
        assert l["classificacao"] == "ESTIMADO" and l["atraso_medio_min"] is None and l["fontes"] == ["olhovivo"]
    a = next(l for l in b["linhas"] if l["linha"] == "A")
    assert a["espera_tipica_min"] == 35 and a["sem_previsao_pct"] == 0
    f = next(l for l in b["linhas"] if l["linha"] == "F")
    assert f["sem_previsao_pct"] == 62.5 and "nenhum ônibus" in f["frase"]
    assert "não atrasos medidos" in b["resumo_falado"] and "atraso forte" not in b["resumo_falado"]
    assert requests.get(f"{mock_url}/boletim", timeout=5).json()["natureza_dados"] == "ESTIMADO"
    auditoria = json.loads((cfg.pasta_logs / "auditoria.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    assert auditoria["tipo"] == "boletim" and auditoria["natureza_dados"] == "ESTIMADO"


def test_amostragem_parcial_gera_aviso(cfg):
    mock_mvp.estado.update({"modo": "REAL", "amostras": _dia_real()[:6]})   # 6 de 48 esperadas (6 pontos x 8)
    cfg.coleta.pontos = cfg.coleta.pontos + ["P1", "P2"]
    b = executar(cfg, DATA).boletim
    assert b["natureza_dados"] == "ESTIMADO"
    assert any("Amostragem parcial" in a for a in b["avisos"]) and "parcial" in b["resumo_falado"]


def test_regra_estimada_limites():
    r = RegrasEstimadas()
    assert classificar_estimada(30.5, 31, 0, r)[0] == CRITICA
    assert classificar_estimada(30, 30, 0, r)[0] == ATENCAO        # no limite exato não é crítica
    assert classificar_estimada(20, 31, 0, r)[0] == ATENCAO        # um pico acima do crítico
    assert classificar_estimada(10, 15, 50, r)[0] == ATENCAO       # metade das consultas sem previsão
    assert classificar_estimada(20, 30, 49.9, r)[0] == OK


def test_linha_configurada_sem_amostras_fica_sem_dados():
    val = validar_amostras([_amostra("P1", 8, [("A", 5)])], DATA, RegrasEstimadas(), [])
    sit, poucas = avaliar_linhas_estimadas(val.validas, ["A", "Z"], RegrasEstimadas())
    assert {s.linha: s.status for s in sit} == {"A": SEM_DADOS, "Z": SEM_DADOS} and poucas == 0


def test_validacao_das_amostras_motivos():
    regs = [
        _amostra("P1", 8, [("A", 5), ("A", 999), ("", 3)]),          # 2 ônibus descartados
        _amostra("P1", 8, [("A", 5)]),                                # duplicada (mesmo ponto e minuto)
        _amostra("P1", 9, [("A", 5)], fonte="simulador"),             # simulação nunca entra como real
        dict(_amostra("P1", 10, []), consultado_em="ontem"),
        dict(_amostra("P1", 11, []), consultado_em="2026-11-11T11:00:00-03:00"),   # outro dia
        dict(_amostra("P9", 12, [])),                                 # ponto fora do escopo
        "lixo",
    ]
    val = validar_amostras(regs, DATA, RegrasEstimadas(), ["P1"])
    assert len(val.validas) == 1 and len(val.validas[0].onibus) == 1 and val.onibus_descartados == 2
    assert val.duplicadas == 1 and val.fora_periodo == 1 and val.fora_escopo == 1
    assert val.contagem_motivos() == {"consultado_em_invalido": 1, "fonte_simulada": 1, "formato_invalido": 1}


# ---------- Sem dado real: INDISPONÍVEL ou SIMULADO (nunca misturado) ----------
def test_sem_amostras_com_mvp_real_publica_indisponivel_sem_simular(cfg):
    mock_mvp.estado["modo"] = "REAL"
    b = executar(cfg, DATA).boletim
    assert b["natureza_dados"] == "INDISPONIVEL" and b["dados_simulados"] is False
    assert b["fonte_dados"] == {"olhovivo": 0, "simulador": 0} and "indisponível" in b["resumo_falado"]


def test_sem_amostras_com_mvp_demo_usa_simulado_rotulado(cfg):
    b = executar(cfg, DATA).boletim
    assert b["natureza_dados"] == "SIMULADO" and b["dados_simulados"] is True
    assert all(l["classificacao"] in ("SIMULADO", "INDISPONIVEL") for l in b["linhas"])
    assert any("SIMULADOS" in a for a in b["avisos"]) and "simulados" in b["resumo_falado"]


def test_fallback_nunca_nao_simula_nem_em_demo(cfg):
    cfg.fallback_simulado = "nunca"
    assert executar(cfg, DATA).boletim["natureza_dados"] == "INDISPONIVEL"


def test_backend_antigo_sem_rota_de_amostras_continua_funcionando(cfg):
    mock_mvp.estado["sem_amostras_api"] = True
    b = executar(cfg, DATA).boletim
    assert b["natureza_dados"] == "SIMULADO"
    assert any("amostras reais" in a for a in b["avisos"])


def test_mvp_fora_ao_ler_amostras_republica_desatualizado(cfg, mock_url):
    mock_mvp.estado.update({"modo": "REAL", "amostras": _dia_real()})
    cfg.coleta.pontos = ["P1", "P2"]
    assert executar(cfg, DATA).codigo == SUCESSO
    requests.post(f"{mock_url}/admin/falha", params={"ativo": "true"}, timeout=5)
    res = executar(cfg, "2026-11-13")
    assert res.codigo == MVP_INDISPONIVEL and res.boletim["desatualizado"] is True
    assert res.boletim["natureza_dados"] == "ESTIMADO" and res.boletim["data_referencia"] == DATA


# ---------- Coletor ----------
def _agora():
    return datetime(2026, 11, 12, 10, 0, tzinfo=FUSO)


def test_coletor_sucesso_parcial_envia_e_audita(cfg):
    cfg.coleta.pontos = ["P1", "P2", "P3", "P4"]
    mock_mvp.estado.update({
        "modo": "REAL",
        "previsoes": {"P1": _previsao("OLHO_VIVO", [("A", 5), ("A", 40), ("A", 999)]),
                      "P2": _previsao("OLHO_VIVO", [("C", 2)])},
        "falha_previsoes": {"P3"},                      # gateway 5xx persistente
    })                                                  # P4: 404 (sem previsão)
    res = coletor.coletar(cfg, agora=_agora())
    assert res.codigo == coletor.SUCESSO and res.status == "parcial"
    assert res.falhas == {"P3": "mvp_ou_sptrans_indisponivel", "P4": "sem_previsao_no_ponto"}
    assert res.envio["gravadas"] == 2
    gravadas = mock_mvp.estado["amostras"]
    assert {a["ponto"] for a in gravadas} == {"P1", "P2"} and all(a["fonte"] == "olhovivo" for a in gravadas)
    assert len(next(a for a in gravadas if a["ponto"] == "P1")["onibus"]) == 2     # minutos=999 descartado
    assert gravadas[0]["consultado_em"] == "2026-11-12T10:00:00-03:00"             # sem microssegundos
    aud = json.loads((cfg.pasta_logs / "auditoria.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    assert aud["tipo"] == "coleta" and aud["status"] == "parcial" and aud["onibus_descartados"] == 1
    assert aud["falhas_por_motivo"] == {"mvp_ou_sptrans_indisponivel": 1, "sem_previsao_no_ponto": 1}
    # coletar de novo no mesmo instante não duplica (idempotente)
    assert coletor.coletar(cfg, agora=_agora()).envio["duplicadas"] == 2


def test_coletor_nunca_grava_simulacao_como_real(cfg):
    cfg.coleta.pontos = ["P1"]
    mock_mvp.estado["previsoes"] = {"P1": _previsao("SIMULADO", [("A", 5)])}
    res = coletor.coletar(cfg, agora=_agora())
    assert res.codigo == coletor.SO_SIMULADO and mock_mvp.estado["amostras"] == []


def test_coletor_chave_recusada_guarda_pendente_e_reenvia_depois(cfg, monkeypatch):
    cfg.coleta.pontos = ["P1"]
    mock_mvp.estado["previsoes"] = {"P1": _previsao("OLHO_VIVO", [("A", 5)])}
    monkeypatch.setenv("MOCK_API_KEY", "chave-certa")
    cfg.api_key = "chave-errada"
    res = coletor.coletar(cfg, agora=_agora())
    assert res.codigo == coletor.ENVIO_FALHOU and res.status == "chave_recusada"
    assert len(list(cfg.coleta.pasta_pendentes.glob("amostras_*.json"))) == 1 and mock_mvp.estado["amostras"] == []
    # Próxima execução com a chave certa: o lote pendente é reenviado sem intervenção humana
    cfg.api_key = "chave-certa"
    mock_mvp.estado["previsoes"] = {"P1": _previsao("OLHO_VIVO", [("A", 7)], "2026-11-12T12:00:00-03:00")}
    res2 = coletor.coletar(cfg, agora=_agora() + timedelta(hours=2))
    assert res2.codigo == coletor.SUCESSO and res2.pendentes_reenviados == 1
    assert list(cfg.coleta.pasta_pendentes.glob("amostras_*.json")) == []
    assert len(mock_mvp.estado["amostras"]) == 2


def test_coletor_mvp_fora_do_ar(cfg):
    cfg.coleta.pontos = ["P1", "P2"]
    cliente = ClienteMVP("http://127.0.0.1:9", timeout=0.3, tentativas=2, backoff_inicial=0)
    res = coletor.coletar(cfg, cliente=cliente, agora=_agora())
    assert res.codigo == coletor.SEM_AMOSTRAS and set(res.falhas.values()) == {"mvp_ou_sptrans_indisponivel"}


def test_coletor_somente_leitura_nao_envia(cfg):
    cfg.coleta.pontos = ["P1"]
    mock_mvp.estado["previsoes"] = {"P1": _previsao("OLHO_VIVO", [("A", 5)])}
    res = coletor.coletar(cfg, somente_leitura=True, agora=_agora())
    assert res.codigo == coletor.SUCESSO and res.status == "sucesso_somente_leitura"
    assert mock_mvp.estado["amostras"] == []
    assert len(list((cfg.pasta_saida / "amostras").glob("amostras_*.json"))) == 1


def test_coletor_resposta_fora_do_contrato_e_descartada():
    amostra, motivo, _ = coletor.normalizar_resposta("P1", dict(_previsao("OLHO_VIVO", []), tipo="CHEGADA"), 120)
    assert amostra is None and motivo == "tipo_inesperado"
    amostra, motivo, _ = coletor.normalizar_resposta("P1", dict(_previsao("OLHO_VIVO", []), consultado_em="10:00"), 120)
    assert amostra is None and motivo == "consultado_em_invalido"

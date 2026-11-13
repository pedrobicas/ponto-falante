"""Regressões: falha explícita, proveniência e cobertura temporal."""
import json
from datetime import datetime

import pytest
import requests

from pf_rpa import coletor
from pf_rpa.cliente_mvp import ClienteMVP, RespostaInvalida
from pf_rpa.config import RegrasEstimadas
from pf_rpa.estimativa import FUSO, avaliar_linhas_estimadas, validar_amostras
from pf_rpa.robo import executar
from test_amostras_reais import DATA, _amostra, _previsao
from tools import mock_mvp


def test_rejeicao_do_backend_nao_e_sucesso(cfg, monkeypatch):
    cfg.coleta.pontos = ["P1"]
    mock_mvp.estado["previsoes"] = {"P1": _previsao("OLHO_VIVO", [("A", 5)])}
    cliente = ClienteMVP(cfg.mvp_url)
    monkeypatch.setattr(cliente, "enviar_amostras", lambda *args: {
        "recebidas": 1, "gravadas": 0, "duplicadas": 0,
        "rejeitadas": [{"indice": 0, "motivo": "fora_da_janela"}]})
    res = coletor.coletar(cfg, cliente=cliente)
    assert res.codigo != coletor.SUCESSO
    assert res.status == "amostras_rejeitadas"
    assert res.erros


@pytest.mark.parametrize("resposta", [
    {"gravadas": 1},
    {"recebidas": 1, "gravadas": True, "duplicadas": 0, "rejeitadas": []},
    {"recebidas": 1, "gravadas": 0, "duplicadas": 0, "rejeitadas": []},
    {"recebidas": 1, "gravadas": 0, "duplicadas": 0, "rejeitadas": [{"indice": 9, "motivo": "erro"}]},
])
def test_confirmacao_incompleta_nao_pode_apagar_pendente(resposta, monkeypatch):
    cliente = ClienteMVP("http://127.0.0.1:9")
    resp = requests.Response()
    resp.status_code = 200
    resp._content = json.dumps(resposta).encode()
    monkeypatch.setattr(cliente.sessao, "post", lambda *args, **kwargs: resp)
    with pytest.raises(RespostaInvalida):
        cliente.enviar_amostras([{}], "teste")


def test_cobertura_nao_troca_repeticoes_por_periodos_ausentes(cfg):
    cfg.coleta.pontos = ["P1", "P2"]
    # 16 consultas no mesmo ponto/hora não cobrem 8 horários em 2 pontos.
    regs = [dict(_amostra("P1", 7, [("A", 5)]), consultado_em=f"{DATA}T07:{i:02d}:00-03:00")
            for i in range(16)]
    mock_mvp.estado.update({"modo": "REAL", "amostras": regs})
    b = executar(cfg, DATA).boletim
    assert b["amostragem"]["cobertura_pct"] == 6.2
    assert any("parcial" in aviso.lower() for aviso in b["avisos"])


def test_previsoes_de_sentidos_opostos_nao_reduzem_espera():
    regs = []
    for hora in (7, 9, 11):
        a = _amostra("P1", hora, [("A", 5), ("A", 20), ("A", 40)])
        a["onibus"][1]["sentido"] = 2
        regs.append(a)
    val = validar_amostras(regs, DATA, RegrasEstimadas(), [])
    sit, _ = avaliar_linhas_estimadas(val.validas, ["A"], RegrasEstimadas())
    assert sit[0].espera_tipica_min == 35


def test_registro_de_chegada_nao_vira_amostra_de_previsao():
    reg = dict(_amostra("P1", 7, []), tipo_registro="CHEGADA")
    val = validar_amostras([reg], DATA, RegrasEstimadas(), [])
    assert not val.validas
    assert val.contagem_motivos() == {"tipo_inesperado": 1}


def test_agendador_usa_sao_paulo_em_host_com_outro_fuso(cfg, monkeypatch):
    import schedule
    from pf_rpa import agendador

    monkeypatch.setattr("sys.argv", ["agendador"])
    monkeypatch.setattr(agendador, "carregar", lambda _: cfg)
    monkeypatch.setattr(agendador.time, "sleep", lambda _: (_ for _ in ()).throw(KeyboardInterrupt()))
    schedule.clear()
    try:
        with pytest.raises(KeyboardInterrupt):
            agendador.main()
        assert len(schedule.jobs) == 9
        assert {str(job.at_time_zone) for job in schedule.jobs} == {"America/Sao_Paulo"}
    finally:
        schedule.clear()


def test_lote_pendente_com_formato_errado_vai_para_quarentena(cfg):
    cfg.coleta.pontos = ["P1"]
    cfg.coleta.pasta_pendentes.mkdir(parents=True)
    caminho = cfg.coleta.pasta_pendentes / "amostras_invalido.json"
    caminho.write_text('{"amostras": null}', encoding="utf-8")
    res = coletor.coletar(cfg)
    assert res.codigo == coletor.SEM_AMOSTRAS
    assert not caminho.exists()
    assert caminho.with_suffix(".invalido").exists()


def test_rejeicao_pendente_e_preservada_para_auditoria(cfg, monkeypatch):
    cfg.coleta.pontos = ["P1"]
    mock_mvp.estado["previsoes"] = {"P1": _previsao("OLHO_VIVO", [("A", 5)])}
    cfg.coleta.pasta_pendentes.mkdir(parents=True)
    caminho = cfg.coleta.pasta_pendentes / "amostras_antigo.json"
    caminho.write_text(json.dumps({"execucao_id": "antigo", "amostras": [{}]}), encoding="utf-8")
    cliente = ClienteMVP(cfg.mvp_url)
    def enviar(amostras, execucao):
        if execucao == "antigo":
            return {"recebidas": 1, "gravadas": 0, "duplicadas": 0,
                    "rejeitadas": [{"indice": 0, "motivo": "fora_da_janela"}]}
        return {"recebidas": 1, "gravadas": 1, "duplicadas": 0, "rejeitadas": []}
    monkeypatch.setattr(cliente, "enviar_amostras", enviar)
    res = coletor.coletar(cfg, cliente=cliente)
    assert res.codigo != 0
    assert caminho.with_suffix(".rejeitado").exists()
    assert not caminho.exists()


def test_dados_invalidos_nao_viram_ausencia_de_onibus():
    previsao = _previsao("OLHO_VIVO", [("A", 999)])
    amostra, motivo, descartados = coletor.normalizar_resposta("P1", previsao, 240)
    assert amostra is None and motivo == "onibus_invalidos" and descartados == 1
    val = validar_amostras([_amostra("P1", 7, [("A", 999)])], DATA, RegrasEstimadas(), [])
    assert not val.validas and val.contagem_motivos() == {"onibus_invalidos": 1}


def test_acessibilidade_ausente_nao_e_contada_como_nao_acessivel():
    regs = [_amostra("P1", h, [("A", 5), ("A", 10)]) for h in (7, 9, 11)]
    for reg in regs:
        reg["onibus"][1].pop("acessivel")
    val = validar_amostras(regs, DATA, RegrasEstimadas(), [])
    sit, _ = avaliar_linhas_estimadas(val.validas, ["A"], RegrasEstimadas())
    assert sit[0].acessiveis_pct == 100.0
    for reg in regs:
        reg["onibus"][0].pop("acessivel")
    val = validar_amostras(regs, DATA, RegrasEstimadas(), [])
    sit, _ = avaliar_linhas_estimadas(val.validas, ["A"], RegrasEstimadas())
    assert sit[0].acessiveis_pct is None


@pytest.mark.parametrize("metodo", ["amostras", "boletim"])
def test_post_autenticado_nao_segue_redirecionamento(monkeypatch, metodo):
    cliente = ClienteMVP("https://mvp.example/api", api_key="segredo-teste")
    resp = requests.Response()
    resp.status_code = 302
    def post(*args, **kwargs):
        assert kwargs["allow_redirects"] is False
        return resp
    monkeypatch.setattr(cliente.sessao, "post", post)
    with pytest.raises(RespostaInvalida):
        if metodo == "amostras":
            cliente.enviar_amostras([{}], "teste")
        else:
            cliente.publicar_boletim({})

"""Os 3 cenários exigidos (sucesso, decisão, falha) + exceções extras.

Rodar:  python -m pytest -v   (dentro da pasta rpa/)
"""
from __future__ import annotations

import json
import shutil

import requests

from pf_rpa.cliente_mvp import ClienteMVP
from pf_rpa.config import Regras
from pf_rpa.decisao import ATENCAO, CRITICA, OK, SEM_DADOS, avaliar_linhas, classificar
from pf_rpa.gtfs import carregar_rede
from pf_rpa.robo import ERRO_CONFIG, MVP_INDISPONIVEL, PUBLICACAO_FALHOU, SUCESSO, executar
from pf_rpa.validacao import Passagem, validar

DATA = "2026-11-12"


# ---------- Cenário 1: SUCESSO ponta a ponta ----------
def test_sucesso_ponta_a_ponta(cfg, mock_url):
    res = executar(cfg, DATA)
    assert res.codigo == SUCESSO and res.publicado
    b = res.boletim
    # Integração com o MVP: o boletim publicado é o que GET /boletim devolve
    publicado = requests.get(f"{mock_url}/boletim", timeout=5).json()
    assert publicado["data_referencia"] == DATA
    assert publicado["linhas"] == b["linhas"]
    # Origem dos dados declarada
    assert b["fonte_dados"]["simulador"] > 0 and b["dados_simulados"] is True
    # Validação e deduplicação funcionaram sobre os inválidos/duplicados injetados
    est = b["estatisticas"]
    assert est["invalidos"] > 0 and est["duplicados"] > 0
    assert est["validos"] + est["invalidos"] + est["duplicados"] + est["fora_escopo"] == est["recebidos"]
    assert set(b["invalidos_por_motivo"]) <= {"linha_inexistente", "campo_vazio", "horario_incoerente"}
    # Evidências locais e auditoria
    assert (cfg.pasta_saida / f"boletim_{DATA}.json").exists()
    assert (cfg.pasta_saida / f"boletim_{DATA}.html").exists()
    auditoria = (cfg.pasta_logs / "auditoria.jsonl").read_text(encoding="utf-8").splitlines()
    assert json.loads(auditoria[-1])["status"] == "sucesso"


# ---------- Cenário 2: DECISÃO (CRÍTICA x ATENÇÃO x OK) ----------
def test_decisao_com_dados_do_mock(cfg):
    res = executar(cfg, DATA)
    status = {l["linha"]: l["status"] for l in res.boletim["linhas"]}
    assert status["1001-10"] == CRITICA     # perfil com ~14 min de atraso médio
    assert status["1002-10"] == ATENCAO     # perfil com ~7 min
    assert status["1004-10"] == OK
    # A primeira linha do boletim é a mais grave (ordenação para leitura em voz)
    assert res.boletim["linhas"][0]["status"] == CRITICA
    assert "atraso forte" in res.boletim["resumo_falado"]


def test_regra_de_decisao_limites():
    r = Regras()
    assert classificar(10.1, 10, r)[0] == CRITICA           # atraso acima do crítico
    assert classificar(2, 31, r)[0] == CRITICA              # intervalo acima do crítico
    assert classificar(10, 30, r)[0] == ATENCAO             # no limite exato ainda não é crítica
    assert classificar(5.5, 0, r)[0] == ATENCAO
    assert classificar(5, 20, r)[0] == OK


def _p(linha, prog, prev, ponto="P1"):
    return Passagem(ponto, linha, "Centro", None, prog, prev, 0, True, "simulador")


def test_sem_dados_nao_decide_no_escuro():
    r = Regras()
    ps = [_p("A", "07:00", "07:30")]                         # 1 passagem só, muito atrasada
    sit = avaliar_linhas(ps, ["A", "B"], r)
    assert {s.linha: s.status for s in sit} == {"A": SEM_DADOS, "B": SEM_DADOS}


def test_intervalo_ignora_buraco_programado_mas_pega_onibus_que_sumiu():
    r = Regras()
    # Pico da manhã e da tarde: o buraco de 8h está na tabela, não é falha
    ps = [_p("A", "08:00", "08:00"), _p("A", "08:15", "08:15"), _p("A", "17:00", "17:00")]
    assert avaliar_linhas(ps, ["A"], r)[0].status == OK
    # Ônibus das 08:15 não passou: espera real de 30+ min entre programados de 15 em 15
    ps = [_p("A", "08:00", "08:00"), _p("A", "08:30", "08:35"), _p("A", "08:45", "08:45")]
    s = avaliar_linhas(ps, ["A"], r)[0]
    assert s.intervalo_max_min == 35 and s.status == CRITICA


# ---------- Cenário 3: FALHA (MVP fora do ar) ----------
def test_falha_mvp_fora_mantem_boletim_anterior_desatualizado(cfg, mock_url):
    assert executar(cfg, "2026-11-11").codigo == SUCESSO        # existe um boletim anterior
    requests.post(f"{mock_url}/admin/falha", params={"ativo": "true"}, timeout=5)
    res = executar(cfg, DATA)
    assert res.codigo == MVP_INDISPONIVEL
    b = res.boletim
    assert b["desatualizado"] is True
    assert b["data_referencia"] == "2026-11-11"                  # é o anterior, não inventa dados novos
    assert "desatualizado" in b["resumo_falado"]
    # O MVP continua no ar para escrita: o boletim desatualizado foi publicado e aparece no GET
    assert requests.get(f"{mock_url}/boletim", timeout=5).json()["desatualizado"] is True
    log = next(cfg.pasta_logs.glob("rpa_*.log"), None)
    auditoria = (cfg.pasta_logs / "auditoria.jsonl").read_text(encoding="utf-8").splitlines()
    assert json.loads(auditoria[-1])["status"] == "mvp_indisponivel"


def test_falha_total_sem_boletim_anterior(cfg):
    cliente = ClienteMVP("http://127.0.0.1:9", timeout=0.5, tentativas=3, backoff_inicial=0)
    res = executar(cfg, DATA, cliente=cliente)
    assert res.codigo == MVP_INDISPONIVEL and not res.publicado
    assert res.boletim["linhas"] == [] and res.boletim["desatualizado"] is True
    assert (cfg.pasta_saida / "boletim_ultimo.json").exists()    # nada se perde


def test_retry_com_backoff_exponencial():
    esperas = []
    cliente = ClienteMVP("http://127.0.0.1:9", timeout=0.3, tentativas=4, backoff_inicial=2,
                         dormir=esperas.append)
    try:
        cliente.buscar_historico(DATA)
    except Exception as e:
        assert "4 tentativas" in str(e)
    assert esperas == [2, 4, 8]


def test_publicacao_recusada_salva_local(cfg, monkeypatch):
    monkeypatch.setenv("MOCK_API_KEY", "chave-de-teste")          # mock exige chave; robô não tem
    res = executar(cfg, DATA)
    assert res.codigo == PUBLICACAO_FALHOU and not res.publicado
    assert (cfg.pasta_saida / f"boletim_{DATA}.json").exists()


def test_publicacao_com_chave_correta(cfg, monkeypatch):
    monkeypatch.setenv("MOCK_API_KEY", "chave-de-teste")
    cfg.api_key = "chave-de-teste"
    assert executar(cfg, DATA).codigo == SUCESSO


def test_chave_nunca_aparece_no_log(cfg, monkeypatch):
    from pf_rpa import registro
    monkeypatch.setenv("RPA_API_KEY", "segredo-xyz")
    arquivo = registro.configurar(cfg.pasta_logs, DATA)
    import logging
    logging.getLogger("pf_rpa.teste").error("token=%s", "segredo-xyz")  # nosemgrep -- valor falso: o teste prova que o log mascara segredos
    assert "segredo-xyz" not in arquivo.read_text(encoding="utf-8")


# ---------- Exceções de entrada (GTFS) ----------
def test_gtfs_ausente_usa_rede_ficticia_e_avisa(cfg):
    assert not cfg.gtfs_pasta.exists()
    rede = carregar_rede(cfg.gtfs_pasta, cfg.gtfs_pasta_ficticia)
    assert rede.origem == "rede_ficticia" and "fictícia" in rede.aviso
    res = executar(cfg, DATA)
    assert any("fictícia" in a for a in res.boletim["avisos"])


def test_gtfs_invalido_e_sem_fallback_para(cfg):
    (cfg.gtfs_pasta).mkdir(parents=True)
    (cfg.gtfs_pasta / "routes.txt").write_text("coluna_errada\nx\n", encoding="utf-8")
    shutil.rmtree(cfg.gtfs_pasta_ficticia)
    res = executar(cfg, DATA)
    assert res.codigo == ERRO_CONFIG and res.status == "erro_gtfs"


def test_validacao_motivos():
    rede = type("R", (), {"linhas": {"L1"}, "pontos": set()})()
    regs = [
        {"ponto": "P", "linha": "L1", "programado_em": "07:00", "previsto_em": "07:05", "fonte": "simulador", "veiculo": "v"},
        {"ponto": "P", "linha": "L1", "programado_em": "07:00", "previsto_em": "07:05", "fonte": "simulador", "veiculo": "v"},
        {"ponto": "P", "linha": "XX", "programado_em": "07:00", "previsto_em": "07:05", "fonte": "simulador"},
        {"ponto": "", "linha": "L1", "programado_em": "07:00", "previsto_em": "07:05", "fonte": "simulador"},
        {"ponto": "P", "linha": "L1", "programado_em": "07:00", "previsto_em": "05:00", "fonte": "simulador"},
        {"ponto": "P", "linha": "L1", "programado_em": "7h", "previsto_em": "07:05", "fonte": "simulador"},
        {"ponto": "P", "linha": "L1", "programado_em": "23:55", "previsto_em": "00:04", "fonte": "olhovivo"},
        "lixo",
    ]
    res = validar(regs, rede, Regras(), [], [])
    assert res.duplicados == 1
    assert res.contagem_motivos() == {"campo_vazio": 1, "formato_invalido": 1, "horario_incoerente": 1,
                                      "horario_mal_formatado": 1, "linha_inexistente": 1}
    virada = [p for p in res.validos if p.fonte == "olhovivo"][0]
    assert virada.atraso_min == 9                                 # 23:55 -> 00:04 cruza a meia-noite

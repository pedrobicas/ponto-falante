"""Testes isolados de retomada do benchmark, sem Ollama, embeddings ou internet."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

MODULO = Path(__file__).resolve().parents[1] / "scripts" / "continuidade_v3.py"
espec = importlib.util.spec_from_file_location("continuidade_v3_isolada", MODULO)
assert espec and espec.loader
c = importlib.util.module_from_spec(espec)
espec.loader.exec_module(c)


def perguntas(n=5):
    return [{"id": f"p{i}", "pergunta": f"Questão {i}?"} for i in range(n)]


def registro(p, config="v3_7b", rubric="v3.1"):
    return {"id": p["id"], "configuracao": config, "rubrica_versao": rubric, "categoria": "correto"}


def salvar(path, linhas):
    path.write_text("".join(json.dumps(row) + "\n" for row in linhas), encoding="utf-8")


def test_retomada_processa_apenas_pendentes_sem_duplicar(tmp_path):
    ps = perguntas()
    path = tmp_path / "saida.jsonl"
    salvar(path, [registro(p) for p in ps[:3]])
    chamadas = []

    def responder(q):
        chamadas.append(q)
        return registro(ps[len(chamadas) + 2])

    linhas = c.executar_com_checkpoint(ps, responder, path, "v3_7b", "v3.1", False)
    assert len(linhas) == 5
    assert chamadas == ["Questão 3?", "Questão 4?"]
    assert c.ler_checkpoint(path, ps, "v3_7b", "v3.1") == linhas
    assert len(path.read_text().splitlines()) == 5
    c.executar_com_checkpoint(ps, lambda _: pytest.fail("Nada a repetir"), path,
                             "v3_7b", "v3.1", False)


def test_interrupcao_preserva_linha_concluida(tmp_path):
    ps = perguntas()
    path = tmp_path / "saida.jsonl"
    contagem = [0]

    def responder(q):
        contagem[0] += 1
        if contagem[0] == 3:
            raise OSError("interrompido")
        return registro(ps[contagem[0] - 1])

    with pytest.raises(OSError):
        c.executar_com_checkpoint(ps, responder, path, "v3_7b", "v3.1", False)
    assert len(c.ler_checkpoint(path, ps, "v3_7b", "v3.1")) == 2
    prox = [2]

    def completar(_):
        linha = registro(ps[prox[0]])
        prox[0] += 1
        return linha

    c.executar_com_checkpoint(ps, completar, path, "v3_7b", "v3.1", False)
    assert len(c.ler_checkpoint(path, ps, "v3_7b", "v3.1")) == 5


@pytest.mark.parametrize("alteracao", [
    lambda r: r.update(id="outro"),
    lambda r: r.update(configuracao="rag_v1"),
    lambda r: r.update(rubrica_versao="v3.0"),
])
def test_rejeita_id_configuracao_ou_rubrica_diferentes(tmp_path, alteracao):
    ps = perguntas()
    r = registro(ps[0])
    alteracao(r)
    path = tmp_path / "saida.jsonl"
    salvar(path, [r])
    before = path.read_bytes()
    with pytest.raises(c.InconsistenciaRodada):
        c.executar_com_checkpoint(ps, lambda _: None, path, "v3_7b", "v3.1", False)
    assert path.read_bytes() == before


def test_rejeita_linha_corrompida_sem_apagar(tmp_path):
    ps = perguntas()
    path = tmp_path / "saida.jsonl"
    path.write_text(json.dumps(registro(ps[0])) + '\n{"id":', encoding="utf-8")
    before = path.read_bytes()
    with pytest.raises(c.InconsistenciaRodada, match="incompleta"):
        c.ler_checkpoint(path, ps, "v3_7b", "v3.1")
    assert path.read_bytes() == before


def test_rejeita_checkpoint_maior_que_conjunto(tmp_path):
    ps = perguntas(2)
    path = tmp_path / "saida.jsonl"
    salvar(path, [registro(p) for p in perguntas(3)])
    with pytest.raises(c.InconsistenciaRodada):
        c.ler_checkpoint(path, ps, "v3_7b", "v3.1")


def test_manifesto_incompativel_bloqueia_retomada():
    esperado = {k: "ok" for k in ("conjunto", "sha256", "configs", "modelo_base",
                                     "opcoes_llm", "rubrica", "v3", "codigo_sha256")}
    anterior = dict(esperado, estado="em_execucao")
    c.conferir_manifesto(anterior, esperado)
    for k in esperado:
        alterado = dict(esperado, **{k: "diferente"})
        with pytest.raises(c.InconsistenciaRodada, match=k):
            c.conferir_manifesto(anterior, alterado)
    with pytest.raises(c.InconsistenciaRodada):
        c.conferir_manifesto(dict(anterior, estado="concluido"), esperado)


def test_trava_impede_processos_simultaneos(tmp_path):
    with c.trava_execucao(tmp_path):
        with pytest.raises(c.InconsistenciaRodada):
            with c.trava_execucao(tmp_path):
                pass
    assert not (tmp_path / ".execucao.lock").exists()


def test_placar_atomico_grava_sem_perder_colunas(tmp_path):
    path = tmp_path / "placar.csv"
    c.escrever_placar_atomico(path, [{"configuracao": "v3_7b", "acerto_total": "90.0% (9/10)"}])
    texto = path.read_text(encoding="utf-8")
    assert "v3_7b" in texto and "acerto_total" in texto
    assert not path.with_suffix(".csv.tmp").exists()

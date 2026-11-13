"""Smoke tests das ferramentas offline, sem necessidade de modelos locais."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PASTA = Path(__file__).resolve().parents[1]


def _copia_da_rodada(tmp_path, hashes_atuais: bool) -> Path:
    import hashlib
    import shutil
    origem = PASTA / "avaliacao" / "v3" / "retomada_dev_20261112"
    destino = tmp_path / "rodada"
    shutil.copytree(origem, destino)
    mf = json.loads((destino / "manifesto.json").read_text(encoding="utf-8"))
    if hashes_atuais:  # simula uma rodada iniciada com o código atual
        mf["codigo_sha256"] = {p: hashlib.sha256((PASTA / "src" / "pf_genai" / p).read_bytes()).hexdigest()
                               for p in mf["codigo_sha256"]}
    else:
        mf["codigo_sha256"]["agente_v3.py"] = "0" * 64
    (destino / "manifesto.json").write_text(json.dumps(mf), encoding="utf-8")
    return destino


def _verificar(pasta: Path):
    return subprocess.run([sys.executable, str(PASTA / "scripts" / "verificar_retomada_v3.py"), "--pasta", str(pasta)],
                          cwd=PASTA, text=True, capture_output=True)


def test_verificacao_de_checkpoint_dos_dados_incluidos(tmp_path):
    r = _verificar(_copia_da_rodada(tmp_path, hashes_atuais=True))
    assert r.returncode == 0, r.stderr
    saida = json.loads(r.stdout)
    assert saida["hashes"] == "conferidos"
    assert saida["configuracoes"]["v3_7b"]["respondidas"] >= 53
    assert saida["configuracoes"]["v3_7b"]["total"] == 108


def test_checkpoint_com_codigo_diferente_nao_e_retomado(tmp_path):
    r = _verificar(_copia_da_rodada(tmp_path, hashes_atuais=False))
    assert r.returncode != 0 and "agente_v3.py" in r.stderr


def test_comparacao_pareada_preserva_criterios(tmp_path):
    antigo = PASTA / "avaliacao" / "v3" / "resultados_dev_v3_v3_7b.jsonl"
    novo = PASTA / "avaliacao" / "v3" / "retomada_dev_20261112" / "resultados_dev_v3_v3_7b.jsonl"
    destino = tmp_path / "comparacao.json"
    subprocess.run([sys.executable, str(PASTA / "scripts" / "comparar_dev_v3.py"),
                    "--antigo", str(antigo), "--novo", str(novo), "--saida", str(destino)],
                   cwd=PASTA, text=True, capture_output=True, check=True)
    r = json.loads(destino.read_text(encoding="utf-8"))
    resumo = r["resumo"]
    assert resumo["rubrica"] == "v3.1"
    assert 53 <= resumo["amostra_pareada"] <= 108
    assert len(r["por_pergunta"]) == resumo["amostra_pareada"]

"""Smoke tests das ferramentas offline, sem necessidade de modelos locais."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PASTA = Path(__file__).resolve().parents[1]


def test_verificacao_de_checkpoint_dos_dados_incluidos():
    r = subprocess.run([sys.executable, str(PASTA / "scripts" / "verificar_retomada_v3.py")],
                       cwd=PASTA, text=True, capture_output=True, check=True)
    saida = json.loads(r.stdout)
    assert saida["hashes"] == "conferidos"
    assert saida["configuracoes"]["v3_7b"]["respondidas"] >= 53
    assert saida["configuracoes"]["v3_7b"]["total"] == 108


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

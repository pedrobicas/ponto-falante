"""Verifica offline se uma execução DEV v3 pode ser retomada, sem Ollama nem teste final."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from continuidade_v3 import InconsistenciaRodada, ler_checkpoint

GENAI = Path(__file__).resolve().parents[1]


def verificar(pasta: Path) -> dict:
    mf = pasta / "manifesto.json"
    if not mf.is_file():
        raise InconsistenciaRodada(f"Manifesto não encontrado: {mf}")
    m = json.loads(mf.read_text(encoding="utf-8"))
    if m.get("conjunto") != "dev_v3":
        raise InconsistenciaRodada("Este verificador é exclusivo do DEV; não abre teste final.")
    base = GENAI / "avaliacao" / "v3" / "perguntas_dev_v3.jsonl"
    if hashlib.sha256(base.read_bytes()).hexdigest() != m["sha256"]:
        raise InconsistenciaRodada("Arquivo de perguntas mudou desde o início da rodada.")
    perguntas = [json.loads(l) for l in base.read_text(encoding="utf-8").splitlines() if l.strip()]
    diffs = [p for p, hash_ in m["codigo_sha256"].items()
             if not (GENAI / "src" / "pf_genai" / p).is_file()
             or hashlib.sha256((GENAI / "src" / "pf_genai" / p).read_bytes()).hexdigest() != hash_]
    if diffs:
        raise InconsistenciaRodada("Arquivos originais alterados: " + ", ".join(diffs) +
                                   ". Não misture versões: preserve a rodada e inicie outra.")
    estados = {}
    for nome in m["configs"]:
        caminho = pasta / f"resultados_dev_v3_{nome}.jsonl"
        dados = ler_checkpoint(caminho, perguntas, nome, m["rubrica"])
        estados[nome] = {"respondidas": len(dados), "total": len(perguntas),
                         "pendentes": len(perguntas) - len(dados)}
    return {"manifesto": str(mf), "estado": m["estado"], "hashes": "conferidos",
            "rubrica": m["rubrica"], "configuracoes": estados,
            "pode_retomar": m["estado"] == "em_execucao"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pasta", type=Path,
                    default=GENAI / "avaliacao" / "v3" / "retomada_dev_20261112")
    args = ap.parse_args()
    print(json.dumps(verificar(args.pasta), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

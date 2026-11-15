"""Prepara os roteiros de terminal dos vídeos (comandos reais) numa pasta de trabalho fora do repositório.

    python scripts/video/preparar.py <pasta de trabalho> [--execucao-boletim ID_DO_RUN]

O robô roda numa cópia de rpa/ para a demonstração de falha não alterar os logs versionados. Nenhum segredo entra
no roteiro: a coleta é só leitura e a demonstração de falha usa uma chave fictícia contra um endereço fora do ar.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
PY = str(RAIZ / ".venv" / "Scripts" / "python.exe")
AQUI = Path(__file__).resolve().parent


def main() -> None:
    trabalho = Path(sys.argv[1]).resolve()
    trabalho.mkdir(parents=True, exist_ok=True)
    execucao = sys.argv[sys.argv.index("--execucao-boletim") + 1] if "--execucao-boletim" in sys.argv else subprocess.run(
        ["gh", "run", "list", "--workflow", "rpa-diario.yml", "--limit", "1", "--json", "databaseId", "-q", ".[0].databaseId"],
        cwd=RAIZ, capture_output=True, text=True, check=True).stdout.strip()
    demo = trabalho / "rpa_demo"
    shutil.rmtree(demo, ignore_errors=True)
    demo.mkdir()
    for nome in ("src", "config", "data", "tests", "tools"):
        shutil.copytree(RAIZ / "rpa" / nome, demo / nome, ignore=shutil.ignore_patterns("__pycache__"))
    for nome in ("requirements.txt", "pyproject.toml"):
        if (RAIZ / "rpa" / nome).exists():
            shutil.copy(RAIZ / "rpa" / nome, demo / nome)
    src = {"PYTHONPATH": "src"}
    rpa = {"prompt": "rpa>", "comandos": [
        {"mostrar": "type config\\monitoramento.yaml   # regras de decisão",
         "argv": [PY, str(AQUI / "mostrar.py"), "regras", str(demo / "config" / "monitoramento.yaml")], "pausa_depois": 6},
        {"mostrar": "python -m pf_rpa.coletor --somente-leitura   # consulta real à SPTrans pelo MVP publicado",
         "argv": [PY, "-m", "pf_rpa.coletor", "--somente-leitura"], "cwd": str(demo),
         "env": {**src, "MVP_URL": "https://ponto-falante.onrender.com/api"}, "pausa_depois": 5},
        {"mostrar": f"gh run view {execucao} --log   # boletim publicado em produção pelo GitHub Actions",
         "argv": ["gh", "run", "view", execucao, "--log"], "cwd": str(RAIZ), "filtro": r"pf_rpa\.(robo|mvp) \|",
         "a_partir_de": r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} \| ", "max_linhas": 22, "pausa_depois": 8},
        {"mostrar": "set MVP_URL=http://127.0.0.1:59999 & python -m pf_rpa.robo   # MVP fora do ar",
         "argv": [PY, "-m", "pf_rpa.robo"], "cwd": str(demo), "mostrar_codigo": True,
         "env": {**src, "MVP_URL": "http://127.0.0.1:59999", "RPA_API_KEY": "chave-ficticia-de-demonstracao"}, "pausa_depois": 6},
        {"mostrar": "type logs\\auditoria.jsonl   # trilha de auditoria da execução com falha",
         "argv": [PY, str(AQUI / "mostrar.py"), "auditoria", str(demo / "logs" / "auditoria.jsonl")], "pausa_depois": 6},
        {"mostrar": "python -m pytest -q   # cenários de sucesso, decisão e falha",
         "argv": [PY, "-m", "pytest", "-q", "-p", "no:cacheprovider"], "cwd": str(demo), "pausa_depois": 5},
    ]}
    genai = {"prompt": "genai>", "comandos": [
        {"mostrar": "ollama list   # modelo local, sem serviço pago",
         "argv": ["ollama", "list"], "pausa_depois": 4},
        {"mostrar": "type avaliacao\\v3\\teste_final_20261113\\placar_teste_v3.csv   # teste inédito, rodado uma única vez",
         "argv": [PY, str(AQUI / "mostrar.py"), "placar",
                  str(RAIZ / "genai" / "avaliacao" / "v3" / "teste_final_20261113" / "placar_teste_v3.csv")], "pausa_depois": 9},
        {"mostrar": "type avaliacao\\v3\\dev_agente_20261114\\*\\placar_dev_v3.csv   # reparo de recusa, medido só no DEV",
         "argv": [PY, str(AQUI / "mostrar.py"), "placar",
                  str(RAIZ / "genai" / "avaliacao" / "v3" / "dev_agente_20261114" / "sem_reparo" / "placar_dev_v3.csv"),
                  str(RAIZ / "genai" / "avaliacao" / "v3" / "dev_agente_20261114" / "com_reparo" / "placar_dev_v3.csv")],
         "pausa_depois": 8},
        {"mostrar": "python -m pytest -q tests   # fundamentação, citações, recusa e segurança da API",
         "argv": [PY, "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests"], "cwd": str(RAIZ / "genai"), "pausa_depois": 5},
    ]}
    (trabalho / "roteiro_rpa.json").write_text(json.dumps(rpa, ensure_ascii=False, indent=1), encoding="utf-8")
    (trabalho / "roteiro_genai.json").write_text(json.dumps(genai, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"roteiros em {trabalho} (boletim de produção: execução {execucao})")


if __name__ == "__main__":
    main()

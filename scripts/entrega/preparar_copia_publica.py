"""Prepara, só no disco local, a cópia sanitizada que pode virar o repositório público da entrega.

Uso na raiz:  .venv/Scripts/python.exe scripts/entrega/preparar_copia_publica.py D:/ponto-falante-publico

* Copia apenas os arquivos versionados no commit atual (git archive HEAD): nada de .venv, modelos, caches,
  entregaveis/, .validation/, .env ou o PDF oficial da FIAP, que já são ignorados pelo Git.
* Procura padrões de segredo e arquivos grandes; se achar algo, para sem criar o repositório.
* Cria um repositório Git novo com um único commit, sem o histórico privado.
* NÃO cria repositório no GitHub, NÃO faz push e NÃO muda a visibilidade do repositório atual.
  Os comandos de publicação são impressos no fim, para o dono rodar quando decidir.
"""
from __future__ import annotations

import io
import re
import subprocess
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LIMITE_BYTES = 5 * 1024 * 1024
SEGREDOS = [
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "chave privada"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}"), "token do GitHub"),
    (re.compile(r"\bsk-[A-Za-z0-9]{20,}"), "chave de API"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "chave AWS"),
    (re.compile(r"\brnd_[A-Za-z0-9]{20,}"), "chave do Render"),
    (re.compile(r"(?i)\b(SPTRANS_GATEWAY_SEGREDO|SPTRANS_GATEWAY_CHAVE|PF_SPTRANS_TOKEN|GENAI_API_KEY|RPA_API_KEY|"
                r"SPRING_DATASOURCE_PASSWORD)[ \t]*[=:][ \t]*['\"]?(?!pontofalante\b|segredo-local\b)[A-Za-z0-9_\-]{12,}"), "variável sensível com valor"),
]
PROIBIDOS = re.compile(r"(^|/)(\.env|.*\.pem|.*\.key|.*\.gguf|.*\.safetensors|.*\.onnx)$")


def git(*args: str, cwd: Path = ROOT) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, check=True)  # nosemgrep -- argumentos fixos em lista, sem shell


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    destino = Path(sys.argv[1]).resolve()
    if destino == ROOT or ROOT in destino.parents:
        sys.exit("O destino precisa ficar fora do repositório privado.")
    if destino.exists() and any(destino.iterdir()):
        sys.exit(f"{destino} já existe e não está vazio.")
    if git("status", "--porcelain", "--untracked-files=no").stdout.strip():
        print("Aviso: há alterações não commitadas; a cópia usa só o commit atual (HEAD).")
    commit = git("rev-parse", "--short", "HEAD").stdout.decode().strip()

    problemas: list[str] = []
    arquivos = 0
    pacote = tarfile.open(fileobj=io.BytesIO(git("archive", "--format=tar", "HEAD").stdout))
    destino.mkdir(parents=True, exist_ok=True)
    for membro in pacote.getmembers():
        if not membro.isfile():
            continue
        nome = membro.name
        if nome.startswith("/") or ".." in Path(nome).parts:
            sys.exit(f"Caminho inesperado no pacote: {nome}")
        dados = pacote.extractfile(membro).read()
        if PROIBIDOS.search(nome):
            problemas.append(f"{nome}: tipo de arquivo que não pode ser publicado")
        if len(dados) > LIMITE_BYTES:
            problemas.append(f"{nome}: {len(dados) // 1024} KB (acima de {LIMITE_BYTES // 1024 // 1024} MB)")
        texto = dados.decode("utf-8", errors="ignore")
        for padrao, tipo in SEGREDOS:
            if padrao.search(texto):
                problemas.append(f"{nome}: possível {tipo}")
        alvo = destino / nome
        alvo.parent.mkdir(parents=True, exist_ok=True)
        alvo.write_bytes(dados)
        arquivos += 1

    if problemas:
        print("Cópia interrompida antes de criar o repositório. Revise:")
        print("\n".join(f"  - {p}" for p in problemas))
        sys.exit(1)

    git("init", "-q", "-b", "main", cwd=destino)
    git("add", "-A", cwd=destino)
    git("commit", "-q", "-m", "Ponto Falante - entrega FIAP Global Solution 2026.2", cwd=destino)
    print(f"Cópia pronta em {destino}: {arquivos} arquivos do commit {commit}, histórico novo com 1 commit.")
    print("Nenhum segredo, arquivo proibido ou arquivo grande encontrado pelas verificações locais.")
    print("\nPara publicar (decisão do dono do repositório; não executado por este script):")
    print(f'  cd "{destino}"')
    print("  gh repo create ponto-falante-entrega --public --source . --push")
    print("O repositório privado atual continua privado.")


if __name__ == "__main__":
    main()

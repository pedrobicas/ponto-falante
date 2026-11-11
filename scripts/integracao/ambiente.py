"""Leitura de .env sem eval, interpolacao ou alteracao do ambiente do processo."""
import os
import re
from pathlib import Path


def carregar(caminho: Path) -> dict[str, str]:
    valores = {}
    if caminho.exists():
        for numero, linha in enumerate(caminho.read_text(encoding="utf-8-sig").splitlines(), 1):
            linha = linha.strip()
            if not linha or linha.startswith("#"):
                continue
            chave, separador, valor = linha.removeprefix("export ").partition("=")
            chave, valor = chave.strip(), valor.strip()
            if not separador or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", chave):
                raise ValueError(f"Arquivo .env invalido na linha {numero}; revise a sintaxe CHAVE=valor.")
            if valor.startswith(('"', "'")):
                if len(valor) < 2 or valor[-1] != valor[0]:
                    raise ValueError(f"Aspas invalidas no .env, linha {numero}.")
                valor = valor[1:-1]
            else:
                valor = valor.split(" #", 1)[0].rstrip()
            valores[chave] = valor
    return {**valores, **os.environ}

"""Leitura de .env sem eval, interpolacao ou alteracao do ambiente do processo."""
import os
import re
from pathlib import Path


def normalizar_sptrans_token(valor: str) -> str:
    token = valor.strip()
    if any(c.isspace() for c in token):
        raise ValueError("SPTRANS_TOKEN contem espacos internos ou quebras de linha; revise o arquivo local.")
    if any(ord(c) < 32 or ord(c) == 127 or c == "\ufeff" for c in token):
        raise ValueError("SPTRANS_TOKEN contem caracteres de controle ou BOM; revise o arquivo local.")
    return token


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

"""Checkpoint seguro para a avaliação v3 (somente biblioteca padrão).

Preserva a ordem e as evidências já gravadas; não relê o teste final fechado.
Não altera o processo de inferência nem a rubrica de avaliação.
"""
from __future__ import annotations

import csv
import json
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Callable


class InconsistenciaRodada(ValueError):
    """A continuação misturaria experiências, versões ou perguntas diferentes."""


def conferir_manifesto(anterior: dict, esperado: dict) -> None:
    """Exige o mesmo conjunto, modelo, rubrica, configs e código de inferência/avaliação."""
    chaves = ("conjunto", "sha256", "configs", "modelo_base", "opcoes_llm",
              "rubrica", "v3", "codigo_sha256")
    divergencias = [chave for chave in chaves if anterior.get(chave) != esperado.get(chave)]
    if divergencias:
        raise InconsistenciaRodada(
            "Retomada recusada: manifesto diferente em " + ", ".join(divergencias) +
            ". Preserve a rodada anterior e faça uma nova execução completa."
        )
    if anterior.get("estado") != "em_execucao":
        raise InconsistenciaRodada("Rodada não está em execução; não repetir avaliação concluída.")


def ler_checkpoint(caminho: Path, perguntas: list[dict], configuracao: str, rubrica: str) -> list[dict]:
    if not caminho.exists():
        return []
    dados: list[dict] = []
    with caminho.open(encoding="utf-8") as arquivo:
        for numero, linha in enumerate(arquivo, 1):
            try:
                registro = json.loads(linha)
            except json.JSONDecodeError as e:
                raise InconsistenciaRodada(
                    f"Linha {numero} de {caminho.name} incompleta/inválida. "
                    "Faça backup e investigue antes de retomar; nenhum resultado será apagado."
                ) from e
            if not isinstance(registro, dict) or numero > len(perguntas):
                raise InconsistenciaRodada("Checkpoint possui formato ou quantidade de registros inválida.")
            if registro.get("id") != perguntas[numero - 1]["id"]:
                raise InconsistenciaRodada(
                    f"Ordem/ID divergente na linha {numero}; possível conjunto de perguntas diferente."
                )
            if registro.get("configuracao") != configuracao or registro.get("rubrica_versao") != rubrica:
                raise InconsistenciaRodada(
                    f"Configuração ou rubrica divergente na linha {numero}; não misturar resultados."
                )
            dados.append(registro)
    return dados


def executar_com_checkpoint(perguntas: list[dict], responder: Callable[[str], dict],
                           caminho: Path, configuracao: str, rubrica: str,
                           progresso: bool = True) -> list[dict]:
    """`responder` recebe a pergunta e devolve uma linha de avaliação pronta.

    Escreve a cada pergunta concluída. Uma exceção não é mascarada: as linhas já
    gravadas permanecem e a próxima execução pode retomar do ID seguinte.
    """
    anteriores = ler_checkpoint(caminho, perguntas, configuracao, rubrica)
    total = len(perguntas)
    if progresso:
        print(f"{configuracao}: {len(anteriores)}/{total} perguntas preservadas", flush=True)
    if len(anteriores) == total:
        return anteriores
    caminho.parent.mkdir(parents=True, exist_ok=True)
    modo = "a" if caminho.exists() else "x"
    with caminho.open(modo, encoding="utf-8", newline="\n") as saida:
        for i in range(len(anteriores), total):
            registro = responder(perguntas[i]["pergunta"])
            if not isinstance(registro, dict) or registro.get("id") != perguntas[i]["id"]:
                raise InconsistenciaRodada(f"A avaliação retornou ID inválido na pergunta {i + 1}.")
            if registro.get("configuracao") != configuracao or registro.get("rubrica_versao") != rubrica:
                raise InconsistenciaRodada(f"A avaliação retornou metadados incompatíveis na pergunta {i + 1}.")
            linha = json.dumps(registro, ensure_ascii=False, allow_nan=False)
            saida.write(linha + "\n")
            saida.flush()
            os.fsync(saida.fileno())
            anteriores.append(registro)
            if progresso:
                print(f"\r{configuracao}: {i + 1}/{total}", end="", flush=True)
    if progresso:
        print()
    return anteriores


@contextmanager
def trava_execucao(pasta: Path):
    """Evita dois processos gravando simultaneamente o mesmo conjunto de resultados."""
    trava = pasta / ".execucao.lock"
    try:
        with trava.open("x", encoding="utf-8") as f:
            f.write(f"pid={os.getpid()}\n")
    except FileExistsError as e:
        raise InconsistenciaRodada(
            f"Existe a trava {trava}. Verifique se uma avaliação ainda está executando. "
            "Se não estiver, remova SOMENTE a trava e execute --retomar novamente."
        ) from e
    try:
        yield
    finally:
        trava.unlink(missing_ok=True)


def escrever_placar_atomico(caminho: Path, resumos: list[dict]) -> None:
    if not resumos:
        raise InconsistenciaRodada("Não é permitido gravar placar vazio.")
    temporario = caminho.with_suffix(caminho.suffix + ".tmp")
    with temporario.open("w", encoding="utf-8", newline="") as arquivo:
        campos = list(resumos[0].keys())
        escritor = csv.DictWriter(arquivo, fieldnames=campos, extrasaction="ignore")
        escritor.writeheader()
        escritor.writerows(resumos)
        arquivo.flush()
        os.fsync(arquivo.fileno())
    os.replace(temporario, caminho)

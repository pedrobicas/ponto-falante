"""Índice vetorial (FAISS) sobre os trechos, com embeddings multilíngues gratuitos (fastembed/ONNX).

Similaridade de cosseno: vetores normalizados + IndexFlatIP (produto interno).
Busca exata, adequada para uma base de algumas centenas de trechos.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from functools import lru_cache

import faiss
import numpy as np
from fastembed import TextEmbedding

from . import BASE
from .trechos import Trecho, carregar

MODELO_EMB = os.environ.get("PF_EMBEDDINGS", "intfloat/multilingual-e5-large")
_cache_modelos: dict[str, TextEmbedding] = {}


def modelo(nome: str = MODELO_EMB) -> TextEmbedding:
    if nome not in _cache_modelos:
        _cache_modelos[nome] = TextEmbedding(nome, cache_dir=str(BASE.parent / ".cache_embeddings"))
    return _cache_modelos[nome]


def _prep(textos: list[str], nome: str, tipo: str) -> list[str]:
    # Modelos E5 pedem prefixos "query:" / "passage:".
    if "e5" in nome.lower():
        return [f"{tipo}: {t}" for t in textos]
    return textos


def embutir(textos: list[str], nome: str = MODELO_EMB, tipo: str = "passage") -> np.ndarray:
    vet = np.array(list(modelo(nome).embed(_prep(textos, nome, tipo))), dtype="float32")
    faiss.normalize_L2(vet)
    return vet


@dataclass
class Resultado:
    trecho: Trecho
    score: float


class Indice:
    def __init__(self, trechos: list[Trecho], nome_modelo: str = MODELO_EMB, vetores: np.ndarray | None = None):
        self.trechos = trechos
        self.nome_modelo = nome_modelo
        vetores = vetores if vetores is not None else embutir([f"{t.documento}. {t.texto}" for t in trechos], nome_modelo)
        self.index = faiss.IndexFlatIP(vetores.shape[1])
        self.index.add(vetores)

    def buscar(self, consulta: str, k: int = 3) -> list[Resultado]:
        # Cache limitado em memória; nunca persiste perguntas. O índice é imutável após carregar.
        # Cópias impedem que um consumidor altere os resultados das próximas consultas.
        return [Resultado(self.trechos[i], score) for i, score in self._buscar(consulta, k)]

    @lru_cache(maxsize=128)
    def _buscar(self, consulta: str, k: int) -> tuple:
        q = embutir([consulta], self.nome_modelo, tipo="query")
        scores, ids = self.index.search(q, k)
        return tuple((int(i), float(s)) for s, i in zip(scores[0], ids[0]) if i >= 0)

    def salvar(self, pasta: Path = BASE) -> None:
        faiss.write_index(self.index, str(pasta / "indice.faiss"))
        (pasta / "indice_meta.json").write_text(json.dumps(
            {"modelo": self.nome_modelo, "trechos": [t.trecho_id for t in self.trechos]}, ensure_ascii=False),
            encoding="utf-8")

    @classmethod
    def carregar(cls, pasta: Path = BASE) -> "Indice":
        meta = json.loads((pasta / "indice_meta.json").read_text(encoding="utf-8"))
        trechos = {t.trecho_id: t for t in carregar(pasta)}
        ordem = [trechos[i] for i in meta["trechos"]]
        obj = cls.__new__(cls)
        obj.trechos, obj.nome_modelo = ordem, meta["modelo"]
        obj.index = faiss.read_index(str(pasta / "indice.faiss"))
        return obj

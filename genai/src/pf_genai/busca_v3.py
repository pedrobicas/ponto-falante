"""Busca v3: trechos v3 + expansão determinística da consulta + híbrida (BM25 + e5-large) + reordenação
por cross-encoder multilíngue local (BAAI/bge-reranker-v2-m3, int8, ONNX/CPU, Apache 2.0).

Cada peça é ligável/desligável para as ablações do DEV v3 (scripts/diagnostico_busca_v3.py).

Por que expansão por dicionário e não reescrita por LLM (v1/v2): a reescrita do LLM custa ~1 s, varia com o
modelo e, no erro 3 da v1, trocou a palavra que distinguia o público. A expansão só ACRESCENTA termos oficiais
(nunca remove a pergunta original), é instantânea e auditável.
"""
from __future__ import annotations

import json
import hashlib
import os
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from threading import Lock

import faiss
import numpy as np
from rank_bm25 import BM25Okapi

from . import BASE
from .indice import embutir, MODELO_EMB
from .trechos_v3 import TrechoV3, carregar as carregar_v3

MODELO_RERANK = os.environ.get("PF_RERANKER", "BAAI/bge-reranker-v2-m3-int8")


def normalizar(s: str) -> str:
    s = unicodedata.normalize("NFKD", (s or "").lower())
    return "".join(c for c in s if not unicodedata.combining(c))


_STOP = set("a o as os de da do das dos e em no na nos nas um uma uns umas para pra pro por com que se eu meu minha "
            "me ja ta to tô la cá ca ele ela isso esse essa este esta ao aos sua seu suas seus mais muito".split())


def _radical(t: str) -> str:
    # radicalização leve (plural e flexões frequentes); suficiente para BM25 em FAQ curta
    for suf in ("coes", "cao", "mente", "s"):
        if len(t) > 4 and t.endswith(suf):
            return t[: -len(suf)]
    return t


def tokens(s: str) -> list[str]:
    return [_radical(t) for t in re.findall(r"\w+", normalizar(s)) if len(t) > 1 and t not in _STOP]


# ---------------- Expansão da consulta (coloquial -> termos oficiais) ----------------
# Regras genéricas do domínio, escritas a partir do vocabulário das fontes (não de perguntas do teste).
_EXPANSOES: list[tuple[str, str]] = [
    (r"\b(idos[oa]s?|velhinh\w*|terceira idade|aposentad\w*|vov[oóô]|av[oóô]s?)\b", "pessoa idosa"),
    (r"\b(cart[aã]o|bilhete)\s+(de|do|da)\s+(idos[oa]|velhinh\w*)", "Bilhete Único Especial da Pessoa Idosa"),
    (r"\b(deficien\w*|pcd|cadeirante|cego|cega|surd[oa]|autis\w*|tea|baixa vis[aã]o|mobilidade reduzida)\b",
     "pessoa com deficiência Bilhete Único Especial da Pessoa com Deficiência"),
    (r"\b(estudante|escola|faculdade|universidade|aluno|aluna|col[eé]gio)\b", "estudante instituição de ensino"),
    (r"\b(passagem|passe|pagar o [oô]nibus|pago [oô]nibus|paga [oô]nibus)\b", "tarifa"),
    (r"\b(gr[aá]tis|de gra[cç]a|sem pagar|n[aã]o pag)\w*", "gratuidade isenção"),
    (r"\b(segunda via|2a via|2ª via|outro cart[aã]o|cart[aã]o novo)\b", "2ª via"),
    (r"\b(firma|patr[aã]o|empresa onde trabalho)\b", "empresa RH vale-transporte"),
    (r"\b(metr[oô]|trem|cptm|trilhos?)\b", "metrô/trem trilhos"),
    (r"\b(venc\w*|validade|expira\w*)\b", "prazo de validade"),
    (r"\b(empresta\w*|emprest\w*|outra pessoa usar|usar o (meu )?cart[aã]o)\b", "uso pessoal intransferível outra pessoa uso indevido"),
    (r"\b(perdi|perdeu|roubaram|roubad\w*|furt\w*|extravi\w*)\b", "perda roubo furto cancelamento bloqueio"),
    (r"\b(quebr\w*|trinc\w*|n[aã]o funciona|parou de funcionar|estragou)\b", "quebrado trincado mau funcionamento"),
    (r"\b(cheg\w* em casa|entrega\w*|demora\w* pra chegar|receber em casa)\b", "prazo para entrega"),
    (r"\b(recarg\w*|carreg\w*|colocar cr[eé]dito|por cr[eé]dito)\b", "recarga"),
    (r"\b(catraca|validador)\b", "validador catraca"),
    (r"\b(morreu|faleceu|falecimento|[oó]bito)\b", "óbito falecimento"),
    (r"\b(m[eé]dico|laudo|formul[aá]rio)\b", "Formulário de Solicitação médico laudo"),
    (r"\b(baixa renda|cad ?[uú]nico|renda)\b", "gratuidade baixa renda CadÚnico renda per capita"),
    (r"\b(lei|direito|estatuto)\b", "lei direito assegurado"),
]


def expandir(pergunta: str) -> str:
    extra: list[str] = []
    for rx, termos in _EXPANSOES:
        if re.search(rx, pergunta, flags=re.IGNORECASE):
            extra.append(termos)
    for m in re.finditer(r"\b(\d{2,3})\s*anos\b", pergunta):
        idade = int(m.group(1))
        if 60 <= idade <= 64:
            extra.append("pessoa idosa 60 a 64 anos gratuidade Bilhete Único Comum")
        elif idade >= 65:
            extra.append("pessoa idosa 65 anos ou mais Bilhete Único Especial da Pessoa Idosa")
    return (pergunta + " | " + " ".join(dict.fromkeys(extra))) if extra else pergunta


# ---------------- Índice v3 ----------------
@dataclass
class Achado:
    trecho: TrechoV3
    score: float           # score final usado na ordenação (reranker se ligado, senão cosseno/RRF)
    cosseno: float         # cosseno e5 com a pergunta original
    rerank: float | None = None


class IndiceV3:
    def __init__(self, trechos: list[TrechoV3], vetores: np.ndarray | None = None, nome_modelo: str = MODELO_EMB):
        self.trechos = trechos
        self.nome_modelo = nome_modelo
        if vetores is None:
            vetores = embutir([t.texto_indexado for t in trechos], nome_modelo)
        self.vetores = vetores
        self.index = faiss.IndexFlatIP(vetores.shape[1])
        self.index.add(vetores)
        self.bm25 = BM25Okapi([tokens(t.texto_indexado) for t in trechos])
        self._por_id = {t.trecho_id: i for i, t in enumerate(trechos)}

    @staticmethod
    def assinatura(trechos: list[TrechoV3]) -> str:
        dados = [(t.trecho_id, t.texto_indexado, t.url, t.ids_v1) for t in trechos]
        return hashlib.sha256(json.dumps(dados, ensure_ascii=False).encode("utf-8")).hexdigest()

    # persistência
    def salvar(self, pasta: Path = BASE) -> None:
        faiss.write_index(self.index, str(pasta / "indice_v3.faiss"))
        (pasta / "indice_v3_meta.json").write_text(json.dumps(
            {"modelo": self.nome_modelo, "trechos": [t.trecho_id for t in self.trechos],
             "conteudo_sha256": self.assinatura(self.trechos)}, ensure_ascii=False),
            encoding="utf-8")

    @classmethod
    def carregar(cls, pasta: Path = BASE) -> "IndiceV3":
        meta = json.loads((pasta / "indice_v3_meta.json").read_text(encoding="utf-8"))
        por_id = {t.trecho_id: t for t in carregar_v3(pasta)}
        trechos = [por_id[i] for i in meta["trechos"]]
        if meta.get("conteudo_sha256") != cls.assinatura(trechos):
            raise ValueError("Índice v3 sem assinatura ou desatualizado: reconstrua os embeddings.")
        idx = faiss.read_index(str(pasta / "indice_v3.faiss"))
        if idx.ntotal != len(trechos):
            raise ValueError("Quantidade de vetores difere dos trechos v3.")
        vet = np.vstack([idx.reconstruct(i) for i in range(idx.ntotal)]).astype("float32")
        return cls(trechos, vet, meta["modelo"])

    @classmethod
    def carregar_ou_criar(cls, pasta: Path = BASE) -> "IndiceV3":
        if (pasta / "indice_v3.faiss").exists() and (pasta / "trechos_v3.jsonl").exists():
            try:
                return cls.carregar(pasta)
            except (ValueError, KeyError, FileNotFoundError):
                # Base alterada: nunca associa silenciosamente vetor antigo ao texto novo.
                ts = carregar_v3(pasta)
                obj = cls(ts)
                obj.salvar(pasta)
                return obj
        from .trechos_v3 import gerar_trechos_v3, salvar
        ts = gerar_trechos_v3(pasta)
        salvar(ts, pasta)
        obj = cls(ts)
        obj.salvar(pasta)
        return obj

    def cosseno(self, consulta: str) -> np.ndarray:
        q = embutir([consulta], self.nome_modelo, tipo="query")[0]
        return self.vetores @ q

    def buscar(self, pergunta: str, k: int = 4, *, expansao: bool = True, hibrida: bool = True,
               rerank: bool = True, n_cand: int = 12, rrf_k: int = 60, filtro=None) -> list[Achado]:
        if k <= 0:
            return []
        elegiveis = np.array([i for i, t in enumerate(self.trechos) if filtro is None or filtro(t)], dtype=int)
        if not len(elegiveis):
            return []
        n_cand = max(k, n_cand)
        consultas = [pergunta]
        if expansao:
            e = expandir(pergunta)
            if e != pergunta:
                consultas.append(e)
        # Um lote ONNX para pergunta e expansão; mesma normalização/prefixo E5 do índice.
        vet_consultas = embutir(consultas, self.nome_modelo, tipo="query")
        cossenos = self.vetores @ vet_consultas.T
        cos_orig = cossenos[:, 0]
        rrf: dict[int, float] = {}
        for qi, q in enumerate(consultas):
            cos = cossenos[:, qi]
            for pos, i in enumerate(elegiveis[np.argsort(-cos[elegiveis], kind="stable")[:n_cand]]):
                rrf[int(i)] = rrf.get(int(i), 0) + 1 / (rrf_k + pos + 1)
            if hibrida:
                sc = self.bm25.get_scores(tokens(q))
                for pos, i in enumerate(elegiveis[np.argsort(-sc[elegiveis], kind="stable")[:n_cand]]):
                    if sc[i] <= 0:
                        break
                    rrf[int(i)] = rrf.get(int(i), 0) + 1 / (rrf_k + pos + 1)
        cand = sorted(rrf, key=lambda i: -rrf[i])[: max(n_cand, k)]
        if rerank:
            notas = reordenar(pergunta, [self.trechos[i].texto_indexado for i in cand])
            ordem = sorted(zip(cand, notas), key=lambda x: -x[1])
            return [Achado(self.trechos[i], float(n), float(cos_orig[i]), float(n)) for i, n in ordem[:k]]
        if not hibrida and not expansao:
            ordem = [int(i) for i in elegiveis[np.argsort(-cos_orig[elegiveis], kind="stable")[:k]]]
            return [Achado(self.trechos[i], float(cos_orig[i]), float(cos_orig[i])) for i in ordem]
        return [Achado(self.trechos[i], float(rrf[i]), float(cos_orig[i])) for i in cand[:k]]


# ---------------- Cross-encoder ----------------
_reranker = None
_trava_reranker = Lock()


def _modelo_rerank():
    global _reranker
    with _trava_reranker:
        if _reranker is None:
            from fastembed.rerank.cross_encoder import TextCrossEncoder
            _reranker = TextCrossEncoder(MODELO_RERANK, cache_dir=str(BASE.parent / ".cache_embeddings"))
    return _reranker


def reordenar(pergunta: str, textos: list[str]) -> list[float]:
    """Nota de relevância (logit) do cross-encoder para cada par (pergunta, trecho)."""
    if not textos:
        return []
    return [float(x) for x in _modelo_rerank().rerank(pergunta, textos)]


def sigmoide(x: float) -> float:
    return float(1 / (1 + np.exp(-x)))

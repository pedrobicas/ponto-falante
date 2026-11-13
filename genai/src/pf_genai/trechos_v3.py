"""Trechos v3: reorganiza a base v1 (trechos.jsonl) sem alterar o texto oficial.

Problemas da divisão v1 encontrados no diagnóstico do DEV v3 (ver RELATORIO.md, "Iteração v3"):
 1. Texto repetido: todas as 28 respostas do idoso 65+ terminam com o aviso "Pessoas com 60 a 64 anos também
    têm direito à gratuidade ... Clique aqui e saiba mais." Esse aviso puxa perguntas de 60 a 64 anos para
    trechos de 65+ e dilui o vetor do trecho. Na v3 ele sai das respostas e vira UM trecho próprio.
 2. Pares pergunta+resposta cortados em 700 caracteres: há trechos que só têm a pergunta (sem resposta) e
    continuações "(cont.)" separadas da pergunta. Na v3, um par = um trecho (as leis seguem por artigo).
 3. Pergunta "colada" no fim da resposta anterior (links da página viraram texto corrido), por exemplo
    "... Aplicativos e outras opções O que fazer se o Bilhete Único apresentar mau funcionamento?".
    Na v3 o par é separado na pergunta embutida.
 4. Contexto do trecho: cada trecho v3 recebe um cabeçalho com o público ("Pessoa idosa 65+",
    "Pessoa idosa 60 a 64 anos", "Pessoa com deficiência", "Estudante", "Bilhete Único", "Tarifas", "Lei").

Cada trecho v3 guarda `ids_v1` (os trechos v1 de onde veio), para que o gabarito dos conjuntos de avaliação
(escrito com ids v1) continue valendo e para que recall seja comparável entre as duas divisões.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import BASE
from .trechos import carregar as carregar_v1

AVISO_60_64 = ("Pessoas com 60 a 64 anos também têm direito à gratuidade, para isso basta carregar o benefício "
               "no Bilhete Único Comum que já possuem.")
_RUIDO = [re.compile(re.escape(AVISO_60_64) + r"\s*(Clique aqui e saiba mais\.)?"),
          re.compile(r"^\s*Clique (aqui )?e saiba mais\.?\s*$", re.M),
          re.compile(r"^\s*Clique aqui e imprima o Formulário\.?\s*$", re.M),
          re.compile(r"^\s*Acesse e faça o seu cadastro\.?\s*$", re.M),
          re.compile(r"^\s*Consulte aqui\.?\s*$", re.M)]
_PREFIXO_LIXO = re.compile(r"^(Site de Atendimento da SPTrans Postos da SPTrans |https?://\S+\s+)")

PUBLICO_DOC = {
    "sptrans-gratuidade-65-mais": "Pessoa idosa com 65 anos ou mais (Bilhete Único Especial da Pessoa Idosa)",
    "sptrans-gratuidade-60-64": "Pessoa idosa de 60 a 64 anos (gratuidade no Bilhete Único Comum)",
    "sptrans-bilhete-pcd": "Pessoa com deficiência (Bilhete Único Especial da Pessoa com Deficiência)",
    "sptrans-bilhete-estudante": "Estudante (Bilhete Único de Estudante)",
    "sptrans-bilhete-unico": "Bilhete Único (todos os passageiros)",
    "sptrans-tarifas": "Tarifas vigentes (todos os passageiros)",
    "lei-10741-transporte": "Lei federal: Estatuto da Pessoa Idosa",
    "lei-13146-transporte": "Lei federal: Lei Brasileira de Inclusão da Pessoa com Deficiência",
}


@dataclass
class TrechoV3:
    trecho_id: str
    documento_id: str
    documento: str
    url: str
    texto: str                     # texto oficial (sem o aviso repetido); é o que vai para o LLM
    ids_v1: list[str] = field(default_factory=list)

    @property
    def texto_indexado(self) -> str:
        """Texto usado no embedding e no BM25: público + texto."""
        return f"{PUBLICO_DOC.get(self.documento_id, self.documento)}. {self.texto}"


def _limpar(texto: str) -> str:
    for rx in _RUIDO:
        texto = rx.sub("", texto)
    texto = _PREFIXO_LIXO.sub("", texto.strip())
    texto = re.sub(r"[ \t ]+", " ", texto)
    return re.sub(r"\n{2,}", "\n", texto).strip()


def _eh_continuacao(texto: str) -> bool:
    primeira = texto.splitlines()[0] if texto else ""
    return "(cont.)" in primeira


def _sem_rotulo_cont(texto: str) -> str:
    """Remove a repetição "Pergunta? (cont.) " / "Art. 39 (cont.) " do início de uma continuação."""
    return re.sub(r"^.*?\(cont\.\)\s*", "", texto, count=1, flags=re.S)


_PERGUNTA_EMBUTIDA = re.compile(r"(?<=[a-zà-ú\)\.”\"]) (?=(?:O que|Existe|Não estou|Já possuo|Tenho interesse|Como|Quais?|Qual)\b[^?\n]{5,200}\?)")


def _separar_pergunta_embutida(texto: str) -> list[str]:
    """Divide '... resposta anterior O que fazer se ...?\nresposta' em dois pares. Só divide quando a
    pergunta embutida termina com '?' e não está no início do texto."""
    linhas = texto.splitlines()
    for i, l in enumerate(linhas):
        if i == 0:
            continue
        m = _PERGUNTA_EMBUTIDA.search(l)
        if m and l.rstrip().endswith("?"):
            antes = "\n".join(linhas[:i] + [l[:m.start()].rstrip()]).strip()
            depois = "\n".join([l[m.end():].strip()] + linhas[i + 1:]).strip()
            return [antes] + _separar_pergunta_embutida(depois)
    # pergunta embutida na 1ª linha (ex.: "Onde devo fazer compra ...? • Postos de venda ... O que fazer se ...?")
    if linhas and linhas[0].count("?") >= 2:
        l = linhas[0]
        primeira = l.index("?") + 1
        m = _PERGUNTA_EMBUTIDA.search(l, primeira)
        if m and l.rstrip().endswith("?"):
            antes = l[:m.start()].rstrip()
            depois = "\n".join([l[m.end():].strip()] + linhas[1:]).strip()
            return [antes] + _separar_pergunta_embutida(depois)
    return [texto]


def gerar_trechos_v3(base: Path = BASE) -> list[TrechoV3]:
    v1 = carregar_v1(base)
    grupos: list[dict] = []
    for t in v1:
        texto = _limpar(t.texto)
        if grupos and grupos[-1]["doc"] == t.documento_id and (_eh_continuacao(t.texto) or not texto):
            if texto:
                grupos[-1]["texto"] += "\n" + _sem_rotulo_cont(texto)
            grupos[-1]["ids"].append(t.trecho_id)
            continue
        grupos.append({"doc": t.documento_id, "documento": t.documento, "url": t.url, "texto": texto,
                       "ids": [t.trecho_id]})
    # Trecho só com a pergunta (sem resposta) + continuação já foram unidos acima pelo "(cont.)".
    saida: list[TrechoV3] = []
    contador: dict[str, int] = {}
    aviso_incluido = False
    for g in grupos:
        partes = _separar_pergunta_embutida(g["texto"]) if g["doc"].startswith("sptrans-") else [g["texto"]]
        for p in partes:
            p = p.strip()
            if len(p) < 30:
                continue
            contador[g["doc"]] = contador.get(g["doc"], 0) + 1
            tid = f"v3-{g['doc']}-{contador[g['doc']]:03d}"
            saida.append(TrechoV3(tid, g["doc"], g["documento"], g["url"], p, list(g["ids"])))
        if g["doc"] == "sptrans-gratuidade-65-mais" and not aviso_incluido:
            aviso_incluido = True
    # O aviso repetido vira um trecho próprio (fonte: página do idoso 65+, trechos 001 a 028)
    ids_aviso = [t.trecho_id for t in v1 if t.documento_id == "sptrans-gratuidade-65-mais" and AVISO_60_64 in t.texto]
    d = next(t for t in v1 if t.documento_id == "sptrans-gratuidade-65-mais")
    saida.append(TrechoV3("v3-sptrans-gratuidade-65-mais-aviso", d.documento_id, d.documento, d.url,
                          "Pessoas com 60 a 64 anos também têm direito à gratuidade? " + AVISO_60_64, ids_aviso[:3]))
    return saida


def salvar(trechos: list[TrechoV3], base: Path = BASE) -> Path:
    caminho = base / "trechos_v3.jsonl"
    with caminho.open("w", encoding="utf-8") as f:
        for t in trechos:
            f.write(json.dumps(asdict(t), ensure_ascii=False) + "\n")
    return caminho


def carregar(base: Path = BASE) -> list[TrechoV3]:
    with (base / "trechos_v3.jsonl").open(encoding="utf-8") as f:
        return [TrechoV3(**json.loads(l)) for l in f if l.strip()]

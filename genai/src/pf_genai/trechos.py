"""Divide os documentos da base em trechos (chunks), cada um com sua fonte.

Estratégia:
- Leis: um trecho por artigo (o artigo é a unidade natural de citação);
  artigos longos são quebrados por parágrafo/inciso mantendo o "Art. X" no início.
- Páginas da SPTrans: blocos de parágrafos até ~700 caracteres, sem cortar frases.
"""
from __future__ import annotations

import csv
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from . import BASE

TAM_MAX = 700


@dataclass
class Trecho:
    trecho_id: str
    documento_id: str
    documento: str        # título legível (vai no campo "documento" da resposta)
    url: str
    texto: str


def _quebrar(texto: str, prefixo: str = "") -> list[str]:
    """Agrupa linhas/parágrafos em blocos de até TAM_MAX caracteres."""
    partes = [p.strip() for p in re.split(r"\n+", texto) if p.strip()]
    blocos, atual = [], ""
    for p in partes:
        if atual and len(atual) + len(p) + 1 > TAM_MAX:
            blocos.append(atual)
            atual = (prefixo + " (cont.) " if prefixo else "") + p
        else:
            atual = f"{atual}\n{p}" if atual else p
    if atual:
        blocos.append(atual)
    return blocos


def dividir_lei(texto: str) -> list[str]:
    artigos = re.split(r"\n(?=Art\.\s*\d)", "\n" + texto)
    saida = []
    for art in artigos:
        art = art.strip()
        if not art:
            continue
        m = re.match(r"(Art\.\s*\d+[º°o]?(?:-[A-Z])?)", art)
        rotulo = m.group(1) if m else ""
        saida.extend(_quebrar(art, rotulo) if len(art) > TAM_MAX else [art])
    return saida


def _juntar_linhas_quebradas(texto: str) -> list[str]:
    """Na extração do HTML, links viram linhas soltas ("Dirija-se a um" / "Posto..." / "mais próximo").
    Juntamos a linha seguinte enquanto a atual não termina com pontuação de fim de frase."""
    linhas = [l.strip() for l in texto.splitlines() if l.strip()]
    saida: list[str] = []
    for l in linhas:
        if saida and not re.search(r"[.?!:;]$", saida[-1]):
            sep = "" if re.match(r"^[,.;:)]", l) else " "
            saida[-1] = saida[-1] + sep + l
        else:
            saida.append(l)
    return saida


def dividir_perguntas_respostas(texto: str) -> list[str]:
    """Páginas de Perguntas e Respostas: um trecho por par pergunta + resposta."""
    linhas = _juntar_linhas_quebradas(texto)
    pares, atual = [], []
    for l in linhas:
        if l.endswith("?") and atual and not atual[-1].endswith("?"):
            pares.append("\n".join(atual))
            atual = []
        atual.append(l)
    if atual:
        pares.append("\n".join(atual))
    saida = []
    for p in pares:
        if len(p) > TAM_MAX:
            pergunta = p.splitlines()[0]
            saida.extend(_quebrar(p, pergunta if pergunta.endswith("?") else ""))
        else:
            saida.append(p)
    return saida


def formatar_tabela_tarifas(texto: str) -> str:
    """A página de tarifas vira, no HTML extraído, uma sequência 'rótulo' / 'R$ valor'.
    Reescrevemos cada célula como frase ("Tarifa ...: R$ 5,30."), sem alterar nenhum valor.
    Cada seção (Mensal, 24 horas, Semanal) aparece repetida no HTML (aba + título):
    vale a primeira linha de cada sequência de títulos."""
    linhas = [l.strip() for l in texto.splitlines() if l.strip()]
    saida, rotulo, secao, ultima_era_secao = [], [], "", False
    fim_tabela = next((i for i, l in enumerate(linhas) if l.startswith("A tarifa de R$")), len(linhas))
    for l in linhas[:fim_tabela]:
        if l in ("PARA PAGAMENTO EM:", "VALOR DA TARIFA:", "Tarifas Vigentes", "•", "Valores das tarifas vigentes."):
            continue
        if l.startswith("Atualizado em"):
            saida.append(f"Tarifas vigentes da SPTrans ({l.lower()}).")
            continue
        m = re.match(r"Crédito Eletrônico Comum - (.+)$", l)
        if m:
            if not ultima_era_secao:
                secao = m.group(1)
            ultima_era_secao = True
            continue
        ultima_era_secao = False
        if l.startswith("R$"):
            nome = " ".join(rotulo).replace(" • ", " · ").replace("•", "·").strip()
            if secao:
                nome = f"Crédito Eletrônico Comum {secao} · {nome}"
            saida.append(f"Tarifa {nome}: {l}.")
            rotulo = []
        else:
            rotulo.append(l)
    return "\n".join(saida) + "\n" + "\n".join(_juntar_linhas_quebradas("\n".join(linhas[fim_tabela:])))


def carregar_fontes(base: Path = BASE) -> list[dict]:
    with (base / "fontes.csv").open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def gerar_trechos(base: Path = BASE) -> list[Trecho]:
    trechos: list[Trecho] = []
    for fonte in carregar_fontes(base):
        arq = base / "textos" / f"{fonte['id']}.txt"
        if not arq.exists():
            continue
        linhas = arq.read_text(encoding="utf-8").strip().splitlines()
        titulo = linhas[0].strip()
        corpo = "\n".join(l for l in linhas[1:] if not l.startswith("Fonte:"))
        if fonte["id"].startswith("lei-"):
            blocos = dividir_lei(corpo)
        elif "perguntas-e-respostas" in fonte["url"]:
            blocos = dividir_perguntas_respostas(corpo)
        elif fonte["id"] == "sptrans-tarifas":
            blocos = _quebrar(formatar_tabela_tarifas(corpo))
        else:
            blocos = _quebrar("\n".join(_juntar_linhas_quebradas(corpo)))
        for i, bloco in enumerate(blocos, 1):
            if len(bloco) < 40:          # descarta restos sem conteúdo (títulos soltos)
                continue
            trechos.append(Trecho(f"{fonte['id']}-{i:03d}", fonte["id"], fonte.get("titulo") or titulo,
                                  fonte["url"], bloco))
    return trechos


def salvar(trechos: list[Trecho], base: Path = BASE) -> Path:
    caminho = base / "trechos.jsonl"
    with caminho.open("w", encoding="utf-8") as f:
        for t in trechos:
            f.write(json.dumps(asdict(t), ensure_ascii=False) + "\n")
    return caminho


def carregar(base: Path = BASE) -> list[Trecho]:
    with (base / "trechos.jsonl").open(encoding="utf-8") as f:
        return [Trecho(**json.loads(l)) for l in f if l.strip()]

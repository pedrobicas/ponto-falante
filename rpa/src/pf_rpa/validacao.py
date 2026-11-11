"""Validação e deduplicação das passagens (etapas 2 e 3 do fluxo).

Cada registro inválido vai para uma lista com o MOTIVO, para auditoria
e para mostrar no boletim quanto dado foi descartado.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .config import Regras
from .gtfs import Rede

CAMPOS_OBRIGATORIOS = ("ponto", "linha", "programado_em", "previsto_em", "fonte")
FONTES_VALIDAS = {"olhovivo", "simulador"}
_HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def minutos_do_dia(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def diferenca_min(programado: str, previsto: str) -> int:
    """previsto - programado, em minutos, tratando a virada da meia-noite."""
    d = minutos_do_dia(previsto) - minutos_do_dia(programado)
    if d < -720:
        d += 1440
    elif d > 720:
        d -= 1440
    return d


@dataclass
class Passagem:
    ponto: str
    linha: str
    sentido: str
    veiculo: str | None
    programado_em: str
    previsto_em: str
    atraso_min: int
    acessivel: bool
    fonte: str


@dataclass
class ResultadoValidacao:
    validos: list[Passagem] = field(default_factory=list)
    invalidos: list[dict[str, Any]] = field(default_factory=list)   # {"indice", "motivo"}
    duplicados: int = 0
    fora_escopo: int = 0

    def contagem_motivos(self) -> dict[str, int]:
        cont: dict[str, int] = {}
        for item in self.invalidos:
            cont[item["motivo"]] = cont.get(item["motivo"], 0) + 1
        return dict(sorted(cont.items()))


def _motivo_invalido(reg: Any, rede: Rede, regras: Regras) -> str | None:
    if not isinstance(reg, dict):
        return "formato_invalido"
    for campo in CAMPOS_OBRIGATORIOS:
        if reg.get(campo) in (None, ""):
            return "campo_vazio"
    if reg["fonte"] not in FONTES_VALIDAS:
        return "fonte_desconhecida"
    if str(reg["linha"]) not in rede.linhas:
        return "linha_inexistente"
    if not _HHMM.match(str(reg["programado_em"])) or not _HHMM.match(str(reg["previsto_em"])):
        return "horario_mal_formatado"
    atraso = diferenca_min(reg["programado_em"], reg["previsto_em"])
    if atraso < -regras.antecipacao_maxima_min or atraso > regras.atraso_maximo_min:
        return "horario_incoerente"
    return None


def validar(registros: list[Any], rede: Rede, regras: Regras,
            linhas_monitoradas: list[str], pontos_monitorados: list[str]) -> ResultadoValidacao:
    res = ResultadoValidacao()
    vistos: set[tuple] = set()
    for i, reg in enumerate(registros):            # estrutura de repetição sobre a coleção
        motivo = _motivo_invalido(reg, rede, regras)
        if motivo:
            res.invalidos.append({"indice": i, "motivo": motivo})
            continue
        linha, ponto = str(reg["linha"]), str(reg["ponto"])
        if (linhas_monitoradas and linha not in linhas_monitoradas) or (
            pontos_monitorados and ponto not in pontos_monitorados
        ):
            res.fora_escopo += 1
            continue
        veiculo = reg.get("veiculo") or None
        # Duplicado = mesmo veículo, mesmo ponto, mesmo minuto. Sem veículo, usa a linha+sentido.
        chave = (veiculo or f"{linha}|{reg.get('sentido', '')}", ponto, reg["previsto_em"])
        if chave in vistos:
            res.duplicados += 1
            continue
        vistos.add(chave)
        res.validos.append(Passagem(
            ponto=ponto, linha=linha, sentido=str(reg.get("sentido") or ""),
            veiculo=veiculo, programado_em=reg["programado_em"], previsto_em=reg["previsto_em"],
            atraso_min=diferenca_min(reg["programado_em"], reg["previsto_em"]),
            acessivel=bool(reg.get("acessivel", False)), fonte=reg["fonte"],
        ))
    return res

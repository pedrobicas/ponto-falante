"""Regra de decisão por linha (etapa 4).

Para cada linha monitorada:
- atraso médio (min) = média de (previsto - programado), sem contar adiantamentos como "negativos
  que compensam": adiantado conta como 0, porque para quem espera no ponto um ônibus adiantado
  também é um ônibus perdido, não um bônus.
- maior intervalo (min) = maior espera entre dois ônibus consecutivos da linha no mesmo ponto
  e sentido (ignorando buracos que a própria tabela programada já prevê).

CRÍTICA  se atraso médio > atraso_critico  OU maior intervalo > intervalo_critico
ATENÇÃO  se atraso médio > atraso_atencao  OU maior intervalo > intervalo_atencao
OK       caso contrário
SEM_DADOS se houver menos passagens que o mínimo (não decidimos no escuro).
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from .config import Regras
from .validacao import Passagem, minutos_do_dia

CRITICA, ATENCAO, OK, SEM_DADOS = "CRITICA", "ATENCAO", "OK", "SEM_DADOS"
ORDEM = {CRITICA: 0, ATENCAO: 1, SEM_DADOS: 2, OK: 3}


@dataclass
class SituacaoLinha:
    linha: str
    status: str
    atraso_medio_min: float | None
    intervalo_max_min: int | None
    passagens: int
    acessiveis_pct: float | None
    fontes: list[str]
    motivo: str


def _intervalo_maximo(passagens: list[Passagem], limite_programado: float) -> int | None:
    """Maior espera real entre ônibus consecutivos no mesmo ponto e sentido.

    Pares cujo intervalo PROGRAMADO já é maior que o limite crítico são ignorados:
    se a própria tabela prevê um buraco (ex.: entre o pico da manhã e o da tarde,
    ou de madrugada), isso não é falha da operação.
    """
    grupos: dict[tuple[str, str], list[tuple[int, int]]] = defaultdict(list)
    for p in passagens:
        grupos[(p.ponto, p.sentido)].append((minutos_do_dia(p.previsto_em), minutos_do_dia(p.programado_em)))
    maior = None
    for horarios in grupos.values():
        horarios.sort()
        for (prev_a, prog_a), (prev_b, prog_b) in zip(horarios, horarios[1:]):
            if prog_b - prog_a > limite_programado:
                continue
            gap = prev_b - prev_a
            if maior is None or gap > maior:
                maior = gap
    return maior


def classificar(atraso: float, intervalo: int | None, r: Regras) -> tuple[str, str]:
    inter = intervalo or 0
    if atraso > r.atraso_critico_min or inter > r.intervalo_critico_min:
        motivo = (f"atraso médio {atraso:.1f} min > {r.atraso_critico_min:g}"
                  if atraso > r.atraso_critico_min else
                  f"intervalo de {inter} min > {r.intervalo_critico_min:g}")
        return CRITICA, motivo
    if atraso > r.atraso_atencao_min or inter > r.intervalo_atencao_min:
        motivo = (f"atraso médio {atraso:.1f} min > {r.atraso_atencao_min:g}"
                  if atraso > r.atraso_atencao_min else
                  f"intervalo de {inter} min > {r.intervalo_atencao_min:g}")
        return ATENCAO, motivo
    return OK, "dentro dos limites"


def avaliar_linhas(validos: list[Passagem], linhas_monitoradas: list[str], regras: Regras) -> list[SituacaoLinha]:
    por_linha: dict[str, list[Passagem]] = defaultdict(list)
    for p in validos:
        por_linha[p.linha].append(p)

    alvo = linhas_monitoradas or sorted(por_linha)
    situacoes = []
    for linha in alvo:                                  # repetição: uma decisão por linha
        ps = por_linha.get(linha, [])
        if len(ps) < regras.minimo_passagens:
            situacoes.append(SituacaoLinha(linha, SEM_DADOS, None, None, len(ps), None,
                                           sorted({p.fonte for p in ps}),
                                           f"só {len(ps)} passagem(ns) válida(s); mínimo {regras.minimo_passagens}"))
            continue
        atraso = round(sum(max(0, p.atraso_min) for p in ps) / len(ps), 1)
        intervalo = _intervalo_maximo(ps, regras.intervalo_critico_min)
        status, motivo = classificar(atraso, intervalo, regras)   # condição de decisão
        acess = round(100 * sum(p.acessivel for p in ps) / len(ps), 1)
        situacoes.append(SituacaoLinha(linha, status, atraso, intervalo, len(ps), acess,
                                       sorted({p.fonte for p in ps}), motivo))
    situacoes.sort(key=lambda s: (ORDEM[s.status], -(s.atraso_medio_min or 0), s.linha))
    return situacoes

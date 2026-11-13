"""Boletim ESTIMADO: validação das amostras reais de previsão e decisão por linha.

Por que "estimado" e não "atraso":
- A Olho Vivo da SPTrans informa PREVISÕES (quando cada ônibus deve chegar ao ponto), não chegadas observadas.
- O GTFS da SPTrans descreve a maior parte das linhas por frequência, sem horário de cada viagem.
Logo, atraso em relação à tabela não é medível com confiança. O que dá para medir com dado real é a ESPERA PREVISTA:
em cada consulta a um ponto, quanto tempo falta para o próximo ônibus de cada linha e qual o maior intervalo previsto
entre ônibus consecutivos. Somando as consultas do dia, o robô estima como foi a espera em cada linha.

Métricas por linha (somente nos pontos em que a linha apareceu ao menos uma vez no dia):
- amostras: consultas válidas a esses pontos; amostras_com_previsao: consultas em que a linha tinha ônibus previsto.
- espera prevista de uma consulta = maior valor entre (minutos até o 1º ônibus) e (intervalos entre ônibus seguintes).
- espera_tipica_min = mediana das esperas previstas; maior_espera_prevista_min = máximo.
- proximo_onibus_mediana_min = mediana dos minutos até o próximo ônibus.
- sem_previsao_pct = % das consultas em que nenhum ônibus da linha estava previsto.

Decisão (limites em config/monitoramento.yaml, seção regras_estimadas):
SEM_DADOS se amostras_com_previsao < minimo_amostras (não decide no escuro)
CRITICA   se espera_tipica > espera_critica
ATENCAO   se espera_tipica > espera_atencao OU maior espera > espera_critica OU sem_previsao_pct >= limite
OK        caso contrário
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from statistics import median
from typing import Any
from zoneinfo import ZoneInfo

from .config import RegrasEstimadas
from .decisao import ATENCAO, CRITICA, OK, ORDEM, SEM_DADOS

FUSO = ZoneInfo("America/Sao_Paulo")
_HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


@dataclass
class OnibusPrevisto:
    linha: str
    sentido: str
    minutos: int
    veiculo: str | None
    acessivel: bool | None


@dataclass
class Amostra:
    ponto: str
    consultado_em: datetime
    onibus: list[OnibusPrevisto]


@dataclass
class ResultadoAmostras:
    validas: list[Amostra] = field(default_factory=list)
    invalidas: list[dict[str, Any]] = field(default_factory=list)   # {"indice", "motivo"}
    duplicadas: int = 0
    fora_periodo: int = 0
    fora_escopo: int = 0
    onibus_descartados: int = 0

    def contagem_motivos(self) -> dict[str, int]:
        cont: dict[str, int] = {}
        for item in self.invalidas:
            cont[item["motivo"]] = cont.get(item["motivo"], 0) + 1
        return dict(sorted(cont.items()))


def _motivo_amostra(reg: Any) -> str | None:
    if not isinstance(reg, dict):
        return "formato_invalido"
    fonte = reg.get("fonte")
    if fonte in ("simulador", "SIMULADO"):
        return "fonte_simulada"
    if fonte != "olhovivo":
        return "fonte_desconhecida"
    if reg.get("tipo_registro") != "AMOSTRA_PREVISAO":
        return "tipo_inesperado"
    if reg.get("ponto") in (None, ""):
        return "campo_vazio"
    if not isinstance(reg.get("onibus"), list):
        return "formato_invalido"
    try:
        quando = datetime.fromisoformat(str(reg.get("consultado_em")))
    except ValueError:
        return "consultado_em_invalido"
    if quando.tzinfo is None:
        return "consultado_em_sem_fuso"
    return None


def _onibus(o: Any, regras: RegrasEstimadas) -> OnibusPrevisto | None:
    if not isinstance(o, dict):
        return None
    linha = o.get("linha") or o.get("letreiro")
    minutos = o.get("minutos")
    if not isinstance(linha, str) or not linha or isinstance(minutos, bool) or not isinstance(minutos, int):
        return None
    if minutos < 0 or minutos > regras.minutos_max_previsao:
        return None
    if not _HHMM.match(str(o.get("previsto_em", ""))):
        return None
    acessivel = o.get("acessivel")
    return OnibusPrevisto(linha, str(o.get("sentido", "")), minutos, o.get("veiculo") or None,
                          acessivel if isinstance(acessivel, bool) else None)


def validar_amostras(registros: list[Any], data_ref: str, regras: RegrasEstimadas,
                     pontos_monitorados: list[str]) -> ResultadoAmostras:
    res = ResultadoAmostras()
    vistos: set[tuple[str, str]] = set()
    for i, reg in enumerate(registros):                 # repetição sobre cada amostra
        motivo = _motivo_amostra(reg)
        if motivo:
            res.invalidas.append({"indice": i, "motivo": motivo})
            continue
        quando = datetime.fromisoformat(str(reg["consultado_em"])).astimezone(FUSO)
        if quando.date().isoformat() != data_ref:
            res.fora_periodo += 1
            continue
        ponto = str(reg["ponto"])
        if pontos_monitorados and ponto not in pontos_monitorados:
            res.fora_escopo += 1
            continue
        chave = (ponto, quando.strftime("%Y-%m-%dT%H:%M"))
        if chave in vistos:                               # mesmo ponto, mesmo minuto
            res.duplicadas += 1
            continue
        vistos.add(chave)
        onibus: list[OnibusPrevisto] = []
        veiculos: set[tuple[str, str]] = set()
        for o in reg["onibus"]:                           # repetição sobre cada ônibus previsto
            b = _onibus(o, regras)
            if b is None:
                res.onibus_descartados += 1
                continue
            if b.veiculo and (b.linha, b.veiculo) in veiculos:
                continue                                  # mesmo veículo listado duas vezes
            if b.veiculo:
                veiculos.add((b.linha, b.veiculo))
            onibus.append(b)
        if reg["onibus"] and not onibus:
            res.invalidas.append({"indice": i, "motivo": "onibus_invalidos"})
            continue
        res.validas.append(Amostra(ponto, quando, onibus))
    res.validas.sort(key=lambda a: (a.consultado_em, a.ponto))
    return res


@dataclass
class SituacaoEstimada:
    linha: str
    status: str
    amostras: int
    amostras_com_previsao: int
    espera_tipica_min: float | None
    maior_espera_prevista_min: int | None
    proximo_onibus_mediana_min: float | None
    sem_previsao_pct: float | None
    acessiveis_pct: float | None
    pontos: list[str]
    motivo: str


def _espera_prevista(minutos: list[int]) -> int:
    """Maior espera prevista numa consulta: até o 1º ônibus ou entre dois ônibus seguidos (só no horizonte visto)."""
    minutos = sorted(minutos)
    return max([minutos[0]] + [b - a for a, b in zip(minutos, minutos[1:])])


def classificar_estimada(tipica: float, maior: int, sem_pct: float, r: RegrasEstimadas) -> tuple[str, str]:
    if tipica > r.espera_critica_min:
        return CRITICA, f"espera típica prevista de {tipica:g} min > {r.espera_critica_min:g}"
    if tipica > r.espera_atencao_min:
        return ATENCAO, f"espera típica prevista de {tipica:g} min > {r.espera_atencao_min:g}"
    if maior > r.espera_critica_min:
        return ATENCAO, f"maior espera prevista de {maior} min > {r.espera_critica_min:g}"
    if sem_pct >= r.sem_previsao_atencao_pct:
        return ATENCAO, f"sem ônibus previsto em {sem_pct:g}% das consultas"
    return OK, "dentro dos limites"


def avaliar_linhas_estimadas(amostras: list[Amostra], linhas_monitoradas: list[str],
                             r: RegrasEstimadas) -> tuple[list[SituacaoEstimada], int]:
    """Devolve as situações por linha e quantas linhas ficaram de fora por ter poucas amostras."""
    por_ponto: dict[str, list[Amostra]] = defaultdict(list)
    for a in amostras:
        por_ponto[a.ponto].append(a)
    pontos_da_linha: dict[str, set[str]] = defaultdict(set)
    for a in amostras:
        for b in a.onibus:
            pontos_da_linha[b.linha].add(a.ponto)

    alvo = linhas_monitoradas or sorted(pontos_da_linha)
    situacoes: list[SituacaoEstimada] = []
    poucas = 0
    for linha in alvo:                                    # repetição: uma decisão por linha
        pontos = sorted(pontos_da_linha.get(linha, set()))
        esperas: list[int] = []
        proximos: list[int] = []
        consultas = sem = acessiveis = acessibilidade_informada = 0
        for p in pontos:
            for a in por_ponto[p]:
                consultas += 1
                minutos = [b.minutos for b in a.onibus if b.linha == linha]
                if not minutos:
                    sem += 1
                    continue
                por_sentido: dict[str, list[int]] = defaultdict(list)
                for b in a.onibus:
                    if b.linha == linha:
                        por_sentido[b.sentido].append(b.minutos)
                # Um ônibus no sentido contrário não preenche a espera desta direção.
                esperas.append(max(_espera_prevista(ms) for ms in por_sentido.values()))
                proximos.append(min(minutos))
                for b in a.onibus:
                    if b.linha == linha:
                        if b.acessivel is not None:
                            acessibilidade_informada += 1
                            acessiveis += b.acessivel
        com = len(esperas)
        sem_pct = round(100 * sem / consultas, 1) if consultas else None
        if com < r.minimo_amostras:
            if not linhas_monitoradas:
                poucas += 1
                continue
            situacoes.append(SituacaoEstimada(
                linha, SEM_DADOS, consultas, com, None, None, None, sem_pct, None, pontos,
                f"só {com} consulta(s) com previsão da linha; mínimo {r.minimo_amostras}"))
            continue
        tipica = round(float(median(esperas)), 1)
        maior = max(esperas)
        status, motivo = classificar_estimada(tipica, maior, sem_pct or 0.0, r)   # condição de decisão
        situacoes.append(SituacaoEstimada(
            linha, status, consultas, com, tipica, maior, round(float(median(proximos)), 1), sem_pct,
            round(100 * acessiveis / acessibilidade_informada, 1) if acessibilidade_informada else None,
            pontos, motivo))
    situacoes.sort(key=lambda s: (ORDEM[s.status], -(s.espera_tipica_min or 0), s.linha))
    return situacoes, poucas

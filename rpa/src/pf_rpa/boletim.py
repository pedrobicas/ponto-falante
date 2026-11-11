"""Monta o boletim diário (etapa 5): JSON para o MVP + HTML simples.

As frases são curtas e sem siglas, porque a tela do MVP lê o boletim em voz
alta para pessoas com baixa visão.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from jinja2 import Environment, select_autoescape

from .config import Regras
from .decisao import ATENCAO, CRITICA, OK, SEM_DADOS, SituacaoLinha
from .validacao import ResultadoValidacao

MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
         "agosto", "setembro", "outubro", "novembro", "dezembro"]
ROTULO = {CRITICA: "Atraso forte", ATENCAO: "Atenção", OK: "Normal", SEM_DADOS: "Sem dados suficientes"}


def data_por_extenso(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d.day} de {MESES[d.month - 1]}"


def _min(valor: float) -> str:
    n = round(valor)
    return "1 minuto" if n == 1 else f"{n} minutos"


def frase_linha(s: SituacaoLinha) -> str:
    por_intervalo = s.motivo.startswith("intervalo")
    if s.status in (CRITICA, ATENCAO) and por_intervalo:
        intensidade = "esperas muito longas" if s.status == CRITICA else "esperas mais longas que o normal"
        return (f"Linha {s.linha}: {intensidade} entre um ônibus e outro, "
                f"de até {_min(s.intervalo_max_min or 0)}.")
    if s.status == CRITICA:
        return (f"Linha {s.linha}: atrasos fortes, em média {_min(s.atraso_medio_min)}; "
                f"maior espera entre ônibus de {_min(s.intervalo_max_min or 0)}.")
    if s.status == ATENCAO:
        return (f"Linha {s.linha}: alguns atrasos, em média {_min(s.atraso_medio_min)}; "
                f"maior espera de {_min(s.intervalo_max_min or 0)}.")
    if s.status == OK:
        return f"Linha {s.linha}: funcionando normalmente."
    return f"Linha {s.linha}: não recebemos dados suficientes para avaliar."


def resumo_falado(data_ref: str, situacoes: list[SituacaoLinha], desatualizado: bool) -> str:
    n_crit = sum(s.status == CRITICA for s in situacoes)
    n_aten = sum(s.status == ATENCAO for s in situacoes)
    partes = [f"Boletim de {data_por_extenso(data_ref)}."]
    if desatualizado:
        partes.append("Atenção: este boletim está desatualizado.")
    if n_crit == 0 and n_aten == 0:
        partes.append("Nenhuma linha monitorada com atraso relevante.")
    else:
        if n_crit:
            partes.append(f"{n_crit} {'linha' if n_crit == 1 else 'linhas'} com atraso forte.")
        if n_aten:
            partes.append(f"{n_aten} {'linha' if n_aten == 1 else 'linhas'} pedindo atenção.")
    for s in situacoes:
        if s.status in (CRITICA, ATENCAO):
            partes.append(frase_linha(s))
    return " ".join(partes)


def montar(data_ref: str, situacoes: list[SituacaoLinha], val: ResultadoValidacao,
           recebidos: int, regras: Regras, origem_rede: str, avisos: list[str],
           agora: datetime) -> dict[str, Any]:
    fontes: dict[str, int] = {"olhovivo": 0, "simulador": 0}
    for p in val.validos:
        fontes[p.fonte] = fontes.get(p.fonte, 0) + 1
    boletim = {
        "data_referencia": data_ref,
        "gerado_em": agora.isoformat(timespec="seconds"),
        "desatualizado": False,
        "motivo_desatualizado": None,
        "fonte_dados": fontes,
        "dados_simulados": fontes.get("simulador", 0) > 0,
        "rede": origem_rede,
        "parametros": {
            "atraso_critico_min": regras.atraso_critico_min,
            "atraso_atencao_min": regras.atraso_atencao_min,
            "intervalo_critico_min": regras.intervalo_critico_min,
            "intervalo_atencao_min": regras.intervalo_atencao_min,
        },
        "estatisticas": {
            "recebidos": recebidos,
            "validos": len(val.validos),
            "invalidos": len(val.invalidos),
            "duplicados": val.duplicados,
            "fora_escopo": val.fora_escopo,
        },
        "invalidos_por_motivo": val.contagem_motivos(),
        "linhas": [
            {
                "linha": s.linha, "status": s.status, "rotulo": ROTULO[s.status],
                "atraso_medio_min": s.atraso_medio_min, "intervalo_max_min": s.intervalo_max_min,
                "passagens": s.passagens, "acessiveis_pct": s.acessiveis_pct,
                "fontes": s.fontes, "motivo": s.motivo, "frase": frase_linha(s),
            }
            for s in situacoes
        ],
        "avisos": avisos,
        "revisao_humana": "Linhas marcadas como atraso forte devem ser conferidas pela equipe da gestora antes de qualquer ação.",
    }
    boletim["resumo_falado"] = resumo_falado(data_ref, situacoes, False)
    boletim["html"] = renderizar_html(boletim)
    return boletim


def marcar_desatualizado(boletim: dict[str, Any], motivo: str, agora: datetime) -> dict[str, Any]:
    """Republica o último boletim conhecido, deixando claro que está velho."""
    b = dict(boletim)
    b["desatualizado"] = True
    b["motivo_desatualizado"] = motivo
    b["marcado_desatualizado_em"] = agora.isoformat(timespec="seconds")
    resumo = b.get("resumo_falado", "")
    if "desatualizado" not in resumo:
        b["resumo_falado"] = ("Atenção: este boletim está desatualizado, pois não conseguimos obter "
                              "os dados mais recentes. " + resumo)
    b["html"] = renderizar_html(b)
    return b


def boletim_vazio_desatualizado(data_ref: str, motivo: str, agora: datetime) -> dict[str, Any]:
    """Quando não há nenhum boletim anterior: publica um aviso honesto em vez de nada."""
    b = {
        "data_referencia": data_ref, "gerado_em": agora.isoformat(timespec="seconds"),
        "desatualizado": True, "motivo_desatualizado": motivo,
        "fonte_dados": {"olhovivo": 0, "simulador": 0}, "dados_simulados": False,
        "rede": None, "parametros": {}, "estatisticas": {}, "invalidos_por_motivo": {},
        "linhas": [], "avisos": [motivo],
        "resumo_falado": "Boletim de atrasos indisponível no momento. Tente mais tarde.",
    }
    b["html"] = renderizar_html(b)
    return b


_env = Environment(autoescape=select_autoescape(default=True), trim_blocks=True, lstrip_blocks=True)
_TEMPLATE = _env.from_string("""<section class="boletim" lang="pt-BR" aria-labelledby="titulo-boletim">
  <h2 id="titulo-boletim">Boletim de atrasos: {{ data_extenso }}</h2>
  {% if b.desatualizado %}
  <p class="aviso" role="alert"><strong>Desatualizado.</strong> {{ b.motivo_desatualizado }}</p>
  {% endif %}
  <p class="resumo">{{ b.resumo_falado }}</p>
  {% if b.linhas %}
  <ul class="linhas">
    {% for l in b.linhas %}
    <li class="status-{{ l.status|lower }}"><strong>{{ l.rotulo }}</strong>: {{ l.frase }}</li>
    {% endfor %}
  </ul>
  {% endif %}
  <p class="origem">Origem dos dados:
    {% if b.fonte_dados.olhovivo %}{{ b.fonte_dados.olhovivo }} registros em tempo real da SPTrans{% endif %}
    {% if b.fonte_dados.olhovivo and b.fonte_dados.simulador %} e {% endif %}
    {% if b.fonte_dados.simulador %}{{ b.fonte_dados.simulador }} registros simulados{% endif %}
    {% if not b.fonte_dados.olhovivo and not b.fonte_dados.simulador %}nenhum registro{% endif %}.
  </p>
  <p class="geracao">Gerado automaticamente em {{ b.gerado_em }}. {{ b.revisao_humana or "" }}</p>
</section>""")


def renderizar_html(b: dict[str, Any]) -> str:
    return _TEMPLATE.render(b=b, data_extenso=data_por_extenso(b["data_referencia"]))

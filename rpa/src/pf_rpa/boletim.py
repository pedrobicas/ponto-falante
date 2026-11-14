"""Monta o boletim diário: JSON para o MVP + HTML simples.

Três naturezas, nunca misturadas no mesmo boletim (campo natureza_dados):
- ESTIMADO: calculado a partir de amostras REAIS de previsão da SPTrans. Mostra espera prevista, nunca atraso.
- SIMULADO: histórico de demonstração (rede fictícia), só quando o MVP está em modo demonstração.
- INDISPONIVEL: não há dado suficiente; o boletim diz isso em vez de inventar.
O bloco "amostragem" traz os fatos VERIFICADOS (quantas consultas reais, em que horário, em quais pontos).

As frases são curtas e sem siglas, porque a tela do MVP lê o boletim em voz alta.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from jinja2 import Environment, select_autoescape

from .config import Regras, RegrasEstimadas
from .decisao import ATENCAO, CRITICA, OK, SEM_DADOS, SituacaoLinha
from .estimativa import ResultadoAmostras, SituacaoEstimada
from .validacao import ResultadoValidacao

MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
         "agosto", "setembro", "outubro", "novembro", "dezembro"]
ROTULO = {CRITICA: "Atraso forte (simulado)", ATENCAO: "Atenção (simulado)", OK: "Normal (simulado)",
          SEM_DADOS: "Sem dados suficientes"}
ROTULO_ESTIMADO = {CRITICA: "Espera longa (estimada)", ATENCAO: "Espera acima do normal (estimada)",
                   OK: "Espera normal (estimada)", SEM_DADOS: "Sem dados suficientes"}
METODO_ESTIMADO = ("Estimado a partir das previsões da SPTrans (Olho Vivo), consultadas automaticamente pelo robô "
                   "nos pontos monitorados ao longo do dia. Uma previsão não é chegada nem prova de atraso: "
                   "o boletim mostra a espera prevista entre ônibus, não atrasos medidos.")
METODO_SIMULADO = ("Dados SIMULADOS de demonstração (rede fictícia), usados só porque o MVP está em modo "
                   "demonstração e não há amostras reais. Não representam a operação real.")
REVISAO_HUMANA = ("Linhas com espera longa devem ser conferidas pela equipe da gestora antes de qualquer ação; "
                  "o boletim sinaliza, não comprova.")


def data_por_extenso(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d.day} de {MESES[d.month - 1]}"


def _min(valor: float) -> str:
    n = round(valor)
    return "1 minuto" if n == 1 else f"{n} minutos"


def _hora_falada(hhmm: str) -> str:
    h, m = hhmm.split(":")
    return f"{int(h)} horas" if m == "00" else f"{int(h)} horas e {int(m)}"


# ---------------------------------------------------------------------------
# SIMULADO (histórico de demonstração)
# ---------------------------------------------------------------------------
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
    partes = [f"Boletim de {data_por_extenso(data_ref)}, com dados simulados de demonstração."]
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
    """Boletim SIMULADO a partir do histórico de demonstração."""
    fontes: dict[str, int] = {"olhovivo": 0, "simulador": 0}
    for p in val.validos:
        fontes[p.fonte] = fontes.get(p.fonte, 0) + 1
    simulado = fontes.get("simulador", 0) > 0
    natureza = "SIMULADO" if simulado else ("INDISPONIVEL" if not fontes.get("olhovivo") else None)

    def classificacao(s: SituacaoLinha) -> str | None:
        if s.status == SEM_DADOS:
            return "INDISPONIVEL"
        return "SIMULADO" if "simulador" in s.fontes else None

    boletim = {
        "data_referencia": data_ref,
        "gerado_em": agora.isoformat(timespec="seconds"),
        "desatualizado": False,
        "motivo_desatualizado": None,
        "natureza_dados": natureza,
        "metodo": METODO_SIMULADO if simulado else None,
        "periodo_referencia": {"data": data_ref, "inicio": None, "fim": None, "fuso": "America/Sao_Paulo"},
        "ultima_atualizacao": agora.isoformat(timespec="seconds"),
        "fonte_dados": fontes,
        "dados_simulados": simulado,
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
                "classificacao": classificacao(s),
                "atraso_medio_min": s.atraso_medio_min, "intervalo_max_min": s.intervalo_max_min,
                "passagens": s.passagens, "acessiveis_pct": s.acessiveis_pct,
                "fontes": s.fontes, "motivo": s.motivo, "frase": frase_linha(s),
            }
            for s in situacoes
        ],
        "avisos": avisos,
        "revisao_humana": REVISAO_HUMANA,
    }
    if natureza is None:   # dado antigo do histórico com fonte olhovivo: sem categoria nova
        del boletim["natureza_dados"]
    boletim["resumo_falado"] = resumo_falado(data_ref, situacoes, False)
    boletim["html"] = renderizar_html(boletim)
    return boletim


# ---------------------------------------------------------------------------
# ESTIMADO (amostras reais de previsão)
# ---------------------------------------------------------------------------
def frase_estimada(s: SituacaoEstimada) -> str:
    if s.status == SEM_DADOS:
        return f"Linha {s.linha}: não há consultas suficientes para estimar a espera."
    if s.status == CRITICA:
        return (f"Linha {s.linha}: espera longa prevista, em geral de até {_min(s.espera_tipica_min or 0)} "
                f"entre um ônibus e outro.")
    if s.status == ATENCAO:
        if s.motivo.startswith("espera típica"):
            return (f"Linha {s.linha}: espera prevista acima do normal, em geral de até "
                    f"{_min(s.espera_tipica_min or 0)} entre um ônibus e outro.")
        if s.motivo.startswith("maior espera"):
            return (f"Linha {s.linha}: em pelo menos uma consulta, a previsão mostrava espera de "
                    f"{_min(s.maior_espera_prevista_min or 0)}.")
        return (f"Linha {s.linha}: em {round(s.sem_previsao_pct or 0)} por cento das consultas, "
                f"nenhum ônibus da linha estava previsto.")
    return (f"Linha {s.linha}: espera prevista dentro do normal, em geral de até "
            f"{_min(s.espera_tipica_min or 0)}.")


def _resumo_estimado(data_ref: str, situacoes: list[SituacaoEstimada], consultas: int,
                     inicio: str, fim: str, parcial: bool) -> str:
    quando = f"às {_hora_falada(inicio)}" if inicio == fim else f"entre {_hora_falada(inicio)} e {_hora_falada(fim)}"
    consultas_txt = "1 consulta" if consultas == 1 else f"{consultas} consultas"
    partes = [f"Boletim de {data_por_extenso(data_ref)}, estimado a partir de {consultas_txt} às "
              f"previsões da SPTrans, {quando}.",
              "São estimativas de espera, não atrasos medidos."]
    if parcial:
        partes.append("A coleta do dia foi parcial; trate o resultado com cautela.")
    n_crit = sum(s.status == CRITICA for s in situacoes)
    n_aten = sum(s.status == ATENCAO for s in situacoes)
    n_ok = sum(s.status == OK for s in situacoes)
    if not n_crit and not n_aten:
        partes.append(f"Nenhuma das {n_ok} linhas avaliadas teve espera prevista acima do normal."
                      if n_ok else "Nenhuma linha teve consultas suficientes para avaliar.")
    else:
        if n_crit:
            partes.append(f"{n_crit} {'linha' if n_crit == 1 else 'linhas'} com espera longa prevista.")
        if n_aten:
            partes.append(f"{n_aten} {'linha' if n_aten == 1 else 'linhas'} com espera acima do normal.")
        for s in situacoes:
            if s.status in (CRITICA, ATENCAO):
                partes.append(frase_estimada(s))
    return " ".join(partes)


def montar_estimado(data_ref: str, situacoes: list[SituacaoEstimada], val: ResultadoAmostras, recebidas: int,
                    linhas_poucas: int, regras: RegrasEstimadas, pontos_monitorados: list[str],
                    execucoes_por_dia: int, avisos: list[str], agora: datetime) -> dict[str, Any]:
    validas = val.validas
    inicio = validas[0].consultado_em.strftime("%H:%M")
    fim = validas[-1].consultado_em.strftime("%H:%M")
    esperadas = len(pontos_monitorados) * execucoes_por_dia if pontos_monitorados else None
    # Uma consulta cobre uma janela de duas horas de um ponto. Reexecuções
    # manuais não substituem horários/pontos que não foram observados.
    janelas = {(a.ponto, (a.consultado_em.hour - 7) // 2) for a in validas
               if a.ponto in pontos_monitorados and 7 <= a.consultado_em.hour < 7 + 2 * execucoes_por_dia}
    cobertura = round(100 * len(janelas) / esperadas, 1) if esperadas else None
    parcial = cobertura is not None and cobertura < regras.cobertura_minima_pct
    avisos = list(avisos)
    if parcial:
        avisos.append(f"Amostragem parcial: {len(janelas)} de {esperadas} janelas de coleta cobertas ({cobertura}%).")
    tem_estimativa = any(s.status != SEM_DADOS for s in situacoes)
    boletim = {
        "data_referencia": data_ref,
        "gerado_em": agora.isoformat(timespec="seconds"),
        "desatualizado": False,
        "motivo_desatualizado": None,
        "natureza_dados": "ESTIMADO" if tem_estimativa else "INDISPONIVEL",
        "metodo": METODO_ESTIMADO,
        "periodo_referencia": {"data": data_ref, "inicio": inicio, "fim": fim, "fuso": "America/Sao_Paulo"},
        "ultima_atualizacao": validas[-1].consultado_em.isoformat(timespec="seconds"),
        "fonte_dados": {"olhovivo": len(validas), "simulador": 0},
        "dados_simulados": False,
        "rede": "sptrans_olhovivo",
        "amostragem": {
            "classificacao": "VERIFICADO",
            "descricao": "Fatos conferidos: consultas reais às previsões da SPTrans feitas pelo robô.",
            "pontos_monitorados": pontos_monitorados,
            "pontos_com_amostra": sorted({a.ponto for a in validas}),
            "consultas_validas": len(validas),
            "consultas_esperadas": esperadas,
            "janelas_cobertas": len(janelas),
            "criterio_cobertura": "Uma janela por ponto a cada duas horas, a partir das 07h de São Paulo.",
            "cobertura_pct": cobertura,
            "primeira_consulta": validas[0].consultado_em.isoformat(timespec="seconds"),
            "ultima_consulta": validas[-1].consultado_em.isoformat(timespec="seconds"),
            "onibus_previstos": sum(len(a.onibus) for a in validas),
        },
        "parametros": {
            "espera_critica_min": regras.espera_critica_min,
            "espera_atencao_min": regras.espera_atencao_min,
            "sem_previsao_atencao_pct": regras.sem_previsao_atencao_pct,
            "minimo_amostras": regras.minimo_amostras,
        },
        "estatisticas": {
            "recebidos": recebidas,
            "validos": len(validas),
            "invalidos": len(val.invalidas),
            "duplicados": val.duplicadas,
            "fora_escopo": val.fora_escopo,
            "fora_periodo": val.fora_periodo,
            "onibus_descartados": val.onibus_descartados,
            "linhas_avaliadas": sum(s.status != SEM_DADOS for s in situacoes),
            "linhas_poucas_amostras": linhas_poucas,
        },
        "invalidos_por_motivo": val.contagem_motivos(),
        "linhas": [
            {
                "linha": s.linha, "status": s.status, "rotulo": ROTULO_ESTIMADO[s.status],
                "classificacao": "INDISPONIVEL" if s.status == SEM_DADOS else "ESTIMADO",
                "atraso_medio_min": None,               # previsão não mede atraso
                "intervalo_max_min": s.maior_espera_prevista_min,
                "espera_tipica_min": s.espera_tipica_min,
                "maior_espera_prevista_min": s.maior_espera_prevista_min,
                "proximo_onibus_mediana_min": s.proximo_onibus_mediana_min,
                "sem_previsao_pct": s.sem_previsao_pct,
                "amostras": s.amostras, "amostras_com_previsao": s.amostras_com_previsao,
                "pontos": s.pontos, "acessiveis_pct": s.acessiveis_pct,
                "fontes": ["olhovivo"] if s.amostras_com_previsao else [],
                "motivo": s.motivo, "frase": frase_estimada(s),
            }
            for s in situacoes
        ],
        "avisos": avisos,
        "revisao_humana": REVISAO_HUMANA,
    }
    boletim["resumo_falado"] = _resumo_estimado(data_ref, situacoes, len(validas), inicio, fim, parcial)
    if not tem_estimativa:
        boletim['resumo_falado'] = (f"Boletim de {data_por_extenso(data_ref)} indisponível: "
                                   f"foram feitas {len(validas)} consultas reais à SPTrans, mas os dados são "
                                   "insuficientes para estimar a espera nas linhas monitoradas.")
    boletim["html"] = renderizar_html(boletim)
    return boletim


# ---------------------------------------------------------------------------
# INDISPONIVEL e desatualizado
# ---------------------------------------------------------------------------
def montar_indisponivel(data_ref: str, motivo: str, linhas: list[str], val: ResultadoAmostras | None,
                        recebidas: int, avisos: list[str], agora: datetime) -> dict[str, Any]:
    """Dia sem amostras reais e sem permissão para simular: diz que não sabe, em vez de inventar."""
    b = {
        "data_referencia": data_ref, "gerado_em": agora.isoformat(timespec="seconds"),
        "desatualizado": False, "motivo_desatualizado": None,
        "natureza_dados": "INDISPONIVEL",
        "metodo": METODO_ESTIMADO,
        "periodo_referencia": {"data": data_ref, "inicio": None, "fim": None, "fuso": "America/Sao_Paulo"},
        "ultima_atualizacao": None,
        "fonte_dados": {"olhovivo": 0, "simulador": 0}, "dados_simulados": False,
        "rede": "sptrans_olhovivo", "parametros": {},
        "estatisticas": {
            "recebidos": recebidas, "validos": 0,
            "invalidos": len(val.invalidas) if val else 0,
            "duplicados": val.duplicadas if val else 0,
            "fora_escopo": val.fora_escopo if val else 0,
            "fora_periodo": val.fora_periodo if val else 0,
        },
        "invalidos_por_motivo": val.contagem_motivos() if val else {},
        "linhas": [
            {"linha": l, "status": SEM_DADOS, "rotulo": ROTULO_ESTIMADO[SEM_DADOS], "classificacao": "INDISPONIVEL",
             "atraso_medio_min": None, "intervalo_max_min": None, "amostras": 0, "amostras_com_previsao": 0,
             "fontes": [], "motivo": motivo, "frase": f"Linha {l}: sem dados reais nesta data."}
            for l in linhas
        ],
        "avisos": [motivo, *avisos],
        "revisao_humana": REVISAO_HUMANA,
        "resumo_falado": (f"Boletim de {data_por_extenso(data_ref)} indisponível: não há dados reais suficientes "
                          f"desta data para estimar a espera dos ônibus."),
    }
    b["html"] = renderizar_html(b)
    return b


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
        "natureza_dados": "INDISPONIVEL",
        "periodo_referencia": {"data": data_ref, "inicio": None, "fim": None, "fuso": "America/Sao_Paulo"},
        "ultima_atualizacao": None,
        "fonte_dados": {"olhovivo": 0, "simulador": 0}, "dados_simulados": False,
        "rede": None, "parametros": {}, "estatisticas": {}, "invalidos_por_motivo": {},
        "linhas": [], "avisos": [motivo],
        "resumo_falado": "Boletim de atrasos indisponível no momento. Tente mais tarde.",
    }
    b["html"] = renderizar_html(b)
    return b


# autoescape ativo para todo template (default=True); a regra abaixo não se aplica.
_env = Environment(  # nosemgrep: python.flask.security.xss.audit.direct-use-of-jinja2.direct-use-of-jinja2
    autoescape=select_autoescape(default=True), trim_blocks=True, lstrip_blocks=True)
_TEMPLATE = _env.from_string("""<section class="boletim" lang="pt-BR" aria-labelledby="titulo-boletim">
  <h2 id="titulo-boletim">Boletim do ônibus: {{ data_extenso }}</h2>
  {% if b.natureza_dados %}
  <p class="natureza natureza-{{ b.natureza_dados|lower }}"><strong>{{ natureza }}</strong></p>
  {% endif %}
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
  {% if b.avisos %}
  <ul class="avisos">{% for a in b.avisos %}<li>{{ a }}</li>{% endfor %}</ul>
  {% endif %}
  <p class="origem">Origem dos dados:
    {% if b.fonte_dados.olhovivo %}{{ b.fonte_dados.olhovivo }} consultas reais às previsões da SPTrans{% endif %}
    {% if b.fonte_dados.olhovivo and b.fonte_dados.simulador %} e {% endif %}
    {% if b.fonte_dados.simulador %}{{ b.fonte_dados.simulador }} registros simulados{% endif %}
    {% if not b.fonte_dados.olhovivo and not b.fonte_dados.simulador %}nenhum registro{% endif %}.
    {% if b.periodo_referencia and b.periodo_referencia.inicio %}
    Período: {{ b.periodo_referencia.inicio }} a {{ b.periodo_referencia.fim }}.
    {% endif %}
    {% if b.metodo %}{{ b.metodo }}{% endif %}
  </p>
  <p class="geracao">Gerado automaticamente em {{ b.gerado_em }}. {{ b.revisao_humana or "" }}</p>
</section>""")
NATUREZA_TEXTO = {"ESTIMADO": "Estimado a partir de dados reais", "SIMULADO": "Dados simulados de demonstração",
                  "INDISPONIVEL": "Dados indisponíveis"}


def renderizar_html(b: dict[str, Any]) -> str:
    return _TEMPLATE.render(b=b, data_extenso=data_por_extenso(b["data_referencia"]),
                            natureza=NATUREZA_TEXTO.get(b.get("natureza_dados") or "", ""))

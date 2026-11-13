"""Orquestrador do robô do boletim: executa o fluxo de ponta a ponta (ver docs/fluxo.bpmn).

Fonte preferida: amostras REAIS de previsão gravadas pelo coletor (pf_rpa.coletor) -> boletim ESTIMADO.
Sem amostra real: boletim INDISPONIVEL, ou SIMULADO só se o MVP estiver em modo demonstração (configurável).

Uso:
    python -m pf_rpa.robo                 # boletim de ontem
    python -m pf_rpa.robo --data 2026-11-12
    python -m pf_rpa.robo --config config/monitoramento.yaml

Códigos de saída (para o agendador e para auditoria):
    0 sucesso | 1 boletim gerado mas publicação falhou (salvo em saida/)
    2 MVP indisponível (boletim anterior republicado como desatualizado)
    3 erro de configuração ou de rede GTFS
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from . import armazenamento, boletim as bol, registro
from .cliente_mvp import ChaveRecusada, ClienteMVP, MVPIndisponivel, NaoEncontrado, RespostaInvalida
from .config import Config, ErroConfiguracao, carregar
from .decisao import avaliar_linhas
from .estimativa import avaliar_linhas_estimadas, validar_amostras
from .gtfs import GTFSInvalido, carregar_rede
from .validacao import validar

log = logging.getLogger("pf_rpa.robo")
FUSO = ZoneInfo("America/Sao_Paulo")

SUCESSO, PUBLICACAO_FALHOU, MVP_INDISPONIVEL, ERRO_CONFIG = 0, 1, 2, 3


@dataclass
class ResultadoExecucao:
    codigo: int
    status: str
    data_referencia: str
    boletim: dict[str, Any] | None = None
    publicado: bool = False
    erros: list[str] = field(default_factory=list)


def executar(cfg: Config, data_ref: str, cliente: ClienteMVP | None = None,
             agora: datetime | None = None) -> ResultadoExecucao:
    agora = agora or datetime.now(FUSO)
    inicio = time.perf_counter()
    cliente = cliente or ClienteMVP(cfg.mvp_url, cfg.timeout, cfg.tentativas, cfg.backoff_inicial, cfg.api_key)
    log.info("=== Início da execução | data de referência %s | MVP %s ===", data_ref, cfg.mvp_url)

    # 1. Coleta das amostras REAIS do dia (gravadas pelo coletor)
    avisos: list[str] = []
    try:
        amostras = cliente.buscar_amostras(data_ref)
        log.info("Amostras reais recebidas: %d", len(amostras))
    except NaoEncontrado:
        amostras = []
        log.warning("O MVP não tem GET /rpa/amostras (versão antiga do backend); sem amostras reais")
        avisos.append("O MVP ainda não oferece amostras reais de previsão.")
    except (MVPIndisponivel, RespostaInvalida) as e:
        return _fluxo_mvp_indisponivel(cfg, cliente, data_ref, str(e), agora, inicio)

    # 2. Validação + deduplicação das amostras (repetição sobre a coleção)
    val = validar_amostras(amostras, data_ref, cfg.regras_estimadas, cfg.coleta.pontos)
    log.info("Validação das amostras: %d válidas, %d inválidas %s, %d duplicadas, %d fora do período, "
             "%d fora do escopo, %d ônibus descartados", len(val.validas), len(val.invalidas),
             val.contagem_motivos(), val.duplicadas, val.fora_periodo, val.fora_escopo, val.onibus_descartados)
    if amostras and len(val.invalidas) > len(amostras) / 2:
        avisos.append("Mais da metade das amostras veio inconsistente; resultado pouco confiável.")
        log.warning("Amostras inconsistentes: %d de %d inválidas", len(val.invalidas), len(amostras))

    # 3. Decisão: há dado real? (condição principal do fluxo)
    if val.validas:
        situacoes, poucas = avaliar_linhas_estimadas(val.validas, cfg.coleta.linhas, cfg.regras_estimadas)
        for s in situacoes:
            log.info("Linha %s -> %s (ESTIMADO: %s)", s.linha, s.status, s.motivo)
        if poucas:
            log.info("%d linha(s) com menos de %d consultas com previsão ficaram fora do boletim",
                     poucas, cfg.regras_estimadas.minimo_amostras)
        b = bol.montar_estimado(data_ref, situacoes, val, len(amostras), poucas, cfg.regras_estimadas,
                                cfg.coleta.pontos, cfg.coleta.execucoes_por_dia, avisos, agora)
        return _publicar(cfg, cliente, data_ref, b, inicio)

    # 4. Sem dado real: simulação só se permitida (e nunca misturada)
    modo = cliente.modo_sptrans() if cfg.fallback_simulado == "somente_demo" else None
    usar_simulado = cfg.fallback_simulado == "sempre" or (cfg.fallback_simulado == "somente_demo" and modo == "DEMO")
    log.info("Nenhuma amostra real válida para %s | modo do MVP: %s | fallback simulado: %s -> %s",
             data_ref, modo, cfg.fallback_simulado, "usar SIMULADO" if usar_simulado else "INDISPONIVEL")
    if not usar_simulado:
        motivo = "Nenhuma amostra real de previsão foi coletada nesta data."
        b = bol.montar_indisponivel(data_ref, motivo, cfg.coleta.linhas, val, len(amostras), avisos, agora)
        return _publicar(cfg, cliente, data_ref, b, inicio)
    return _fluxo_simulado(cfg, cliente, data_ref, agora, inicio)


def _fluxo_simulado(cfg: Config, cliente: ClienteMVP, data_ref: str, agora: datetime,
                    inicio: float) -> ResultadoExecucao:
    """Histórico SIMULADO de demonstração (rede fictícia). Só roda sem amostras reais e com fallback permitido."""
    try:
        rede = carregar_rede(cfg.gtfs_pasta, cfg.gtfs_pasta_ficticia)
    except GTFSInvalido as e:
        log.error("Nenhuma rede GTFS utilizável: %s", e)
        res = ResultadoExecucao(ERRO_CONFIG, "erro_gtfs", data_ref, erros=[str(e)])
        _auditar(cfg, res, inicio, {})
        return res
    avisos = [rede.aviso] if rede.aviso else []
    avisos.append("Sem amostras reais nesta data e MVP em modo demonstração: boletim com dados SIMULADOS.")
    try:
        registros = cliente.buscar_historico(data_ref)
        log.info("Histórico simulado recebido: %d registros", len(registros))
    except (MVPIndisponivel, RespostaInvalida) as e:
        return _fluxo_mvp_indisponivel(cfg, cliente, data_ref, str(e), agora, inicio)

    val = validar(registros, rede, cfg.regras, cfg.linhas, cfg.pontos)
    log.info("Validação: %d válidos, %d inválidos %s, %d duplicados, %d fora do escopo",
             len(val.validos), len(val.invalidos), val.contagem_motivos(), val.duplicados, val.fora_escopo)
    if not registros:
        avisos.append("O MVP não registrou passagens nesta data.")
        log.warning("Histórico vazio para %s", data_ref)
    elif len(val.invalidos) > len(registros) / 2:
        avisos.append("Mais da metade dos registros veio inconsistente; resultado pouco confiável.")
        log.warning("Dados inconsistentes: %d de %d inválidos", len(val.invalidos), len(registros))

    situacoes = avaliar_linhas(val.validos, cfg.linhas, cfg.regras)
    for s in situacoes:
        log.info("Linha %s -> %s (SIMULADO: %s)", s.linha, s.status, s.motivo)
    b = bol.montar(data_ref, situacoes, val, len(registros), cfg.regras, rede.origem, avisos, agora)
    return _publicar(cfg, cliente, data_ref, b, inicio)


def _publicar(cfg: Config, cliente: ClienteMVP, data_ref: str, b: dict[str, Any],
              inicio: float) -> ResultadoExecucao:
    caminho = armazenamento.salvar(cfg.pasta_saida, b)
    log.info("Boletim %s salvo em %s", b.get("natureza_dados"),
             caminho.relative_to(cfg.base) if caminho.is_relative_to(cfg.base) else caminho)
    try:
        cliente.publicar_boletim(b)
        log.info("Boletim publicado no MVP (POST /boletim)")
        res = ResultadoExecucao(SUCESSO, "sucesso", data_ref, b, publicado=True)
    except ChaveRecusada as e:
        log.error("Chave recusada ao publicar: %s. Cópia local mantida.", e)
        res = ResultadoExecucao(PUBLICACAO_FALHOU, "chave_recusada", data_ref, b, erros=[str(e)])
    except (MVPIndisponivel, RespostaInvalida) as e:
        log.error("Falha ao publicar o boletim: %s. Cópia local mantida.", e)
        res = ResultadoExecucao(PUBLICACAO_FALHOU, "publicacao_falhou", data_ref, b, erros=[str(e)])
    _auditar(cfg, res, inicio, b.get("estatisticas", {}), situacoes=b["linhas"], fontes=b["fonte_dados"],
             natureza=b.get("natureza_dados"))
    return res


def _fluxo_mvp_indisponivel(cfg: Config, cliente: ClienteMVP, data_ref: str, motivo: str,
                            agora: datetime, inicio: float) -> ResultadoExecucao:
    """Exceção principal: sem histórico, mantém o boletim anterior marcado como desatualizado."""
    log.error("MVP indisponível para leitura do histórico: %s", motivo)
    texto = f"Não foi possível ler os dados de {bol.data_por_extenso(data_ref)} no MVP."
    anterior = armazenamento.carregar_ultimo(cfg.pasta_saida)
    if anterior:
        b = bol.marcar_desatualizado(anterior, texto, agora)
        log.warning("Republicando o boletim de %s marcado como desatualizado", anterior.get("data_referencia"))
    else:
        b = bol.boletim_vazio_desatualizado(data_ref, texto, agora)
        log.warning("Sem boletim anterior: gerando aviso de indisponibilidade")
    armazenamento.salvar(cfg.pasta_saida, b)
    publicado = False
    try:
        cliente.publicar_boletim(b)
        publicado = True
        log.info("Boletim desatualizado publicado no MVP")
    except (MVPIndisponivel, RespostaInvalida) as e:
        log.error("Também não foi possível publicar: %s", e)
    res = ResultadoExecucao(MVP_INDISPONIVEL, "mvp_indisponivel", data_ref, b, publicado, [motivo])
    _auditar(cfg, res, inicio, {})
    return res


def _auditar(cfg: Config, res: ResultadoExecucao, inicio: float, estatisticas: dict,
             situacoes: list | None = None, fontes: dict | None = None, natureza: str | None = None) -> None:
    contagem = {}
    for s in situacoes or []:
        contagem[s["status"]] = contagem.get(s["status"], 0) + 1
    registro.auditar(cfg.pasta_logs, {
        "tipo": "boletim",
        "data_referencia": res.data_referencia,
        "status": res.status,
        "codigo_saida": res.codigo,
        "publicado": res.publicado,
        "duracao_s": round(time.perf_counter() - inicio, 2),
        "estatisticas": estatisticas,
        "linhas_por_status": contagem,
        "fonte_dados": fontes or {},
        "natureza_dados": natureza,
        "erros": res.erros,
    })
    nivel = logging.INFO if res.codigo == SUCESSO else logging.ERROR
    log.log(nivel, "=== Fim da execução | status=%s | código=%d ===", res.status, res.codigo)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Robô de boletim de atrasos do Ponto Falante")
    parser.add_argument("--config", default=str(Path(__file__).resolve().parents[2] / "config" / "monitoramento.yaml"))
    parser.add_argument("--data", help="Data de referência AAAA-MM-DD (padrão: ontem)")
    args = parser.parse_args(argv)

    hoje = datetime.now(FUSO).date()
    data_ref = args.data or (hoje - timedelta(days=1)).isoformat()
    try:
        date.fromisoformat(data_ref)
        cfg = carregar(args.config)
    except (ValueError, ErroConfiguracao) as e:
        print(f"Erro de configuração: {e}", file=sys.stderr)
        return ERRO_CONFIG
    registro.configurar(cfg.pasta_logs, hoje.isoformat())
    return executar(cfg, data_ref).codigo


if __name__ == "__main__":
    sys.exit(main())

"""Orquestrador do robô: executa o fluxo de ponta a ponta (ver docs/fluxo.bpmn).

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
from .cliente_mvp import ClienteMVP, MVPIndisponivel, RespostaInvalida
from .config import Config, ErroConfiguracao, carregar
from .decisao import avaliar_linhas
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

    # 1. Rede (GTFS real ou fictícia)
    try:
        rede = carregar_rede(cfg.gtfs_pasta, cfg.gtfs_pasta_ficticia)
    except GTFSInvalido as e:
        log.error("Nenhuma rede GTFS utilizável: %s", e)
        res = ResultadoExecucao(ERRO_CONFIG, "erro_gtfs", data_ref, erros=[str(e)])
        _auditar(cfg, res, inicio, {})
        return res
    avisos = [rede.aviso] if rede.aviso else []

    # 2. Coleta do histórico do dia
    try:
        registros = cliente.buscar_historico(data_ref)
        log.info("Histórico recebido: %d registros", len(registros))
    except (MVPIndisponivel, RespostaInvalida) as e:
        return _fluxo_mvp_indisponivel(cfg, cliente, data_ref, str(e), agora, inicio)

    # 3. Validação + deduplicação (repetição sobre a coleção)
    val = validar(registros, rede, cfg.regras, cfg.linhas, cfg.pontos)
    log.info("Validação: %d válidos, %d inválidos %s, %d duplicados, %d fora do escopo",
             len(val.validos), len(val.invalidos), val.contagem_motivos(), val.duplicados, val.fora_escopo)
    if not registros:
        avisos.append("O MVP não registrou passagens nesta data.")
        log.warning("Histórico vazio para %s", data_ref)
    elif len(val.invalidos) > len(registros) / 2:
        avisos.append("Mais da metade dos registros veio inconsistente; resultado pouco confiável.")
        log.warning("Dados inconsistentes: %d de %d inválidos", len(val.invalidos), len(registros))

    # 4. Decisão por linha
    situacoes = avaliar_linhas(val.validos, cfg.linhas, cfg.regras)
    for s in situacoes:
        log.info("Linha %s -> %s (%s)", s.linha, s.status, s.motivo)

    # 5. Boletim + publicação
    b = bol.montar(data_ref, situacoes, val, len(registros), cfg.regras, rede.origem, avisos, agora)
    caminho = armazenamento.salvar(cfg.pasta_saida, b)
    log.info("Boletim salvo em %s", caminho.relative_to(cfg.base) if caminho.is_relative_to(cfg.base) else caminho)
    try:
        cliente.publicar_boletim(b)
        log.info("Boletim publicado no MVP (POST /boletim)")
        res = ResultadoExecucao(SUCESSO, "sucesso", data_ref, b, publicado=True)
    except (MVPIndisponivel, RespostaInvalida) as e:
        log.error("Falha ao publicar o boletim: %s. Cópia local mantida.", e)
        res = ResultadoExecucao(PUBLICACAO_FALHOU, "publicacao_falhou", data_ref, b, erros=[str(e)])
    _auditar(cfg, res, inicio, b.get("estatisticas", {}), situacoes=b["linhas"], fontes=b["fonte_dados"])
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
             situacoes: list | None = None, fontes: dict | None = None) -> None:
    contagem = {}
    for s in situacoes or []:
        contagem[s["status"]] = contagem.get(s["status"], 0) + 1
    registro.auditar(cfg.pasta_logs, {
        "data_referencia": res.data_referencia,
        "status": res.status,
        "codigo_saida": res.codigo,
        "publicado": res.publicado,
        "duracao_s": round(time.perf_counter() - inicio, 2),
        "estatisticas": estatisticas,
        "linhas_por_status": contagem,
        "fonte_dados": fontes or {},
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

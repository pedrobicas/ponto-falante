"""Agendamento simples: boletim todo dia no horário configurado e coletor de amostras ao longo do dia.

O coletor roda coleta.execucoes_por_dia vezes, de 2 em 2 horas a partir das 07:00 (07, 09, ..., 21),
igual ao .github/workflows/rpa-coleta.yml.

    python -m pf_rpa.agendador              # fica rodando e dispara no horário
    python -m pf_rpa.agendador --agora      # roda uma vez já (útil na demo)

Em produção, o mesmo comando "python -m pf_rpa.robo" pode ir para o cron
(Linux) ou para o Agendador de Tarefas do Windows; ver README.
"""
from __future__ import annotations

import argparse
import logging
import time
from datetime import datetime
from pathlib import Path

import schedule

from . import registro
from .config import carregar
from .coletor import main as rodar_coletor
from .robo import FUSO, main as rodar_robo

log = logging.getLogger("pf_rpa.agendador")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(Path(__file__).resolve().parents[2] / "config" / "monitoramento.yaml"))
    parser.add_argument("--agora", action="store_true", help="executa imediatamente antes de agendar")
    args = parser.parse_args()

    cfg = carregar(args.config)
    registro.configurar(cfg.pasta_logs, datetime.now(FUSO).date().isoformat())

    def tarefa() -> None:
        codigo = rodar_robo(["--config", args.config])
        log.info("Execução agendada terminou com código %d", codigo)

    def coleta() -> None:
        codigo = rodar_coletor(["--config", args.config])
        log.info("Coleta agendada terminou com código %d", codigo)

    if args.agora:
        tarefa()
    schedule.every().day.at(cfg.horario, "America/Sao_Paulo").do(tarefa)
    horarios = [f"{7 + 2 * i:02d}:00" for i in range(cfg.coleta.execucoes_por_dia) if 7 + 2 * i < 24]
    for h in horarios:
        schedule.every().day.at(h, "America/Sao_Paulo").do(coleta)
    log.info("Boletim agendado para todo dia às %s; coleta às %s. Ctrl+C para sair.", cfg.horario, ", ".join(horarios))
    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    main()

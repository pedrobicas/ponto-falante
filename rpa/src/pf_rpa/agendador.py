"""Agendamento simples: roda o robô todo dia no horário configurado.

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

    if args.agora:
        tarefa()
    schedule.every().day.at(cfg.horario).do(tarefa)
    log.info("Robô agendado para todo dia às %s. Ctrl+C para sair.", cfg.horario)
    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    main()

"""Executa o RPA original contra Spring local e confirma persistencia do boletim."""
import argparse
from dataclasses import replace
from datetime import datetime, timedelta
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit
from urllib.request import urlopen
from zoneinfo import ZoneInfo

from ambiente import carregar

RAIZ = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True, help="Origem local do Spring, sem /api.")
    parser.add_argument("--env-file", type=Path, default=RAIZ / ".env")
    args = parser.parse_args()
    try:
        url = urlsplit(args.url)
        if url.scheme not in {"http", "https"} or url.hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise ValueError("Este teste publica dados e aceita somente servidor local.")
        env = carregar(args.env_file)
        chave = env.get("RPA_API_KEY")
        if not chave:
            raise ValueError("Configure RPA_API_KEY no ambiente local.")
        sys.path.insert(0, str(RAIZ / "rpa/src"))
        from pf_rpa.config import carregar as carregar_rpa
        from pf_rpa.robo import executar
        cfg = carregar_rpa(RAIZ / "rpa/config/monitoramento.yaml")
        data = (datetime.now(ZoneInfo("America/Sao_Paulo")).date() - timedelta(days=1)).isoformat()
        with TemporaryDirectory(prefix="pf-integracao-rpa-") as pasta:
            cfg = replace(cfg, mvp_url=args.url.rstrip("/") + "/api", api_key=chave,
                          pasta_saida=Path(pasta) / "saida", pasta_logs=Path(pasta) / "logs", backoff_inicial=0)
            resultado = executar(cfg, data)
            if resultado.codigo != 0 or not resultado.publicado:
                raise ValueError("O RPA nao confirmou a publicacao do boletim.")
            with urlopen(cfg.mvp_url + "/boletim/" + data, timeout=15) as resposta:
                boletim = json.load(resposta)
            if boletim.get("data_referencia") != data or not boletim.get("linhas") or not boletim.get("recebido_em"):
                raise ValueError("O boletim nao foi relido corretamente do PostgreSQL.")
        print("RPA: historico Spring consumido; boletim publicado e relido do PostgreSQL.")
        return 0
    except Exception:
        print("RPA: teste local falhou; confira logs locais e chave de integracao. Segredos omitidos.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

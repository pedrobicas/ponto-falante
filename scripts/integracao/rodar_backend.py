"""Inicia o Spring Boot lendo o .env local e passando segredos somente pelo ambiente."""
import argparse
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

from ambiente import carregar, normalizar_sptrans_token

RAIZ = Path(__file__).resolve().parents[2]


def preparar_ambiente(arquivo: Path) -> dict[str, str]:
    env = carregar(arquivo)
    modo = env.get("PF_SPTRANS_MODO", "auto").strip().lower()
    if modo not in {"auto", "demo"}:
        raise ValueError("PF_SPTRANS_MODO deve ser auto ou demo.")
    env["PF_SPTRANS_MODO"] = modo
    env["SPTRANS_TOKEN"] = "" if modo == "demo" else normalizar_sptrans_token(env.get("SPTRANS_TOKEN", ""))
    base = env.get("SPTRANS_BASE_URL") or "https://api.olhovivo.sptrans.com.br/v2.1"
    url = urlsplit(base)
    if url.scheme != "https" and not (url.scheme == "http" and url.hostname in {"127.0.0.1", "localhost", "::1"}):
        raise ValueError("SPTRANS_BASE_URL deve usar HTTPS; HTTP somente para testes locais.")
    env["SPTRANS_BASE_URL"] = base
    if "SPRING_DATASOURCE_PASSWORD" not in env and env.get("POSTGRES_PASSWORD"):
        env["SPRING_DATASOURCE_PASSWORD"] = env["POSTGRES_PASSWORD"]
    return env


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=RAIZ / ".env")
    parser.add_argument("--backend-dir", type=Path, default=RAIZ / "backend")
    args = parser.parse_args()
    try:
        env = preparar_ambiente(args.env_file)
        backend = args.backend_dir.resolve()
        wrapper = backend / ("mvnw.cmd" if os.name == "nt" else "mvnw")
        if not wrapper.is_file() or not (backend / "pom.xml").is_file():
            raise ValueError("Backend incompleto; informe --backend-dir com pom.xml e Maven Wrapper.")
        print("Iniciando Spring Boot com configuracao local; segredos omitidos.", flush=True)
        return subprocess.call([str(wrapper), "spring-boot:run"], cwd=backend, env=env)  # nosemgrep -- ferramenta local; argumentos fixos, env do próprio operador
    except ValueError as erro:
        print(f"Backend: {erro}", file=sys.stderr)
    except OSError:
        print("Backend: nao foi possivel iniciar o Maven Wrapper. Confira Java 21 e permissoes.", file=sys.stderr)
    except KeyboardInterrupt:
        return 130
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

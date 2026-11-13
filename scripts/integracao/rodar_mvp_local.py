"""Compila e inicia Angular + JAR Spring + PostgreSQL local, sem Docker. SPTrans em demo, salvo --sptrans-gateway."""
import argparse
import os
from pathlib import Path
import secrets
import subprocess
import sys

from ambiente import carregar

RAIZ = Path(__file__).resolve().parents[2]


def executar(cmd, cwd, env):
    subprocess.run([str(c) for c in cmd], cwd=cwd, env=env, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", action="store_true", help="Recompila frontend e backend.")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--env-file", type=Path, default=RAIZ / ".env")
    parser.add_argument("--sptrans-gateway", action="store_true",
                        help="Dados reais pelo gateway da Prefeitura (SPTRANS_GATEWAY_CHAVE/SEGREDO do .env).")
    args = parser.parse_args()
    pasta = RAIZ / ".validation/local"
    pasta.mkdir(parents=True, exist_ok=True)
    seguro = pasta / "runtime.env"
    env = carregar(args.env_file)
    anterior = carregar(seguro)
    for key in ("RPA_API_KEY", "PF_SALT", "GENAI_API_KEY"):
        env[key] = env.get(key) or anterior.get(key) or secrets.token_urlsafe(32)
    seguro.write_text("".join(f"{key}={env[key]}\n" for key in ("RPA_API_KEY", "PF_SALT", "GENAI_API_KEY")), encoding="utf-8")
    env["SPTRANS_TOKEN"] = ""
    if args.sptrans_gateway:
        if not (env.get("SPTRANS_GATEWAY_CHAVE", "").strip() and env.get("SPTRANS_GATEWAY_SEGREDO", "").strip()):
            print("SPTRANS_GATEWAY_CHAVE/SEGREDO ausentes no .env.", file=sys.stderr)
            return 2
        env["PF_SPTRANS_MODO"] = "auto"
    else:
        env["PF_SPTRANS_MODO"] = "demo"
        env["SPTRANS_GATEWAY_CHAVE"] = env["SPTRANS_GATEWAY_SEGREDO"] = ""
    env["GENAI_URL"] = (env.get("GENAI_URL", "").strip() or "http://127.0.0.1:8001").replace("host.docker.internal", "127.0.0.1")
    npm = "npm.cmd" if os.name == "nt" else "npm"
    mvn = RAIZ / "backend" / ("mvnw.cmd" if os.name == "nt" else "mvnw")
    jar = RAIZ / "backend/target/pontofalante.jar"
    try:
        if args.build or not jar.exists():
            if not (RAIZ / "frontend/node_modules").exists():
                executar([npm, "ci", "--no-audit", "--no-fund"], RAIZ / "frontend", env)
            executar([npm, "run", "build", "--", "--configuration", "production"], RAIZ / "frontend", env)
            executar([mvn, "-B", "-q", "-Pfrontend-build",
                      f"-Dpf.frontend.dir={RAIZ / 'frontend/dist/frontend/browser'}",
                      f"-Dpf.integration.root={RAIZ}", f"-Dpf.integration.python={sys.executable}",
                      "-Dpf.integration.angular=true", "verify"], RAIZ / "backend", env)
        cp = pasta / "classpath.txt"
        executar([mvn, "-B", "-q", "dependency:build-classpath", "-Dmdep.includeScope=test", f"-Dmdep.outputFile={cp}"], RAIZ / "backend", env)
        classes = pasta / "classes"
        classes.mkdir(exist_ok=True)
        classpath = cp.read_text(encoding="utf-8").strip()
        executar(["javac", "-encoding", "UTF-8", "-cp", classpath, "-d", classes, RAIZ / "scripts/local/DemoLocal.java"], RAIZ, env)
        return subprocess.call(["java", "-cp", str(classes) + os.pathsep + classpath, "DemoLocal", str(RAIZ), str(args.port)], cwd=RAIZ, env=env)
    except (subprocess.CalledProcessError, OSError):
        print("Falha ao preparar o MVP local; confira Java 21, Node 24 e as mensagens do build.", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())

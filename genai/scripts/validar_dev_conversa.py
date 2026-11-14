"""Smoke DEV independente, via FastAPI real. Não lê nenhum conjunto final.

Verifica disponibilidade, decisão de responder/recusar e família da fonte. Não mede
acurácia factual: o texto das respostas exige revisão humana junto ao corpus.
"""
import json
import sys
import time
import argparse
import os
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "scripts/integracao"))
from ambiente import carregar


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidato', action='store_true', help='Busca experimental, sem alterar API nem produção.')
    parser.add_argument('--direto', action='store_true', help='Agente local com rastros de diagnóstico, sem passar pela API.')
    parser.add_argument('--saida', type=Path, help='Arquivo novo de evidência; nunca sobrescreve uma avaliação.')
    args = parser.parse_args()
    env = carregar(RAIZ / "scripts/genai/.env.local")
    chave = env.get("GENAI_API_KEY")
    if not chave:
        raise SystemExit("GENAI_API_KEY local ausente; nenhuma requisição enviada.")
    modo = 'candidato' if args.candidato else 'direto' if args.direto else 'real'
    saida = args.saida or RAIZ / f".validation/assistente-20261113/genai-dev-{modo}-{datetime.now():%Y%m%d-%H%M%S-%f}.jsonl"
    if args.candidato or args.direto:
        for k in ('PF_MODELO', 'PF_LIMIAR', 'OLLAMA_HOST'):
            if env.get(k): os.environ[k] = env[k]
        sys.path.insert(0, str(RAIZ / 'genai/src'))
        from pf_genai import agente
        from pf_genai.indice import Indice
        from pf_genai.busca_conversa import IndiceConversa
        indice = Indice.carregar()
    saida.parent.mkdir(parents=True, exist_ok=True)
    casos = [json.loads(l) for l in (RAIZ / "genai/avaliacao/dev_conversa_20261113.jsonl").read_text(encoding="utf-8").splitlines() if l]
    falhas = 0
    with saida.open("x", encoding="utf-8") as arquivo:
        for caso in casos:
            inicio = time.perf_counter()
            # Loopback fixo da API local (mesma máquina): HTTP sem TLS não sai do computador.
            # nosemgrep: python.lang.security.audit.insecure-transport.urllib.insecure-request-object.insecure-request-object
            req = Request("http://127.0.0.1:8001/chat", data=json.dumps({"pergunta": caso["pergunta"]}).encode(),
                          headers={"Content-Type": "application/json", "X-API-Key": chave})
            try:
                if args.candidato or args.direto:
                    busca = IndiceConversa(indice, caso['pergunta']) if args.candidato else indice
                    resultado = agente.responder(caso['pergunta'], busca)
                    r = resultado.resposta.model_dump(exclude_none=True)
                    r['passos'] = resultado.passos
                else:
                    with urlopen(req, timeout=50) as resposta:  # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected -- URL fixa de loopback
                        r = json.load(resposta)
                ids = [f["trecho_id"] for f in r.get("fontes", [])]
                fonte_ok = caso["nao_consta"] or any(i.startswith(d + "-") for i in ids for d in caso["documentos"])
                ok = r.get("nao_consta") == caso["nao_consta"] and fonte_ok
                linha = {**caso, "resposta": r, "contrato_dev_ok": ok}
            except Exception as e:
                linha = {"id": caso["id"], "erro_tipo": type(e).__name__, "contrato_dev_ok": False}
            linha["ms_total"] = round((time.perf_counter() - inicio) * 1000)
            arquivo.write(json.dumps(linha, ensure_ascii=False) + "\n")
            arquivo.flush()
            falhas += not linha['contrato_dev_ok']
            print(f"{caso['id']}: contrato={linha['contrato_dev_ok']}, {linha['ms_total']} ms", flush=True)
    print(f"Contratos: {len(casos) - falhas}/{len(casos)}. Revisão factual ainda necessária. Evidência: {saida}")
    return int(falhas > 0)


if __name__ == "__main__":
    raise SystemExit(main())

"""Experimento v3: roda configurações sobre um conjunto e grava avaliacao/v3/placar_<conjunto>.csv.

    python scripts/rodar_v3.py --conjunto dev_v3 --configs rag_v1 v3_7b v3_7b_sem_rerank ...
    python scripts/rodar_v3.py --conjunto teste_v3 --configs sem_contexto rag_v1 agente_v1 v2_7b v3_7b   # UMA vez

Mesmo Ollama (temperatura 0, semente 42) e mesmas perguntas para todas as configurações.
O teste v3 só pode ser rodado com --confirmo-execucao-unica (proteção contra uso acidental).
"""
from __future__ import annotations

import argparse
import json
import hashlib
import sys
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pf_genai import agente, agente_v2, agente_v3, avaliacao_v3 as av3, gerador, llm  # noqa: E402
from pf_genai.agente_v2 import ConfigV2  # noqa: E402
from pf_genai.agente_v3 import ConfigV3  # noqa: E402
from pf_genai.busca_v3 import IndiceV3  # noqa: E402
from pf_genai.indice import Indice  # noqa: E402
from continuidade_v3 import (InconsistenciaRodada, conferir_manifesto,
                            executar_com_checkpoint, escrever_placar_atomico, trava_execucao)

# v3_7b: configuração histórica de 12/11 (limiar 0,0, sem poda), preservada para reprodução.
BASE_V3 = ConfigV3("v3_7b", limiar_rerank=0.0, podar_sem_evidencia=False)
CONFIGS_V3 = {
    "v3_7b": BASE_V3,
    "v3_3b": replace(BASE_V3, nome="v3_3b", modelo_gerador="qwen2.5:3b"),
    # ablações (uma peça desligada por vez, sempre no DEV)
    "v3_7b_sem_rerank": replace(BASE_V3, nome="v3_7b_sem_rerank", rerank=False),
    "v3_7b_sem_expansao": replace(BASE_V3, nome="v3_7b_sem_expansao", expansao=False),
    "v3_7b_sem_intencao": replace(BASE_V3, nome="v3_7b_sem_intencao", intencao=False),
    "v3_7b_sem_filtro_publico": replace(BASE_V3, nome="v3_7b_sem_filtro_publico", filtro_publico=False),
    "v3_7b_sem_checagens": replace(BASE_V3, nome="v3_7b_sem_checagens", checagens=False),
    "v3_7b_k5": replace(BASE_V3, nome="v3_7b_k5", k_contexto=5),
    # iteração 13/11 (DEV): limiar recalibrado e poda de fonte sem evidência literal
    "v3_7b_poda": replace(BASE_V3, nome="v3_7b_poda", podar_sem_evidencia=True),
    "v3_7b_poda_l25": replace(BASE_V3, nome="v3_7b_poda_l25", podar_sem_evidencia=True, limiar_rerank=-2.5),
    # v3_final = padrão atual do ConfigV3 (mesmos parâmetros de v3_7b_poda_l25), usado na API e no teste final.
    "v3_final": ConfigV3("v3_final"),
}
OUTRAS = ["sem_contexto", "rag_v1", "agente_v1", "v2_7b"]


def conferir_modelos_locais(configuracoes: list[str], modelo_base: str) -> None:
    """Falha antes de gravar linhas se Ollama/modelo estiver indisponível."""
    necessarios = {modelo_base}
    for nome in configuracoes:
        if nome in CONFIGS_V3:
            necessarios.add(CONFIGS_V3[nome].modelo_gerador)
    try:
        resposta = llm._cliente.list()
        modelos = resposta.models if hasattr(resposta, "models") else resposta.get("models", [])
        instalados = set()
        for m in modelos:
            titulo = (getattr(m, "model", None) or getattr(m, "name", None)
                      or (m.get("model") or m.get("name") if isinstance(m, dict) else None))
            if titulo:
                instalados.add(titulo)
    except Exception as e:
        sys.exit(f"Ollama local indisponível ({type(e).__name__}); nenhuma resposta nova foi gravada.")
    ausentes = necessarios - instalados
    if ausentes:
        sys.exit(f"Instale os modelos {sorted(ausentes)} no Ollama antes de executar. "
                 "Nenhuma resposta nova foi gravada.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--conjunto", choices=list(av3.CONJUNTOS_V3), required=True)
    ap.add_argument("--configs", nargs="+", choices=OUTRAS + list(CONFIGS_V3), required=True)
    ap.add_argument("--limiar", type=float, default=None, help="limiar do cross-encoder (padrão: o da ConfigV3)")
    ap.add_argument("--confirmo-execucao-unica", action="store_true")
    ap.add_argument("--saida", type=Path, help="Diretório de evidências. Com --retomar, use a pasta original.")
    ap.add_argument("--retomar", action="store_true", help="Continua DEV na mesma pasta, validando manifesto e IDs.")
    ap.add_argument("--modelo-base", default="qwen2.5:7b", help="Mesmo modelo para sem_contexto/RAG/agente v1.")
    args = ap.parse_args()
    if args.retomar and (args.conjunto != "dev_v3" or args.saida is None):
        sys.exit("--retomar só é permitido no DEV e exige --saida da rodada original.")
    if args.conjunto == "teste_v3" and not args.confirmo_execucao_unica:
        sys.exit("teste_v3 é congelado e roda UMA vez: use --confirmo-execucao-unica.")
    sys.stdout.reconfigure(encoding="utf-8")
    pasta = args.saida or av3.PASTA_V3 / datetime.now(timezone.utc).strftime("rodada_%Y%m%dT%H%M%SZ")
    if not args.retomar:
        pasta.mkdir(parents=True, exist_ok=True)
        if (pasta / "manifesto.json").exists():
            sys.exit("Diretório já contém uma rodada. Para DEV, use --retomar; caso contrário, escolha --saida novo.")
    elif not (pasta / "manifesto.json").is_file():
        sys.exit("A pasta solicitada não contém manifesto; retomada recusada.")
    conjunto_path = av3.CONJUNTOS_V3[args.conjunto]
    conjunto_hash = hashlib.sha256(conjunto_path.read_bytes()).hexdigest()
    if args.conjunto == "teste_v3":
        if conjunto_hash != "8b8100c417af716175aadbba1142fe7aa638be0a967aedb6370dca9d5b8957ab":
            sys.exit("Hash do teste fechado difere do congelamento.")
        # v3_final: candidata escolhida no DEV de 13/11 (7b); v3_7b fica para comparar com a iteração anterior.
        finais_permitidas = {"sem_contexto", "rag_v1", "agente_v1", "v2_7b", "v3_7b", "v3_final"}
        if args.modelo_base != "qwen2.5:7b" or any(c not in finais_permitidas for c in args.configs):
            sys.exit("Teste final exige modelo 7b; ablações e 3b ficam no DEV.")
        if (av3.PASTA_V3 / "teste_v3.execucao.json").exists():
            sys.exit("O teste final já foi iniciado. Não repita nem ajuste o sistema com suas respostas.")
    llm.MODELO = args.modelo_base
    llm.OPCOES.update(num_ctx=8192, num_predict=750)
    fontes_codigo = sorted((Path(__file__).resolve().parents[1] / "src/pf_genai").glob("*.py"))
    manifesto = {"conjunto": args.conjunto, "sha256": conjunto_hash, "configs": args.configs,
                 "modelo_base": llm.MODELO, "opcoes_llm": llm.OPCOES, "rubrica": av3.RUBRICA_VERSAO,
                 "v3": {n: asdict(replace(CONFIGS_V3[n], limiar_rerank=args.limiar)
                         if args.limiar is not None else CONFIGS_V3[n]) for n in args.configs if n in CONFIGS_V3},
                 "codigo_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in fontes_codigo},
                 "inicio_utc": datetime.now(timezone.utc).isoformat(), "estado": "em_execucao"}
    manifesto_path = pasta / "manifesto.json"
    if args.retomar:
        anterior = json.loads(manifesto_path.read_text(encoding="utf-8"))
        conferir_manifesto(anterior, manifesto)
        manifesto = anterior
    else:
        manifesto_path.write_text(json.dumps(manifesto, ensure_ascii=False, indent=2), encoding="utf-8")
    perguntas = av3.carregar(args.conjunto)
    conferir_modelos_locais(args.configs, args.modelo_base)
    idx1 = Indice.carregar()
    idx3 = IndiceV3.carregar_ou_criar()
    # A marcação irreversível ocorre apenas após conferir modelos e índices:
    # se Ollama estiver desligado, o teste final não será consumido por acidente.
    if args.conjunto == "teste_v3":
        try:
            with (av3.PASTA_V3 / "teste_v3.execucao.json").open("x", encoding="utf-8") as marcador:
                json.dump({"saida": str(pasta.resolve()), "sha256": conjunto_hash}, marcador)
        except FileExistsError:
            sys.exit("O teste final já foi iniciado. Não repita nem ajuste o sistema com suas respostas.")
    with trava_execucao(pasta):
        resumos = []
        for nome in args.configs:
            if nome == "sem_contexto":
                funcao = lambda q: gerador.sem_contexto(q)
            elif nome == "rag_v1":
                funcao = lambda q: gerador.rag(q, idx1)
            elif nome == "agente_v1":
                funcao = lambda q: agente.responder(q, idx1)
            elif nome == "v2_7b":
                cfg2 = ConfigV2("v2_7b", modelo_gerador="qwen2.5:7b", modelo_verificador="qwen2.5:7b")
                funcao = lambda q, c=cfg2: agente_v2.responder(q, idx1, c)
            else:
                cfg = CONFIGS_V3[nome]
                if args.limiar is not None:
                    cfg = replace(cfg, limiar_rerank=args.limiar)
                funcao = lambda q, c=cfg: agente_v3.responder(q, idx3, c)

            caminho = pasta / f"resultados_{args.conjunto}_{nome}.jsonl"
            from continuidade_v3 import ler_checkpoint
            ja_feitos = ler_checkpoint(caminho, perguntas, nome, av3.RUBRICA_VERSAO)
            contador = [len(ja_feitos)]

            def avaliar_pergunta(texto):
                # O executor entrega as perguntas em ordem e o checkpoint só
                # contém um prefixo válido do conjunto congelado.
                p = perguntas[contador[0]]
                contador[0] += 1
                try:
                    resultado = funcao(texto)
                except Exception as e:
                    # Falha de infraestrutura não deve preencher o placar com
                    # 55 "falhas operacionais" se o Ollama cair no meio.
                    raise RuntimeError(
                        f"Falha em {nome}/{p['id']}; checkpoint preservado. "
                        "Verifique o Ollama e use --retomar."
                    ) from e
                resultado.configuracao = nome
                return av3.avaliar(p, resultado)

            linhas = executar_com_checkpoint(perguntas, avaliar_pergunta, caminho,
                                              nome, av3.RUBRICA_VERSAO)
            resumo = av3.resumir(linhas)
            resumos.append(resumo)
            print(json.dumps(resumo, ensure_ascii=False))
        escrever_placar_atomico(pasta / f"placar_{args.conjunto}.csv", resumos)
        manifesto["estado"] = "concluido"
        manifesto["fim_utc"] = datetime.now(timezone.utc).isoformat()
        temporario = manifesto_path.with_suffix(".json.tmp")
        temporario.write_text(json.dumps(manifesto, ensure_ascii=False, indent=2), encoding="utf-8")
        temporario.replace(manifesto_path)


if __name__ == "__main__":
    main()

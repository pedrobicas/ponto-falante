"""Coletor de amostras REAIS de previsão (etapa automática que alimenta o boletim ESTIMADO).

Em cada execução:
1. Reenvia lotes pendentes de execuções anteriores (saida/pendentes/), se houver.
2. Repetição sobre os pontos monitorados: GET /pontos/{codigo}/previsoes no MVP (que consulta a SPTrans).
3. Valida cada resposta: só entra previsão real (fonte OLHO_VIVO, tipo PREVISAO, horário com fuso). Resposta
   SIMULADA (MVP em demonstração) é descartada: simulação nunca vira amostra real.
4. Envia o lote em POST /rpa/amostras (X-API-Key). Se o MVP cair ou recusar a chave, o lote é guardado em
   saida/pendentes/ e reenviado na próxima execução (sem intervenção humana).
5. Registra log e uma linha de auditoria (logs/auditoria.jsonl, tipo "coleta").

Uso:
    python -m pf_rpa.coletor                    # coleta e envia
    python -m pf_rpa.coletor --somente-leitura  # só lê os endpoints públicos e salva o lote local (sem POST)

Códigos de saída:
    0 sucesso (inclusive parcial: algum ponto falhou, mas houve amostra enviada)
    1 amostras coletadas, mas o envio falhou (lote guardado em pendentes)
    2 nenhuma amostra coletada (MVP fora do ar ou SPTrans indisponível em todos os pontos)
    3 erro de configuração
    4 o MVP só devolveu dados SIMULADOS (modo demonstração): nada foi gravado como real
    5 o MVP rejeitou uma ou mais amostras (motivos registrados na auditoria)
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from . import registro
from .cliente_mvp import ChaveRecusada, ClienteMVP, MVPIndisponivel, NaoEncontrado, RespostaInvalida
from .config import Config, ErroConfiguracao, carregar

log = logging.getLogger("pf_rpa.coletor")
FUSO = ZoneInfo("America/Sao_Paulo")
SUCESSO, ENVIO_FALHOU, SEM_AMOSTRAS, ERRO_CONFIG, SO_SIMULADO = 0, 1, 2, 3, 4
AMOSTRAS_REJEITADAS = 5
_HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
MAX_POR_ENVIO = 60


@dataclass
class ResultadoColeta:
    codigo: int
    status: str
    execucao_id: str
    amostras: list[dict[str, Any]] = field(default_factory=list)
    falhas: dict[str, str] = field(default_factory=dict)          # ponto -> motivo
    envio: dict[str, Any] = field(default_factory=dict)
    pendentes_reenviados: int = 0
    pendente_salvo: str | None = None
    erros: list[str] = field(default_factory=list)


def normalizar_resposta(ponto: str, dados: dict[str, Any], minutos_max: int) -> tuple[dict | None, str | None, int]:
    """Converte a resposta de /previsoes numa amostra do contrato. Devolve (amostra, motivo_recusa, ônibus_descartados)."""
    if dados.get("fonte") != "OLHO_VIVO":
        return None, "resposta_simulada" if dados.get("fonte") == "SIMULADO" else "fonte_desconhecida", 0
    if dados.get("tipo") != "PREVISAO":
        return None, "tipo_inesperado", 0
    try:
        quando = datetime.fromisoformat(str(dados.get("consultado_em")))
    except ValueError:
        return None, "consultado_em_invalido", 0
    if quando.tzinfo is None:
        return None, "consultado_em_invalido", 0
    if not isinstance(dados.get("onibus"), list):
        return None, "formato_invalido", 0
    onibus, descartados = [], 0
    for o in dados["onibus"]:                                 # repetição sobre cada ônibus previsto
        if not isinstance(o, dict):
            descartados += 1
            continue
        linha, minutos, previsto = o.get("letreiro"), o.get("minutos"), o.get("previsto_em")
        if (not isinstance(linha, str) or not re.fullmatch(r"[0-9A-Za-z-]{1,20}", linha)
                or isinstance(minutos, bool) or not isinstance(minutos, int) or not 0 <= minutos <= minutos_max
                or not isinstance(previsto, str) or not _HHMM.match(previsto)):
            descartados += 1
            continue
        item = {"linha": linha, "sentido": o.get("sentido"), "destino": str(o.get("destino") or "")[:80],
                "previsto_em": previsto, "minutos": minutos}
        if isinstance(o.get("acessivel"), bool):
            item["acessivel"] = o["acessivel"]
        if isinstance(o.get("veiculo"), str) and 0 < len(o["veiculo"]) <= 40:
            item["veiculo"] = o["veiculo"]                    # já chega anonimizado (hash) do MVP
        onibus.append(item)
    if dados["onibus"] and not onibus:
        return None, "onibus_invalidos", descartados
    referencia = dados.get("horario_referencia")
    amostra = {
        "ponto": ponto,
        "consultado_em": quando.replace(microsecond=0).isoformat(),
        "horario_referencia": referencia if isinstance(referencia, str) and _HHMM.match(referencia) else None,
        "fonte": "OLHO_VIVO",
        "tipo": "PREVISAO",
        "onibus": onibus,
    }
    return amostra, None, descartados


def _salvar_pendente(pasta: Path, execucao_id: str, amostras: list[dict[str, Any]]) -> Path:
    pasta.mkdir(parents=True, exist_ok=True)
    caminho = pasta / f"amostras_{execucao_id}.json"
    temporario = caminho.with_suffix(".tmp")
    temporario.write_text(json.dumps({"execucao_id": execucao_id, "amostras": amostras}, ensure_ascii=False),
                         encoding="utf-8")
    temporario.replace(caminho)
    return caminho


def _enviar(cliente: ClienteMVP, amostras: list[dict[str, Any]], execucao_id: str) -> dict[str, Any]:
    total = {"recebidas": 0, "gravadas": 0, "duplicadas": 0, "rejeitadas": []}
    for i in range(0, len(amostras), MAX_POR_ENVIO):           # lotes dentro do limite do backend
        r = cliente.enviar_amostras(amostras[i:i + MAX_POR_ENVIO], execucao_id)
        total["recebidas"] += int(r.get("recebidas", 0))
        total["gravadas"] += int(r.get("gravadas", 0))
        total["duplicadas"] += int(r.get("duplicadas", 0))
        total["rejeitadas"] += [{"indice": int(x.get("indice", -1)) + i, "motivo": x.get("motivo")}
                                for x in r.get("rejeitadas", []) if isinstance(x, dict)]
    return total


def _reenviar_pendentes(cfg: Config, cliente: ClienteMVP, erros: list[str]) -> int:
    """Repetição sobre os lotes pendentes; um lote só é apagado depois que o MVP confirma o recebimento."""
    reenviados = 0
    for arquivo in sorted(cfg.coleta.pasta_pendentes.glob("amostras_*.json")):
        try:
            lote = json.loads(arquivo.read_text(encoding="utf-8"))
            amostras = lote["amostras"]
            if not isinstance(amostras, list) or not amostras or not all(isinstance(a, dict) for a in amostras):
                raise ValueError("formato_invalido")
        except (OSError, ValueError, KeyError, TypeError):
            log.error("Lote pendente ilegível, movido para quarentena: %s", arquivo.name)
            arquivo.rename(arquivo.with_suffix(".invalido"))
            erros.append(f"Lote {arquivo.name} ilegível; guardado em quarentena.")
            continue
        r = _enviar(cliente, amostras, str(lote.get("execucao_id", arquivo.stem))[:64])
        log.info("Lote pendente %s reenviado: %d gravadas, %d duplicadas, %d rejeitadas (ex.: fora da janela de 48 h)",
                 arquivo.name, r["gravadas"], r["duplicadas"], len(r["rejeitadas"]))
        if r["rejeitadas"]:
            # Recusa definitiva (ex.: expiração) não melhora com retry, mas precisa
            # permanecer verificável e tornar a execução visivelmente incompleta.
            destino = arquivo.with_suffix(".rejeitado")
            destino.write_text(json.dumps({**lote, "resultado": r}, ensure_ascii=False), encoding="utf-8")
            erros.append(f"Lote {arquivo.name}: {len(r['rejeitadas'])} amostra(s) rejeitada(s).")
        arquivo.unlink()
        reenviados += 1
    return reenviados


def coletar(cfg: Config, cliente: ClienteMVP | None = None, somente_leitura: bool = False,
            agora: datetime | None = None) -> ResultadoColeta:
    agora = agora or datetime.now(FUSO)
    inicio = time.perf_counter()
    execucao_id = "coleta-" + agora.strftime("%Y%m%dT%H%M%S")
    cliente = cliente or ClienteMVP(cfg.mvp_url, cfg.coleta.timeout_segundos, cfg.tentativas,
                                    cfg.backoff_inicial, cfg.api_key)
    res = ResultadoColeta(SUCESSO, "sucesso", execucao_id)
    log.info("=== Início da coleta %s | %d pontos | MVP %s | %s ===", execucao_id, len(cfg.coleta.pontos),
             cfg.mvp_url, "somente leitura" if somente_leitura else "com envio")
    if not cfg.coleta.pontos:
        res.codigo, res.status = ERRO_CONFIG, "sem_pontos"
        res.erros.append("Nenhum ponto configurado em coleta.pontos")
        log.error(res.erros[0])
        _auditar(cfg, res, inicio, 0, somente_leitura)
        return res

    # 1. Pendências de execuções anteriores
    if not somente_leitura:
        try:
            res.pendentes_reenviados = _reenviar_pendentes(cfg, cliente, res.erros)
        except (MVPIndisponivel, RespostaInvalida) as e:
            log.warning("Pendências continuam guardadas para a próxima execução: %s", e)
            res.erros.append(str(e))

    # 2 e 3. Repetição sobre os pontos, com validação de cada resposta
    descartados = 0
    for ponto in cfg.coleta.pontos:
        try:
            dados = cliente.previsoes(ponto, cfg.coleta.timeout_segundos)
        except NaoEncontrado:
            # A SPTrans devolve parada vazia quando não há previsão (ex.: madrugada). Não é prova de ausência.
            res.falhas[ponto] = "sem_previsao_no_ponto"
            log.warning("Ponto %s: MVP respondeu 404 (sem previsão ou ponto inexistente)", ponto)
            continue
        except (MVPIndisponivel, RespostaInvalida) as e:
            res.falhas[ponto] = "mvp_ou_sptrans_indisponivel"
            log.error("Ponto %s: %s", ponto, e)
            continue
        amostra, motivo, n_desc = normalizar_resposta(ponto, dados, cfg.regras_estimadas.minutos_max_previsao)
        descartados += n_desc
        if motivo:
            res.falhas[ponto] = motivo
            log.warning("Ponto %s: resposta descartada (%s)", ponto, motivo)
            continue
        res.amostras.append(amostra)
        log.info("Ponto %s: %d ônibus previstos em %d linhas (consultado em %s)%s", ponto, len(amostra["onibus"]),
                 len({o["linha"] for o in amostra["onibus"]}), amostra["consultado_em"],
                 f"; {n_desc} ônibus descartados" if n_desc else "")

    # 4. Decisão sobre o resultado da coleta
    if not res.amostras:
        so_simulado = res.falhas and all(m == "resposta_simulada" for m in res.falhas.values())
        res.codigo, res.status = (SO_SIMULADO, "mvp_em_demonstracao") if so_simulado else (SEM_AMOSTRAS, "sem_amostras")
        res.erros.append("O MVP só devolveu dados simulados; nada gravado como real." if so_simulado
                         else "Nenhuma amostra real coletada.")
        log.error(res.erros[-1])
    elif somente_leitura:
        destino = cfg.pasta_saida / "amostras" / f"amostras_{execucao_id}.json"
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(json.dumps({"execucao_id": execucao_id, "amostras": res.amostras}, ensure_ascii=False,
                                      indent=1), encoding="utf-8")
        res.status = "parcial_somente_leitura" if res.falhas else "sucesso_somente_leitura"
        log.info("Somente leitura: %d amostras salvas em %s (nada enviado ao MVP)", len(res.amostras),
                 destino.relative_to(cfg.base) if destino.is_relative_to(cfg.base) else destino)
    else:
        try:
            res.envio = _enviar(cliente, res.amostras, execucao_id)
            res.status = "parcial" if res.falhas else "sucesso"
            if res.envio["rejeitadas"]:
                res.codigo, res.status = AMOSTRAS_REJEITADAS, "amostras_rejeitadas"
                res.erros.append(f"MVP rejeitou {len(res.envio['rejeitadas'])} amostra(s).")
            log.info("Envio: %d gravadas, %d duplicadas, %d rejeitadas %s", res.envio["gravadas"],
                     res.envio["duplicadas"], len(res.envio["rejeitadas"]), res.envio["rejeitadas"] or "")
        except (MVPIndisponivel, RespostaInvalida) as e:
            caminho = _salvar_pendente(cfg.coleta.pasta_pendentes, execucao_id, res.amostras)
            res.pendente_salvo = caminho.name
            res.codigo = ENVIO_FALHOU
            res.status = "chave_recusada" if isinstance(e, ChaveRecusada) else "envio_falhou"
            res.erros.append(str(e))
            log.error("Envio falhou (%s). Lote guardado em pendentes/%s para a próxima execução.", e, caminho.name)
    if res.codigo == SUCESSO and res.erros:
        res.codigo, res.status = ENVIO_FALHOU, "pendencias_com_falha"
    _auditar(cfg, res, inicio, descartados, somente_leitura)
    return res


def _auditar(cfg: Config, res: ResultadoColeta, inicio: float, descartados: int, somente_leitura: bool) -> None:
    motivos: dict[str, int] = {}
    for m in res.falhas.values():
        motivos[m] = motivos.get(m, 0) + 1
    registro.auditar(cfg.pasta_logs, {
        "tipo": "coleta",
        "execucao_id": res.execucao_id,
        "status": res.status,
        "codigo_saida": res.codigo,
        "somente_leitura": somente_leitura,
        "duracao_s": round(time.perf_counter() - inicio, 2),
        "pontos_configurados": len(cfg.coleta.pontos),
        "amostras_validas": len(res.amostras),
        "onibus_previstos": sum(len(a["onibus"]) for a in res.amostras),
        "onibus_descartados": descartados,
        "falhas_por_motivo": dict(sorted(motivos.items())),
        "envio": {k: (len(v) if isinstance(v, list) else v) for k, v in res.envio.items()},
        "rejeitadas": res.envio.get("rejeitadas", []),
        "pendentes_reenviados": res.pendentes_reenviados,
        "pendente_salvo": res.pendente_salvo,
        "fonte_dados": "olhovivo",
        "erros": res.erros,
    })
    nivel = logging.INFO if res.codigo == SUCESSO else logging.ERROR
    log.log(nivel, "=== Fim da coleta | status=%s | código=%d ===", res.status, res.codigo)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Coletor de amostras reais de previsão do Ponto Falante")
    parser.add_argument("--config", default=str(Path(__file__).resolve().parents[2] / "config" / "monitoramento.yaml"))
    parser.add_argument("--somente-leitura", action="store_true",
                        help="só consulta os endpoints públicos e salva o lote localmente, sem POST")
    args = parser.parse_args(argv)
    try:
        cfg = carregar(args.config)
    except ErroConfiguracao as e:
        print(f"Erro de configuração: {e}", file=sys.stderr)
        return ERRO_CONFIG
    registro.configurar(cfg.pasta_logs, datetime.now(FUSO).date().isoformat())
    return coletar(cfg, somente_leitura=args.somente_leitura).codigo


if __name__ == "__main__":
    sys.exit(main())

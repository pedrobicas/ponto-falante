"""
Comunicação com a API central do Ponto Falante.

Dois contratos:
- "equipe" (padrão, usado pela api_fake.py e no relatório):
    GET  /pontos/{codigo}/previsoes -> linhas que passam no ponto (para validar o OCR)
    POST /deteccoes                 -> envia o que a câmera viu
- "mvp" (o Spring Boot publicado, contratos/openapi-mvp.yaml):
    GET  /api/pontos/{codigo}/linhas (cadastro GTFS) e, se vazio, /api/pontos/{codigo}/previsoes
    POST /api/integracoes/visao/deteccoes com X-API-Key = VISAO_API_KEY

Resiliente: timeout curto, novas tentativas e, se a API estiver fora, a detecção
vai para uma fila local (arquivo .jsonl) e é reenviada depois. Nunca trava a câmera.
"""
from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

log = logging.getLogger("ponto_falante.api")


class ClienteAPI:
    def __init__(self, base_url: str | None = None, timeout: float = 3.0,
                 tentativas: int = 2, fila: str | Path = "fila_deteccoes.jsonl",
                 cache_s: float = 60.0, contrato: str = "equipe", chave: str | None = None,
                 dispositivo: str | None = None):
        if contrato not in ("equipe", "mvp"):
            raise ValueError("contrato deve ser 'equipe' ou 'mvp'")
        self.contrato = contrato
        self.chave = chave if chave is not None else os.getenv("VISAO_API_KEY", "")
        self.dispositivo = (dispositivo or os.getenv("PF_VISAO_DISPOSITIVO", "camera-ponto"))[:64]
        self.base_url = (base_url or os.getenv("PONTO_FALANTE_API", "http://localhost:8000")).rstrip("/")
        self.timeout = timeout
        self.tentativas = tentativas
        self.fila = Path(fila)
        self.cache_s = cache_s
        self._cache_linhas: dict[str, tuple[float, list[str]]] = {}
        self.sessao = requests.Session()

    def _requisicao(self, metodo: str, caminho: str, **kwargs):
        ultimo_erro = None
        for tentativa in range(1, self.tentativas + 1):
            try:
                r = self.sessao.request(metodo, self.base_url + caminho, timeout=self.timeout, **kwargs)
                r.raise_for_status()
                return r
            except requests.RequestException as e:
                ultimo_erro = e
                log.warning("Falha %s %s (tentativa %d/%d): %s", metodo, caminho, tentativa, self.tentativas, e)
                time.sleep(0.3 * tentativa)  # backoff simples
        raise ConnectionError(f"API indisponível: {ultimo_erro}")

    def linhas_do_ponto(self, ponto: str) -> list[str]:
        """Linhas que passam no ponto. Lista vazia se a API estiver fora (o leitor
        então funciona em modo sem validação, com confiança reduzida)."""
        agora = time.time()
        if ponto in self._cache_linhas and agora - self._cache_linhas[ponto][0] < self.cache_s:
            return self._cache_linhas[ponto][1]
        try:
            if self.contrato == "mvp":
                linhas = self._linhas_mvp(ponto)
            else:
                dados = self._requisicao("GET", f"/pontos/{ponto}/previsoes").json()
                itens = dados if isinstance(dados, list) else dados.get("previsoes", [])
                linhas = sorted({p["linha"] for p in itens if p.get("linha")})
        except (ConnectionError, ValueError, KeyError, AttributeError, TypeError) as e:
            log.warning("Sem lista de linhas do ponto %s: %s", ponto, e)
            # Mantém o último cache válido, se houver.
            return self._cache_linhas.get(ponto, (0, []))[1]
        self._cache_linhas[ponto] = (agora, linhas)
        return linhas

    def _linhas_mvp(self, ponto: str) -> list[str]:
        """Linhas do ponto no MVP: cadastro oficial; sem cadastro (modo demonstração), as linhas previstas agora."""
        dados = self._requisicao("GET", f"/api/pontos/{int(ponto)}/linhas").json()
        linhas = {l["letreiro"] for l in dados.get("linhas", []) if l.get("letreiro")}
        if not linhas:
            dados = self._requisicao("GET", f"/api/pontos/{int(ponto)}/previsoes").json()
            linhas = {o["letreiro"] for o in dados.get("onibus", []) if o.get("letreiro")}
        return sorted(linhas)

    def _corpo(self, ponto: str, linha: str | None, confianca: float) -> dict:
        agora = datetime.now(timezone.utc).isoformat()
        if self.contrato == "mvp":
            return {"ponto": int(ponto), "linha_reconhecida": linha, "confianca": round(float(confianca), 3),
                    "capturado_em": agora, "dispositivo": self.dispositivo}
        return {"ponto": ponto, "linha_lida": linha, "confianca": round(float(confianca), 3), "criado_em": agora}

    def _post_deteccao(self, corpo: dict) -> None:
        if self.contrato == "mvp":
            self._requisicao("POST", "/api/integracoes/visao/deteccoes", json=corpo, headers={"X-API-Key": self.chave})
        else:
            self._requisicao("POST", "/deteccoes", json=corpo)

    def enviar_deteccao(self, ponto: str, linha: str | None, confianca: float) -> bool:
        corpo = self._corpo(ponto, linha, confianca)
        try:
            self._post_deteccao(corpo)
            log.info("Detecção enviada: %s", {k: v for k, v in corpo.items() if k != "dispositivo"})
            return True
        except ConnectionError:
            with self.fila.open("a", encoding="utf-8") as f:
                f.write(json.dumps(corpo, ensure_ascii=False) + "\n")
            log.warning("API fora: detecção guardada na fila %s", self.fila)
            return False

    def reenviar_fila(self) -> int:
        """Tenta reenviar o que ficou na fila. Devolve quantas foram enviadas."""
        if not self.fila.exists():
            return 0
        pendentes = [json.loads(l) for l in self.fila.read_text(encoding="utf-8").splitlines() if l.strip()]
        restantes, enviados = [], 0
        for corpo in pendentes:
            try:
                self._post_deteccao(corpo)
                enviados += 1
            except ConnectionError:
                restantes.append(corpo)
        if restantes:
            self.fila.write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in restantes), encoding="utf-8")
        else:
            self.fila.unlink()
        return enviados

"""Cliente HTTP da API do MVP (Spring Boot).

- GET  /historico?data=YYYY-MM-DD  -> passagens do dia (olhovivo ou simulador)
- POST /boletim                    -> publica o boletim (cabeçalho X-API-Key)

Cada chamada tenta N vezes com espera crescente (backoff exponencial).
Se todas falharem, levanta MVPIndisponivel: quem chama decide o que fazer.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Callable

import requests

log = logging.getLogger("pf_rpa.mvp")


class MVPIndisponivel(Exception):
    """API do MVP fora do ar, lenta demais ou respondendo erro de servidor."""


class RespostaInvalida(Exception):
    """A API respondeu, mas o conteúdo não segue o contrato."""


class ClienteMVP:
    def __init__(self, url: str, timeout: float = 10, tentativas: int = 3,
                 backoff_inicial: float = 2, api_key: str | None = None,
                 dormir: Callable[[float], None] = time.sleep):
        self.url = url.rstrip("/")
        self.timeout = timeout
        self.tentativas = max(1, tentativas)
        self.backoff_inicial = backoff_inicial
        self.api_key = api_key
        self._dormir = dormir
        self.sessao = requests.Session()

    def _com_retry(self, descricao: str, fazer: Callable[[], requests.Response]) -> requests.Response:
        espera = self.backoff_inicial
        ultimo_erro = ""
        for tentativa in range(1, self.tentativas + 1):
            try:
                resp = fazer()
                if resp.status_code >= 500:
                    ultimo_erro = f"HTTP {resp.status_code}"
                elif resp.status_code in (401, 403):
                    # Erro de credencial não melhora tentando de novo.
                    raise MVPIndisponivel(f"{descricao}: acesso negado (HTTP {resp.status_code}); confira RPA_API_KEY")
                else:
                    return resp
            except (requests.ConnectionError, requests.Timeout) as e:
                ultimo_erro = type(e).__name__
            log.warning("%s falhou (tentativa %d/%d): %s", descricao, tentativa, self.tentativas, ultimo_erro)
            if tentativa < self.tentativas:
                self._dormir(espera)
                espera *= 2
        raise MVPIndisponivel(f"{descricao}: sem resposta após {self.tentativas} tentativas ({ultimo_erro})")

    def buscar_historico(self, data: str) -> list[dict[str, Any]]:
        resp = self._com_retry(
            f"GET /historico?data={data}",
            lambda: self.sessao.get(f"{self.url}/historico", params={"data": data}, timeout=self.timeout),
        )
        if resp.status_code != 200:
            raise RespostaInvalida(f"/historico respondeu HTTP {resp.status_code}")
        try:
            dados = resp.json()
        except ValueError as e:
            raise RespostaInvalida("/historico não devolveu JSON") from e
        # Aceita lista direta ou {"passagens": [...]} para tolerar pequenas variações do backend.
        if isinstance(dados, dict) and isinstance(dados.get("passagens"), list):
            dados = dados["passagens"]
        if not isinstance(dados, list):
            raise RespostaInvalida("/historico deveria devolver uma lista de passagens")
        return dados

    def publicar_boletim(self, boletim: dict[str, Any]) -> None:
        cabecalhos = {"Content-Type": "application/json"}
        if self.api_key:
            cabecalhos["X-API-Key"] = self.api_key
        resp = self._com_retry(
            "POST /boletim",
            lambda: self.sessao.post(f"{self.url}/boletim", json=boletim, headers=cabecalhos, timeout=self.timeout),
        )
        if resp.status_code not in (200, 201, 204):
            raise RespostaInvalida(f"/boletim recusou o envio: HTTP {resp.status_code}")

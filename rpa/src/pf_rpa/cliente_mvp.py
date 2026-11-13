"""Cliente HTTP da API do MVP (Spring Boot).

- GET  /historico?data=AAAA-MM-DD          -> passagens do dia (histórico SIMULADO de demonstração)
- GET  /rpa/amostras?data=AAAA-MM-DD       -> amostras REAIS de previsão gravadas pelo coletor
- POST /rpa/amostras                       -> coletor envia amostras (cabeçalho X-API-Key)
- GET  /pontos/{codigo}/previsoes          -> previsão atual da SPTrans num ponto (o que o coletor amostra)
- GET  /status                             -> modo do MVP (sptrans REAL, DEMO ou INDISPONIVEL)
- POST /boletim                            -> publica o boletim (cabeçalho X-API-Key)

Cada chamada tenta N vezes com espera crescente (backoff exponencial) quando há erro de rede ou HTTP 5xx
(o gateway da Prefeitura devolve 500 intermitente). Erro de chave (401/403) não é repetido.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Callable

import requests

log = logging.getLogger("pf_rpa.mvp")


class MVPIndisponivel(Exception):
    """API do MVP fora do ar, lenta demais ou respondendo erro de servidor."""


class ChaveRecusada(MVPIndisponivel):
    """O MVP recusou a chave (401/403). Tentar de novo não resolve: confira RPA_API_KEY."""


class RespostaInvalida(Exception):
    """A API respondeu, mas o conteúdo não segue o contrato."""


class NaoEncontrado(Exception):
    """HTTP 404: rota inexistente (MVP antigo) ou recurso sem dados (ponto sem previsão)."""


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
        self.sessao.headers["User-Agent"] = "PontoFalante-RPA/2.0"

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
                    raise ChaveRecusada(f"{descricao}: acesso negado (HTTP {resp.status_code}); confira RPA_API_KEY")
                else:
                    return resp
            except (requests.ConnectionError, requests.Timeout) as e:
                ultimo_erro = type(e).__name__
            log.warning("%s falhou (tentativa %d/%d): %s", descricao, tentativa, self.tentativas, ultimo_erro)
            if tentativa < self.tentativas:
                self._dormir(espera)
                espera *= 2
        raise MVPIndisponivel(f"{descricao}: sem resposta após {self.tentativas} tentativas ({ultimo_erro})")

    def _json(self, resp: requests.Response, rota: str) -> Any:
        if resp.status_code == 404:
            raise NaoEncontrado(f"{rota} respondeu HTTP 404")
        if resp.status_code != 200:
            raise RespostaInvalida(f"{rota} respondeu HTTP {resp.status_code}")
        try:
            return resp.json()
        except ValueError as e:
            raise RespostaInvalida(f"{rota} não devolveu JSON") from e

    def _cabecalhos(self) -> dict[str, str]:
        cab = {"Content-Type": "application/json"}
        if self.api_key:
            cab["X-API-Key"] = self.api_key
        return cab

    # ---------- leitura ----------
    def buscar_historico(self, data: str) -> list[dict[str, Any]]:
        resp = self._com_retry(
            f"GET /historico?data={data}",
            lambda: self.sessao.get(f"{self.url}/historico", params={"data": data}, timeout=self.timeout),
        )
        try:
            dados = self._json(resp, "/historico")
        except NaoEncontrado as e:
            raise RespostaInvalida(str(e)) from e
        # Aceita lista direta ou {"passagens": [...]} para tolerar pequenas variações do backend.
        if isinstance(dados, dict) and isinstance(dados.get("passagens"), list):
            dados = dados["passagens"]
        if not isinstance(dados, list):
            raise RespostaInvalida("/historico deveria devolver uma lista de passagens")
        return dados

    def buscar_amostras(self, data: str) -> list[dict[str, Any]]:
        """Amostras reais do dia. Levanta NaoEncontrado se o MVP ainda não tem a rota (versão antiga)."""
        resp = self._com_retry(
            f"GET /rpa/amostras?data={data}",
            lambda: self.sessao.get(f"{self.url}/rpa/amostras", params={"data": data}, timeout=self.timeout),
        )
        dados = self._json(resp, "/rpa/amostras")
        if not isinstance(dados, list):
            raise RespostaInvalida("/rpa/amostras deveria devolver uma lista")
        return dados

    def modo_sptrans(self) -> str | None:
        """REAL, DEMO ou INDISPONIVEL segundo /status; None se não deu para saber."""
        try:
            resp = self._com_retry("GET /status",
                                   lambda: self.sessao.get(f"{self.url}/status", timeout=self.timeout))
            dados = self._json(resp, "/status")
        except (MVPIndisponivel, RespostaInvalida, NaoEncontrado) as e:
            log.warning("Não foi possível ler o modo do MVP: %s", e)
            return None
        modo = dados.get("sptrans") if isinstance(dados, dict) else None
        return modo if isinstance(modo, str) else None

    def previsoes(self, ponto: str, timeout: float | None = None) -> dict[str, Any]:
        resp = self._com_retry(
            f"GET /pontos/{ponto}/previsoes",
            lambda: self.sessao.get(f"{self.url}/pontos/{ponto}/previsoes", timeout=timeout or self.timeout),
        )
        dados = self._json(resp, f"/pontos/{ponto}/previsoes")
        if not isinstance(dados, dict):
            raise RespostaInvalida("previsões deveriam ser um objeto")
        return dados

    # ---------- escrita (exigem X-API-Key) ----------
    def enviar_amostras(self, amostras: list[dict[str, Any]], execucao_id: str) -> dict[str, Any]:
        corpo = {"execucao_id": execucao_id, "amostras": amostras}
        resp = self._com_retry(
            "POST /rpa/amostras",
            lambda: self.sessao.post(f"{self.url}/rpa/amostras", json=corpo, headers=self._cabecalhos(),
                                     timeout=self.timeout, allow_redirects=False),
        )
        try:
            dados = self._json(resp, "/rpa/amostras")
        except NaoEncontrado as e:
            raise RespostaInvalida("o MVP ainda não tem POST /rpa/amostras (versão antiga do backend)") from e
        if not isinstance(dados, dict) or any(
                type(dados.get(campo)) is not int or dados[campo] < 0
                for campo in ("recebidas", "gravadas", "duplicadas")):
            raise RespostaInvalida("/rpa/amostras respondeu fora do contrato")
        rejeitadas = dados.get("rejeitadas")
        if not isinstance(rejeitadas, list) or any(
                not isinstance(r, dict) or type(r.get("indice")) is not int
                or not 0 <= r["indice"] < len(amostras) or not isinstance(r.get("motivo"), str)
                or not r["motivo"] for r in rejeitadas):
            raise RespostaInvalida("/rpa/amostras respondeu com rejeições inválidas")
        if (dados["recebidas"] != len(amostras)
                or dados["gravadas"] + dados["duplicadas"] + len(rejeitadas) != len(amostras)
                or len({r["indice"] for r in rejeitadas}) != len(rejeitadas)):
            raise RespostaInvalida("/rpa/amostras não confirmou o resultado de todas as amostras")
        return dados

    def publicar_boletim(self, boletim: dict[str, Any]) -> None:
        resp = self._com_retry(
            "POST /boletim",
            lambda: self.sessao.post(f"{self.url}/boletim", json=boletim, headers=self._cabecalhos(),
                                     timeout=self.timeout, allow_redirects=False),
        )
        if resp.status_code not in (200, 201, 204):
            raise RespostaInvalida(f"/boletim recusou o envio: HTTP {resp.status_code}")

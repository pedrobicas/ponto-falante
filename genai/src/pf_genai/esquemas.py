"""Formato de resposta da IA (contrato do grupo), validado com pydantic."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

RESPOSTA_NAO_CONSTA = ("Não encontrei essa informação nas fontes oficiais que eu conheço. "
                       "Para ter certeza, ligue para a SPTrans no telefone 156.")


class Fonte(BaseModel):
    documento: str
    trecho_id: str


class RespostaIA(BaseModel):
    resposta: str = Field(min_length=1, max_length=700)
    fontes: list[Fonte] = Field(default_factory=list)
    confianca: Literal["alta", "media", "baixa"]
    nao_consta: bool

    @model_validator(mode="after")
    def coerencia(self):
        # Recusa não cita fonte; resposta afirmativa precisa citar pelo menos uma.
        if self.nao_consta and self.fontes:
            self.fontes = []
        if not self.nao_consta and not self.fontes:
            raise ValueError("resposta sem nao_consta precisa citar ao menos uma fonte")
        return self


def recusa(confianca: str = "alta") -> RespostaIA:
    return RespostaIA(resposta=RESPOSTA_NAO_CONSTA, fontes=[], confianca=confianca, nao_consta=True)


class PerguntaChat(BaseModel):
    pergunta: str = Field(min_length=1, max_length=500)


class RespostaChat(RespostaIA):
    modo: str | None = None
    latencia_ms: int | None = None

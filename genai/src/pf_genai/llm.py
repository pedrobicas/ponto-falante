"""Cliente do LLM local (Ollama). Temperatura 0 para respostas reprodutíveis."""
from __future__ import annotations

import json
import os
from typing import Any

import ollama

MODELO = os.environ.get("PF_MODELO", "qwen2.5:3b")
_cliente = ollama.Client(host=os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434"), timeout=120)
OPCOES = {"temperature": 0, "seed": 42, "num_ctx": 4096, "num_predict": 350}


def gerar(sistema: str, usuario: str, json_schema: dict | None = None, **opcoes) -> str:
    resp = _cliente.chat(
        model=MODELO,
        messages=[{"role": "system", "content": sistema}, {"role": "user", "content": usuario}],
        format=json_schema if json_schema is not None else "",
        options={**OPCOES, **opcoes},
        keep_alive="30m",
    )
    return resp["message"]["content"]


def gerar_json(sistema: str, usuario: str, schema: dict | str = "json", **opcoes) -> dict[str, Any]:
    """Pede saída estruturada (Ollama 'format' com JSON Schema) e devolve o dict."""
    bruto = gerar(sistema, usuario, json_schema=schema, **opcoes)
    return json.loads(bruto)

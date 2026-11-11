"""Cliente do LLM local (Ollama). Temperatura 0 para respostas reprodutíveis."""
from __future__ import annotations

import json
import os
from typing import Any

import ollama

MODELO = os.environ.get("PF_MODELO", "qwen2.5:3b")
_cliente = ollama.Client(host=os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434"), timeout=120)
OPCOES = {"temperature": 0, "seed": 42, "num_ctx": 4096, "num_predict": 350}


def gerar(sistema: str, usuario: str, json_schema: dict | None = None, modelo: str | None = None,
          **opcoes) -> str:
    modelo = modelo or MODELO
    extra = {"think": False} if modelo.startswith("qwen3") else {}   # qwen3: sem "thinking" (latência)
    resp = _cliente.chat(
        model=modelo,
        messages=[{"role": "system", "content": sistema}, {"role": "user", "content": usuario}],
        format=json_schema if json_schema is not None else "",
        options={**OPCOES, **opcoes},
        keep_alive="30m",
        **extra,
    )
    return resp["message"]["content"]


def gerar_json(sistema: str, usuario: str, schema: dict | str = "json", modelo: str | None = None,
               **opcoes) -> dict[str, Any]:
    """Pede saída estruturada (Ollama 'format' com JSON Schema) e devolve o dict."""
    bruto = gerar(sistema, usuario, json_schema=schema, modelo=modelo, **opcoes)
    return json.loads(bruto)

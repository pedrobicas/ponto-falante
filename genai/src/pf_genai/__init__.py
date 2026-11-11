"""Assistente do Ponto Falante: LLM local (Ollama) + RAG + agente verificador."""
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]          # pasta genai/
BASE = RAIZ / "base"
AVALIACAO = RAIZ / "avaliacao"

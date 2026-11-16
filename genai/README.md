# Ponto Falante · Assistente com LLM local (Generative AI for Engineering)

Global Solution 2026.2 · CitizenTech · FIAP Engenharia de Software (4º ano) · problema: **mobilidade**

| Integrante | RM |
|---|---|
| Pedro Henrique Bicas Couto | 99534 |
| Bryan Willian | 551305 |
| Felipe Masera Terra | 99405 |
| Gabriel Fernandes Doms | 98630 |
| Lucas Vassão Braga | 98607 |

O assistente tira dúvidas de passageiros de ônibus de São Paulo, sobretudo pessoas idosas, com deficiência visual e estudantes. Os temas são gratuidade, Bilhete Único, integração, tarifas e direitos no transporte.

- Ele responde **só com base em documentos oficiais** (SPTrans e leis federais), **cita o trecho** usado e **recusa** quando a base não tem a resposta ("Não encontrei… ligue 156").
- A resposta é curta porque é lida em voz alta pelo aplicativo.
- Roda **100% local e gratuito**: Ollama + `qwen2.5:7b` no site (o `qwen2.5:3b` da v1 continua reproduzível), embeddings `multilingual-e5-large`, índice FAISS.
- O backend Spring Boot do MVP chama este serviço por HTTP (`POST /chat`).

Relatório completo: [RELATORIO.md](RELATORIO.md) · Cinco erros reais: [avaliacao/erros.md](avaliacao/erros.md)

## Resultado mais recente (teste final v3, 46 perguntas inéditas, rodado uma vez em 13/11/2026)

Mesmo `qwen2.5:7b` em todas as configurações. Detalhes, ablações do DEV e 5 erros analisados na seção 12 do
[RELATORIO.md](RELATORIO.md).

| Configuração | Acerto | Recusa correta | Erros factuais por pergunta |
|---|---|---|---|
| Sem contexto | 8,7% | 15,4% | 34,8% |
| RAG simples | 65,2% | 69,2% | 15,2% |
| **Agente v1 (usado no site)** | **65,2%** | **84,6%** | **8,7%** |
| Agente v3 | 58,7% | 76,9% | 13,0% |

A v3 venceu no DEV (88,0%) mas não no teste: o agente v1 segue como padrão por errar menos.

## Resultado em uma tabela (teste final, 40 perguntas, rodado uma vez)

Mesmo modelo, temperatura 0, semente 42, mesmo índice, mesmo limiar e mesmas perguntas. Só muda a estratégia.

| Configuração | Acerto | Recusa correta ("não consta") | Alucinação | Recusa indevida | Sem fundamentação | Precisão das citações |
|---|---|---|---|---|---|---|
| A · modelo sem contexto | 5,0% | 10% | 85,0% | 13,3% | 100% | 0% |
| B · RAG simples | 67,5% | 100% | 20,0% | 16,7% | 4,0% | 80,8% |
| C · RAG + agente (usado na API) | 52,5% | 100% | **5,0%** | 56,7% | **0%** | 81,2% |

O RAG acerta muito mais e alucina muito menos que o mesmo modelo sem contexto. O agente é o mais seguro: alucina 4 vezes menos que o RAG simples e nunca dá resposta sem fundamentação. O custo é recusar mais do que deveria. Detalhes e interpretação estão no [RELATORIO.md](RELATORIO.md#8-resultados).

## Estrutura

```
genai/
  notebooks/   01_base_conhecimento · 02_indice_recall_limiar · 03_geracao_fundamentada · 04_agente_e_placar (com saídas)
  base/        fontes.csv (fonte, URL, licença, data de acesso) · brutos/ (cópias baixadas) · textos/ · trechos.jsonl
               tabela_base.csv · indice.faiss + indice_meta.json
  avaliacao/   perguntas_dev.jsonl (desenvolvimento) · perguntas.jsonl (teste final) · placar_dev.csv · placar_teste.csv
               resultados_*.jsonl (resposta por pergunta) · historico_dev/ (5 iterações do agente) · erros.md
               exploratorio_descartado/ (1ª rodada que usou o teste; descartada, mantida por transparência)
  src/pf_genai/ trechos · indice · llm · gerador (sem contexto e RAG) · agente · esquemas (pydantic) · avaliacao
  api/app.py   FastAPI: POST /chat, GET /health
  scripts/     baixar_leis.py · rodar_placar.py · gerar_notebooks.py
  tests/       test_unidades.py (contrato, validação, métricas, degradação da API)
```

## Como reproduzir (Windows, macOS ou Linux)

1. **Ollama e modelo** (gratuitos): instale em https://ollama.com e baixe o modelo:
   ```bash
   ollama pull qwen2.5:3b
   ```
2. **Python 3.11** e dependências:
   ```bash
   python -m venv .venv
   ```
   ```bash
   .venv/Scripts/pip install -r requirements.txt
   ```
   (No macOS/Linux, use `.venv/bin/pip`.) O modelo de embeddings (~2 GB) é baixado automaticamente na primeira execução.
3. **Base de conhecimento:**
   - as páginas da SPTrans estão salvas em `base/brutos/`, com a data de acesso em `fontes.csv`, porque o site muda;
   - as leis podem ser baixadas de novo com o comando abaixo;
   - o notebook 01 gera os trechos e o 02 gera o índice.
   ```bash
   python scripts/baixar_leis.py
   ```
4. **Notebooks com saídas** (01 a 04):
   ```bash
   jupyter nbconvert --to notebook --execute --inplace notebooks/*.ipynb --ExecutePreprocessor.timeout=-1
   ```
5. **Placar.** Use `dev` para desenvolvimento; `teste` é a avaliação final e deve rodar uma única vez:
   ```bash
   python scripts/rodar_placar.py --conjunto dev
   ```
   ```bash
   python scripts/rodar_placar.py --conjunto teste
   ```
6. **Testes** (não precisam do Ollama):
   ```bash
   python -m pytest -q tests
   ```
7. **API** (dentro de `genai/`, com `PYTHONPATH=src`):
   ```bash
   uvicorn api.app:app --port 8001
   ```
   Configure `GENAI_API_KEY` no ambiente antes de iniciar. Exemplo de chamada em Bash,
   usando a mesma variável (não substituir por uma chave literal no histórico):
   ```bash
   curl -X POST http://localhost:8001/chat -H "X-API-Key: $GENAI_API_KEY" -H "Content-Type: application/json" -d "{\"pergunta\": \"Tenho 67 anos, pago ônibus?\"}"
   ```

Variáveis de ambiente:

| Variável | Para que serve | Padrão |
|---|---|---|
| `PF_MODELO` | Modelo do Ollama (o site usa `qwen2.5:7b`, definido em `scripts/genai/.env.local`) | `qwen2.5:3b` |
| `OLLAMA_HOST` | Endereço do Ollama | `http://127.0.0.1:11434` |
| `PF_EMBEDDINGS` | Modelo de embeddings | `intfloat/multilingual-e5-large` |
| `PF_LIMIAR` | Limiar de similaridade | `0.86` |
| `PF_MODO` | Estratégia servida pela API: `agente` (menos alucinação) ou `rag` (responde mais) | `agente` |
| `GENAI_API_KEY` | Autenticação entre backend e API; obrigatória no serviço publicado | Sem padrão |
| `GENAI_TIMEOUT_S` | Prazo global de uma pergunta, incluindo as etapas do agente | `40` |

O Ollama não exige chave de provedor. A API do produto exige autenticação; no Windows,
use as instruções de serviço em [`scripts/genai/README.md`](../scripts/genai/README.md).

## Evidência da API rodando

`tests/saida_api.txt`: chamada real em 11/11/2026 a `GET /health` (200, LLM e índice ok), três `POST /chat` (incluindo uma pergunta fora da base, recusada em 0,7 s) e uma pergunta vazia (422, validação do contrato).

## Contrato com o backend (Spring Boot)

`POST /chat` recebe `{"pergunta": "..."}` e devolve:

```json
{"resposta": "...", "fontes": [{"documento": "...", "trecho_id": "..."}],
 "confianca": "alta|media|baixa", "nao_consta": false, "modo": "rag_agente", "latencia_ms": 2100}
```

- Se o Ollama cair, a resposta é HTTP 503 com uma mensagem amigável (`modo: "indisponivel"`). Nunca há falha silenciosa.
- `GET /health` informa o estado do LLM e do índice.
- Ao exceder 40 s, a API retorna 504; o backend apresenta indisponibilidade ao usuário.
  Diagnóstico da gravação: [`timeout_genai_20261114.md`](../docs/evidencias/timeout_genai_20261114.md).
- Contrato completo: `../contratos/openapi-integracao.yaml`. Exemplo em Java: `../contratos/GUIA_BACKEND_SPRING.md`.

## Por que agente e não LoRA

- Treinar LoRA de um modelo de 3B pede GPU NVIDIA (CUDA) e centenas de pares pergunta/resposta revisados. A máquina do projeto tem GPU AMD no Windows e o prazo era de 8 dias.
- O agente roda no **mesmo** modelo local, é medido no **mesmo** placar e ataca diretamente os erros do RAG simples:
  - reescrita da consulta;
  - citação restrita aos trechos recuperados;
  - checagem determinística de números;
  - verificação de fundamentação com nova tentativa ou recusa.
- Cada decisão fica registrada em `passos`, o que torna a resposta explicável.

## Segurança, explicabilidade e LGPD

- **LGPD:** a API não guarda a pergunta, IP nem identificador. O log registra só latência, se recusou e quantas fontes usou. A base só tem documentos públicos, sem dado pessoal.
- **Explicabilidade:** toda resposta afirmativa cita o `trecho_id` e o documento. O rastro do agente (`passos`) mostra por que ele respondeu ou recusou.
- **Segurança:**
  - roda localmente, sem enviar dados a terceiros;
  - o JSON é validado com pydantic antes de sair;
  - na dúvida, recusa e indica o telefone 156 da SPTrans.
- **O que é simulado:** nada nesta parte. As perguntas de avaliação foram escritas pela equipe, com gabarito tirado dos documentos oficiais.

## Links

- Repositório atual: https://github.com/pedrobicas/ponto-falante (privado; cópia pública sanitizada depende de autorização).
- Vídeo final local: [Ponto_Falante_GenAI.mp4](../entregaveis/Ponto_Falante_GenAI.mp4), 2min22s (142 s), 1920 x 1080, sem áudio e sem música.
- [Roteiro para narração humana](../entregaveis/ROTEIRO_GENAI.md) · [Evidências e limites observados](../docs/evidencias/video_genai_20261115.md).
- Hospedagem e URL pública do vídeo ainda pendentes. `entregaveis/` é uma pasta local ignorada pelo Git.

# Ponto Falante · Análise e arquitetura dos módulos GenAI e RPA

Global Solution 2026.2 · CitizenTech · Engenharia de Software 4º ano · entrega 19/11/2026 23h55
Responsável pelos módulos: Pedro ([NOME COMPLETO E RM])
Fontes: PDF oficial da GS (prevalece; slides 18–31 e 45–50) e Guia do grupo (Prompt 0 = contrato comum).

---

## 1. O que cada módulo resolve

| Módulo | Pergunta do cidadão / tarefa | Saída consumida pelo MVP |
|---|---|---|
| **GenAI · Inteligência** | "Tenho 62 anos, pago a passagem?", "Como peço o cartão especial?", "Quanto tempo vale a integração do Bilhete Único?" | `POST /chat` → JSON com resposta curta, fontes citadas, confiança e `nao_consta` |
| **RPA · Automação** | Hoje alguém teria de acompanhar as linhas, anotar atrasos, comparar com o programado e avisar passageiros. O robô faz isso todo dia. | Boletim diário (JSON + HTML em linguagem simples) publicado no backend → `GET /boletim` |

## 2. Decisão de stack (divergência resolvida)

O Guia diz que a API central é FastAPI, mas o MVP do grupo é **Angular + Spring Boot + PostgreSQL**. Prevalece o que o grupo construiu. Consequência:

- O **Spring Boot é o único ponto de entrada** do Angular. Ele expõe todos os endpoints do contrato (`/pontos`, `/previsoes`, `/chat`, `/boletim`, `/historico`, `/status`, `/health`).
- O **GenAI é um microsserviço Python** (FastAPI + Ollama) que o Spring chama por HTTP via variável `LLM_URL`. O navegador nunca fala com o Ollama.
- O **RPA é um job Python agendado** que lê `GET /historico` do Spring e publica com `POST /boletim` (endpoint novo, autenticado por chave em variável de ambiente).
- Integração por contrato HTTP (slide 21, "Integração real"), não por prints.

```mermaid
flowchart LR
  U[Passageiro<br/>Angular: voz + alto contraste] -->|HTTPS| SB[Spring Boot API]
  SB --> PG[(PostgreSQL)]
  SB -->|POST /chat<br/>LLM_URL, timeout 30s| GA[GenAI service<br/>FastAPI :8001]
  GA --> RET[Busca vetorial FAISS<br/>embeddings multilíngues]
  RET --> KB[(base/ trechos com fonte)]
  GA --> OL[Ollama<br/>qwen2.5:3b local]
  RPA[Robô RPA<br/>Python + schedule] -->|GET /historico?data=| SB
  RPA -->|lê| GTFS[(GTFS ou rede fictícia)]
  RPA -->|POST /boletim<br/>X-API-Key| SB
  RPA --> LOG[(logs/ + saida/)]
  SB -->|GET /boletim| U
```

## 3. Contratos de integração com o Spring Boot

Arquivo de referência: `contratos/openapi-integracao.yaml` (o time do backend pode gerar DTOs a partir dele).

### 3.1 `POST /chat` (Spring → GenAI)

Requisição: `{"pergunta": "string (1–500 caracteres)"}`
Sem identificador de usuário, sem histórico guardado (LGPD by design).

Resposta 200 (formato exigido pelo Guia):
```json
{
  "resposta": "Sim. Pessoas com 60 anos ou mais não pagam a tarifa nos ônibus municipais de São Paulo...",
  "fontes": [{"documento": "SPTrans · Gratuidades", "trecho_id": "sptrans-gratuidade-003"}],
  "confianca": "alta",
  "nao_consta": false
}
```
Regras: `nao_consta=true` ⇒ `fontes=[]` e resposta padrão "Não encontrei essa informação nas fontes oficiais que tenho...". O Spring repassa o corpo sem alterar. Se o serviço cair ou passar do timeout, o Spring responde 200 com `{"resposta": "O assistente está indisponível agora. Tente de novo em instantes.", "fontes": [], "confianca": "baixa", "nao_consta": true}` (degradar com elegância).

Extras opcionais na resposta (o Spring pode ignorar): `"modo"`, `"latencia_ms"`.

### 3.2 `GET /historico?data=YYYY-MM-DD` (RPA → Spring)

Lista de passagens do dia, de qualquer fonte. Proposta: o mesmo objeto `previsao` do contrato comum + `veiculo` (identificador já anonimizado/hash), necessário para remover duplicados (mesmo veículo, mesmo ponto, mesmo minuto).
```json
[{"ponto":"PF-0001","linha":"8000-10","sentido":"Terminal Lapa","veiculo":"a1f3...",
  "programado_em":"07:10","previsto_em":"07:18","minutos":0,"acessivel":true,
  "fonte":"simulador","atualizado_em":"2026-11-12T07:18:05-03:00"}]
```
**Pedido ao backend:** incluir `veiculo` no histórico. Se não vier, o robô deduplica por (linha, ponto, minuto) e registra no log.

### 3.3 `POST /boletim` (RPA → Spring) e `GET /boletim` (Angular → Spring)

Cabeçalho `X-API-Key: ${RPA_API_KEY}` (variável de ambiente nos dois lados, nunca no código). O Spring guarda o JSON (tabela `boletim`, coluna `jsonb`, chave `data_referencia`, upsert) e `GET /boletim` devolve o mais recente.
```json
{
  "data_referencia": "2026-11-12",
  "gerado_em": "2026-11-13T06:00:04-03:00",
  "desatualizado": false,
  "motivo_desatualizado": null,
  "fonte_dados": {"olhovivo": 0, "simulador": 412},
  "parametros": {"atraso_critico_min": 10, "atraso_atencao_min": 5, "intervalo_critico_min": 30, "intervalo_atencao_min": 20},
  "estatisticas": {"recebidos": 430, "validos": 400, "invalidos": 18, "duplicados": 12},
  "invalidos_por_motivo": {"linha_inexistente": 6, "horario_incoerente": 9, "campo_vazio": 3},
  "linhas": [{"linha": "8000-10", "status": "CRITICA", "atraso_medio_min": 12.4, "intervalo_max_min": 34,
              "passagens": 41, "frase": "Linha 8000-10: atrasos fortes, em média 12 minutos."}],
  "resumo_falado": "Boletim de 12 de novembro. 1 linha com atraso forte...",
  "html": "<section>...</section>"
}
```
Se `POST /boletim` falhar após as tentativas, o robô salva em `saida/` e registra a falha. Quando o histórico do dia não puder ser lido, republica o último boletim com `desatualizado=true` e o motivo (exigência do Guia: "mantém o boletim anterior marcado como desatualizado").

## 4. GenAI · desenho técnico

| Item | Escolha | Por quê |
|---|---|---|
| LLM | **Ollama + qwen2.5:3b** (Q4, ~1,9 GB) | Local e gratuito (exigência do slide 29), melhor português entre os 3B sugeridos, roda em CPU ou na RX 7600 |
| Embeddings | `intfloat/multilingual-e5-large` via fastembed (ONNX) | Multilíngue, gratuito, sem PyTorch. Escolhido no conjunto de desenvolvimento contra MiniLM e mpnet (recall@3 1,00 × 0,65 × 0,60) |
| Índice | FAISS (`IndexFlatIP`, cosseno) | Citado no Guia; base pequena, busca exata |
| Validação | pydantic v2 + `format=json` do Ollama | JSON sempre válido; se inválido, 1 nova tentativa e depois recusa |
| Especialização | **Agente** (não LoRA) | Ver abaixo |

**Por que agente e não LoRA:** treinar LoRA de um 3B exige GPU NVIDIA (Colab T4) e um conjunto de treino que não temos tempo de montar bem em 8 dias; a GPU AMD no Windows não roda o ecossistema de treino. O agente é avaliável no mesmo placar e ataca diretamente as causas de alucinação. Pipeline do agente:
1. **Classificar** a pergunta (escopo transporte / fora de escopo) → fora de escopo recusa sem gastar geração.
2. **Reescrever** a consulta em termos da base (ex.: "velhinho" → "pessoa idosa 60 anos gratuidade").
3. **Buscar** top-k com limiar; se nada passar do limiar → `nao_consta`.
4. **Gerar** resposta curta em JSON citando `trecho_id`.
5. **Verificar**: cada `trecho_id` citado existe entre os recuperados e a resposta é sustentada pelo trecho (checagem pelo próprio LLM); senão, regenera uma vez ou recusa.

**Separação desenvolvimento × teste:** todas as escolhas (embeddings, limiar 0,86, ajustes do agente) usam `avaliacao/perguntas_dev.jsonl` (30 perguntas); o teste final `avaliacao/perguntas.jsonl` (40) é rodado uma única vez, depois de congelar o agente.

**Três configurações do placar (critério 06):** (A) modelo sem contexto, (B) RAG simples, (C) RAG + agente. Métricas sobre ~40 perguntas com gabarito: acerto (resposta correta), alucinação (afirma algo fora do gabarito/da base), recusa correta em perguntas "não consta", JSON válido, citação correta, latência média.

**Base de conhecimento (só documentos públicos, a confirmar por você antes do uso):**
- Lei 10.741/2003 (Estatuto da Pessoa Idosa), artigos de transporte (arts. 39 a 42), no site do Planalto.
- Lei 13.146/2015 (Lei Brasileira de Inclusão), capítulo do transporte e mobilidade (arts. 46 a 52), no site do Planalto.
- Páginas da SPTrans sobre tarifas, gratuidades (idoso, pessoa com deficiência), Bilhete Único e integração.
Vou verificar cada URL antes de baixar e registrar data de acesso e licença na tabela da base (critério 02). Não invento números: tarifa e prazos vêm só do texto baixado.

**Estrutura do repositório GenAI (slide 31):**
```
genai/
  notebooks/   01_base.ipynb 02_indice_recall.ipynb 03_geracao.ipynb 04_agente_placar.ipynb (com saídas)
  base/        brutos/ trechos.jsonl fontes.csv
  avaliacao/   perguntas.jsonl placar.csv erros.md
  api/         app.py (POST /chat, GET /health)
  src/pf_genai/  chunking, indice, gerador, agente, esquemas
  tests/       testes do contrato e da recusa
  README.md  RELATORIO.md  requirements.txt
```

## 5. RPA · desenho técnico

Python 3.11 + `requests` (com retry/backoff), `pyyaml`, `jinja2`, `schedule`, `pytest`. Python foi escolhido porque o slide 47 aceita e porque versiona e testa melhor que UiPath/Power Automate.

Fluxo (8 etapas obrigatórias dos slides 47–48):
1. **Entrada:** `config/monitoramento.yaml` (linhas, pontos, limites X/Y, URL do MVP) + GTFS (`routes.txt`, `stop_times.txt`) ou rede fictícia.
2. **Coleta:** `GET /historico?data=` com 3 tentativas e backoff exponencial.
3. **Repetição + validação:** para cada registro, valida linha existente, horário coerente (previsto não antes do programado em mais de 60 min; formato HH:MM), campos obrigatórios. Inválidos vão para lista com motivo.
4. **Deduplicação:** (veículo, ponto, minuto).
5. **Decisão por linha:** atraso médio > X **ou** intervalo entre ônibus > Y ⇒ CRÍTICA; entre limites ⇒ ATENÇÃO; senão OK. Limites iniciais (hipóteses documentadas): X = 10 / 5 min, Y = 30 / 20 min.
6. **Saída:** boletim JSON + HTML acessível com frases curtas para leitura em voz; `POST /boletim`.
7. **Exceções:** MVP fora (retry → boletim anterior marcado como desatualizado), GTFS ausente/inválido (cai para rede fictícia e avisa no boletim), dados inconsistentes (registrados por motivo), falha de publicação (salva local e sai com código de erro). Nenhuma falha silenciosa.
8. **Logs:** arquivo diário em `logs/` com data/hora, recebidos, válidos, inválidos por motivo, duplicados, linhas por status, sucesso/falha e mensagens de erro, sem chave nem dado pessoal (o veículo já vem em hash).

Testes (`tests/`): sucesso ponta a ponta contra um mock do backend; decisão CRÍTICA × ATENÇÃO × OK; falha com API fora (boletim desatualizado); GTFS ausente; duplicados e inválidos.

**Pessoa no circuito (IA responsável):** o robô sinaliza; o boletim diz "linhas para a equipe da gestora verificar" e os limites ficam em configuração, editáveis por uma pessoa.

**Estrutura do repositório RPA (slide 49):**
```
rpa/
  README.md  requirements.txt
  config/     monitoramento.yaml
  src/pf_rpa/ coleta, validacao, decisao, boletim, publicacao, robo (orquestrador), agendador
  tools/      mock_mvp.py (imita o Spring Boot para testes e demo sem backend)
  docs/       fluxo.bpmn, fluxo.png, relatorio.md (base do PDF com os 12 itens)
  assets/     prints e evidências
  logs/       amostras sem dados sensíveis
  tests/      pytest dos 3+ cenários
```

## 6. Mapeamento para os critérios oficiais

### GenAI (slide 30, 10 pontos)
| # | Critério | Pts | Onde fica |
|---|---|---|---|
| 01 | Tarefa e ~40 casos com gabarito, incluindo "não consta" | 0,5 | `avaliacao/perguntas.jsonl` (≥ 8 "não consta") |
| 02 | Base em trechos com fonte | 1,0 | `base/trechos.jsonl`, `base/fontes.csv`, notebook 01 |
| 03 | recall@1, recall@3 e limiar justificado | 1,0 | notebook 02 (curva de limiar × recusa correta) |
| 04 | JSON válido, citação e recusa | 2,0 | notebook 03, `src/pf_genai/gerador.py`, testes |
| 05 | Especialização (agente) × RAG simples | 2,0 | notebook 04, `src/pf_genai/agente.py` |
| 06 | Placar das 3 configurações interpretado | 2,0 | `avaliacao/placar.csv` + seção no relatório |
| 07 | 5 erros reais com causa e correção | 1,0 | `avaliacao/erros.md` (tirados do placar real) |
| 08 | README e reprodutibilidade | 0,5 | `README.md`, `requirements.txt`, script único de reprodução |
| Relatório (slide 31) | nomes/RMs, ficha técnica, diagrama, tabela da base, performance, 5 erros, conclusão e links | | `RELATORIO.md` |

### RPA (slides 47–50, 10 pontos)
| Critério | Pts | Evidência |
|---|---|---|
| Integração com o MVP | 1 | `POST /boletim` no Spring + tela de boletim no Angular; print e trecho do vídeo |
| Documentação | 2 | README + PDF com os 12 itens do slide 49 + BPMN |
| Desenvolvimento | 5 | 8 etapas: decisão, repetição, exceções, logs, testes |
| Vídeo (até 3 min) | 2 | Roteiro em `docs/roteiro_video.md` |

## 7. Ordem de desenvolvimento (11/11 → 19/11)

| Data | GenAI | RPA / integração |
|---|---|---|
| **11/11 (qua)** | Análise, contratos, estrutura | Robô completo contra o mock, testes |
| **12/11 (qui)** | Instalar Ollama + modelo; baixar e conferir documentos; notebook 01 | Exceções, logs, BPMN |
| **13/11 (sex)** | 40 perguntas com gabarito; índice; recall@1/@3; limiar | Agendamento; relatório RPA |
| **14/11 (sáb)** | Geração em JSON + recusa; API `/chat` | Passar contrato ao backend (`/historico`, `POST /boletim`) |
| **15/11 (dom)** | Agente; placar das 3 configurações | Marco do grupo: componente funcionando sozinho |
| **16/11 (seg)** | 5 erros reais; ajustes | Integração com o Spring real |
| **17/11 (ter)** | Integração `/chat` com Spring; relatório GenAI | Integração com MVP publicado; evidências |
| **18/11 (qua)** | Revisão de reprodutibilidade | Gravar vídeo RPA (3 min); PDF RPA |
| **19/11 (qui)** | Envio GenAI (links) | Envio RPA (PDF) até 23h55 |

## 8. Riscos e mitigação

| Risco | Mitigação |
|---|---|
| Backend Spring atrasar | Mock do backend no repositório RPA; GenAI testável direto na porta 8001 |
| Spring publicado na nuvem não alcança o Ollama no seu PC | Opções: (1) serviço GenAI em VM da nuvem do grupo (qwen2.5:3b roda em CPU com 4 GB RAM); (2) túnel temporário para a demo. Decidir com o integrante de DevOps até 15/11 |
| Páginas da SPTrans mudarem ou bloquearem download | Salvar cópia em `base/brutos/` com data de acesso; leis federais do Planalto como base mínima |
| Modelo 3B lento em CPU | `num_predict` curto, respostas de até 3 frases, cache de embeddings |
| Dados de histórico simulados | Boletim mostra `fonte_dados`; README e relatório declaram o que é simulado |

## 9. O que preciso de você

1. Autorização para instalar Ollama + qwen2.5:3b e as bibliotecas Python.
2. Nomes completos e RMs do grupo.
3. Quem constrói o backend Spring Boot e onde está o repositório, para alinhar `/historico`, `POST /boletim` e `LLM_URL`.
4. Confirmação das URLs da base de conhecimento (vou listar depois de verificar).

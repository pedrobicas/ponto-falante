# Ponto Falante · Robô de boletim de atrasos (RPA)

**FIAP · Global Solution 2026.2 · CitizenTech · Robotic Process Automation**
Atividade: *Do Processo Manual à Automação Inteligente* · Professores: Bruno Diniz e Cibele Ribeiro

## Integrantes

| Nome completo | RM |
|---|---|
| Pedro Henrique Bicas Couto | RM 99534 |
| Bryan Willian | RM 551305 |
| Felipe Masera Terra | RM 99405 |
| Gabriel Fernandes Doms | RM 98630 |
| Lucas Vassão Braga | RM 98607 |

## O problema

O **Ponto Falante** mostra e fala a previsão dos próximos ônibus para pessoas com deficiência visual e idosos em São Paulo. Para avisar o passageiro de que uma linha anda atrasando, alguém teria de acompanhar as linhas todos os dias, anotar os atrasos, comparar com o horário programado e escrever um aviso. É um trabalho manual, repetitivo e fácil de esquecer.

**O robô faz isso sozinho, todo dia às 06:00:** busca as passagens do dia anterior no MVP, valida e limpa os dados, decide quais linhas estão críticas e publica um boletim em linguagem simples, que a tela do MVP lê em voz alta.

## Como funciona

![Fluxo BPMN](docs/fluxo.png)

Fluxo completo em [`docs/fluxo.bpmn`](docs/fluxo.bpmn) (abre em https://demo.bpmn.io).

1. **Entrada:** `config/monitoramento.yaml` (linhas e pontos monitorados, limites de decisão) e rede GTFS (SPTrans real, se baixada, ou rede fictícia documentada).
2. **Coleta:** `GET /historico?data=` do MVP, com 3 tentativas e espera crescente (2 s, 4 s, 8 s).
3. **Validação (repetição sobre cada registro):** campos obrigatórios, linha existente no GTFS, horário no formato HH:MM, horário coerente (não mais que 60 min adiantado nem 180 min atrasado). Cada inválido é guardado com o motivo.
4. **Deduplicação:** mesmo veículo, mesmo ponto, mesmo minuto.
5. **Decisão (por linha):**

| Status | Regra |
|---|---|
| CRÍTICA | atraso médio > 10 min **ou** maior espera entre ônibus > 30 min |
| ATENÇÃO | atraso médio > 5 min **ou** maior espera > 20 min |
| OK | abaixo dos dois limites |
| SEM DADOS | menos de 3 passagens válidas (o robô não decide no escuro) |

   Os limites são hipóteses iniciais, ficam no YAML e podem ser ajustados por uma pessoa da gestora sem mexer no código. Ônibus adiantado conta como atraso zero (não "compensa" atraso de outro), e buracos que a própria tabela programada prevê (por exemplo, entre o pico da manhã e o da tarde) não contam como espera.
6. **Saída:** boletim JSON + HTML acessível com `resumo_falado`, publicado com `POST /boletim` (cabeçalho `X-API-Key`). O MVP mostra em `GET /boletim`.
7. **Exceções** (nenhuma falha silenciosa):

| Situação | O que o robô faz | Código de saída |
|---|---|---|
| MVP fora do ar ao ler o histórico | 3 tentativas com backoff; republica o último boletim marcado como **desatualizado**, com o motivo | 2 |
| Publicação recusada ou MVP fora ao publicar | Salva o boletim em `saida/` e registra a falha | 1 |
| GTFS real ausente ou inválido | Usa a rede fictícia e avisa no boletim | 0 |
| Nenhuma rede GTFS utilizável | Para e registra erro | 3 |
| Histórico vazio ou mais da metade inconsistente | Gera o boletim com aviso de baixa confiabilidade | 0 |
| Chave inválida (401/403) | Não insiste e registra "confira RPA_API_KEY" | 1 |

8. **Logs e auditoria:** `logs/rpa_AAAA-MM-DD.log` (data/hora, nível, etapa, mensagem) e `logs/auditoria.jsonl` (um resumo por execução: recebidos, válidos, inválidos, duplicados, linhas por status, fonte dos dados, erros, duração). A chave é mascarada automaticamente. Amostras reais estão em [`logs/`](logs/).

## Integração com o MVP

Contrato em [`../contratos/openapi-integracao.yaml`](../contratos/openapi-integracao.yaml) e guia para o backend Spring Boot em [`../contratos/GUIA_BACKEND_SPRING.md`](../contratos/GUIA_BACKEND_SPRING.md).

```
Robô  --GET /historico?data=-->  Spring Boot (PostgreSQL)
Robô  --POST /boletim (X-API-Key)-->  Spring Boot  --GET /boletim-->  Angular (lê em voz alta)
```

O boletim sempre informa de onde vieram os dados (`fonte_dados`: Olho Vivo em tempo real ou simulador) e se a rede é o GTFS real ou a fictícia.

## Como rodar

Pré-requisito: Python 3.11+.

```bash
cd rpa
python -m venv .venv
.venv\Scripts\activate          # Linux/Mac: source .venv/bin/activate
pip install -r requirements.txt
```

**Sem backend (mock com dados simulados):**
```bash
uvicorn tools.mock_mvp:app --port 8080
```
Em outro terminal:
```bash
set PYTHONPATH=src              # Linux/Mac: export PYTHONPATH=src
python -m pf_rpa.robo --data 2026-11-12
```

**Com o backend real:** defina `MVP_URL` (ex.: `https://ponto-falante.exemplo/api`) e `RPA_API_KEY` (mesmo valor do backend) como variáveis de ambiente. Nunca grave a chave em arquivo versionado.

**Agendado (todo dia às 06:00):**
```bash
python -m pf_rpa.agendador
```
Ou no Agendador de Tarefas do Windows / cron: `python -m pf_rpa.robo` (sem `--data`, usa o dia anterior).

**Simular a queda do MVP (para a demonstração):**
```bash
curl -X POST "http://127.0.0.1:8080/admin/falha?ativo=true"
```

## Testes

```bash
python -m pytest -v
```
14 testes, incluindo os 3 cenários exigidos:

| Cenário | Teste | Resultado esperado |
|---|---|---|
| Sucesso | `test_sucesso_ponta_a_ponta` | boletim publicado e igual ao `GET /boletim`; inválidos e duplicados barrados; auditoria "sucesso" |
| Decisão | `test_decisao_com_dados_do_mock`, `test_regra_de_decisao_limites`, `test_intervalo_ignora_buraco_programado...` | 1001-10 CRÍTICA, 1002-10 ATENÇÃO, 1004-10 OK; limites exatos |
| Falha | `test_falha_mvp_fora_mantem_boletim_anterior_desatualizado`, `test_falha_total_sem_boletim_anterior`, `test_retry_com_backoff_exponencial` | boletim anterior marcado como desatualizado; esperas 2, 4, 8 s |

Evidências em [`tests/EVIDENCIAS.md`](tests/EVIDENCIAS.md).

## Estrutura

```
README.md          este arquivo
requirements.txt   dependências
config/            monitoramento.yaml (linhas, pontos, limites, horário)
data/              gtfs_ficticio/ (rede fictícia) e gtfs_sptrans/ (GTFS real, opcional, fora do Git)
src/pf_rpa/        robo.py (orquestrador), cliente_mvp.py, gtfs.py, validacao.py, decisao.py,
                   boletim.py, armazenamento.py, registro.py, agendador.py
tools/mock_mvp.py  imita o backend para testes e demo sem o Spring Boot
docs/              fluxo.bpmn, fluxo.png, relatorio.md (base do PDF), roteiro_video.md
assets/            exemplos de boletim e prints
logs/              amostras de logs sem dados sensíveis
tests/             testes automatizados e evidências
```

## Dados simulados (declaração obrigatória)

Enquanto o backend não estiver publicado, o histórico vem do **mock** (`tools/mock_mvp.py`), que gera passagens com semente fixa por data, em uma **rede fictícia de 5 linhas e 20 pontos** (nomes terminados em "FICTÍCIA"). O mock injeta de propósito cerca de 3% de registros inválidos e 3% de duplicados para provar a validação. Com o MVP real, o robô usa o mesmo código e o boletim mostra se os dados vieram do Olho Vivo (tempo real) ou do simulador do grupo.

## Segurança e LGPD

- Nenhum dado pessoal: o robô processa passagens de ônibus; o identificador do veículo já chega anonimizado (hash).
- `RPA_API_KEY` e `MVP_URL` só em variáveis de ambiente; o filtro de log mascara a chave.
- Logs guardam contagens e mensagens técnicas, nunca o conteúdo bruto dos registros.
- Pessoa no circuito: o boletim sinaliza, mas recomenda que a equipe da gestora confira as linhas críticas antes de agir.

## Links

- Repositório: [preencher]
- Vídeo (até 3 min): [preencher]

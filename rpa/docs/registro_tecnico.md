# Registro técnico detalhado · RPA

> Documento interno da equipe. Guarda o histórico de execuções, a investigação da cobertura e os detalhes operacionais
> que antes ficavam no relatório. O relatório acadêmico entregue aos professores é [relatorio.md](relatorio.md).

## Relatório técnico (versão de 15/11/2026, preservada)

**Ponto Falante · FIAP Global Solution 2026.2 · CitizenTech**
Atividade: *Do Processo Manual à Automação Inteligente* · Professores Bruno Diniz e Cibele Ribeiro



## 1. Integrantes

| Nome completo | RM |
|---|---|
| Pedro Henrique Bicas Couto | RM 99534 |
| Bryan Willian | RM 551305 |
| Felipe Masera Terra | RM 99405 |
| Gabriel Fernandes Doms | RM 98630 |
| Lucas Vassão Braga | RM 98607 |

## 2. A CitizenTech e o problema resolvido

O **Ponto Falante** é uma plataforma de acessibilidade para usuários de ônibus de São Paulo, especialmente pessoas com deficiência visual e idosos, que têm dificuldade de ler o letreiro e de usar apps de transporte. O MVP (Angular + Spring Boot + PostgreSQL, publicado em https://ponto-falante.onrender.com) mostra e fala a previsão real dos próximos ônibus (SPTrans), tem um assistente de horários e de regras de gratuidade e um boletim diário das linhas.

**Problema operacional:** para avisar os passageiros de que uma linha anda com espera longa, alguém precisaria consultar os pontos várias vezes por dia, anotar as previsões, comparar e escrever um aviso. É manual, repetitivo, sujeito a esquecimento e não escala.

## 3. Objetivo da automação e benefício ao cidadão

**Objetivo:** coletar previsões reais ao longo do dia e publicar todo dia, sem intervenção humana, um boletim por linha com dados validados, decisão explicável e origem declarada.

**Benefício:** o passageiro com baixa visão ouve, na tela do MVP, quais linhas tiveram espera longa prevista e pode sair mais cedo ou escolher outra linha. A gestora de transporte recebe a lista de linhas em atenção para conferir.

## 4. Processo e desenho do fluxo

![Fluxo BPMN](fluxo.png)

Arquivo editável: `docs/fluxo.bpmn` (BPMN 2.0, gerado por `docs/gerar_fluxo_bpmn.py`). São dois robôs, cada um com o seu agendamento.

| Etapa | Entrada | Processamento | Saída |
|---|---|---|---|
| Coleta (8 vezes por dia) | `config/monitoramento.yaml` (6 pontos) | `GET /api/pontos/{codigo}/previsoes` no MVP; só respostas com `fonte = OLHO_VIVO` viram amostra | `POST /api/rpa/amostras` com `X-API-Key`; lote pendente em `saida/pendentes/` se falhar |
| Início do boletim (06:00) | Agendamento diário | Carrega a configuração | Configuração validada |
| Leitura | `GET /api/rpa/amostras?data=` | 3 tentativas, com esperas de 2 s e 4 s entre elas | Amostras do dia anterior |
| Validação (laço) | Cada amostra | Campos, período, ponto no escopo, previsões de 0 a 120 min, sentidos separados | Válidas + inválidas com motivo |
| Deduplicação | Válidas | Mesmo ponto e mesmo horário de consulta contam uma vez | Amostras únicas |
| Decisão (laço) | Cada linha | Espera típica, maior espera e consultas sem ônibus previsto → CRÍTICA, ATENÇÃO, OK ou SEM DADOS | Situação por linha |
| Boletim | Situações | JSON + HTML + frase para voz, com a categoria (ESTIMADO, SIMULADO ou INDISPONIVEL) | `saida/boletim_AAAA-MM-DD.*` |
| Publicação | Boletim | `POST /boletim` com `X-API-Key`; o backend confere a proveniência | `GET /boletim` e tela do MVP |
| Auditoria | Resultado | Log + `auditoria.jsonl` | Evidência da execução |

## 5. Tecnologias e justificativa

| Tecnologia | Uso | Por quê |
|---|---|---|
| Python 3.11 | Robôs | Aceito no slide 47; versionável e testável; o grupo já usa Python na IA |
| requests | HTTP com retry | Simples e padrão de mercado |
| PyYAML | Configuração | Regras e pontos editáveis sem mexer no código |
| Jinja2 | HTML do boletim | Escapa conteúdo automaticamente (segurança) |
| GitHub Actions | Agendamento | Gratuito; `rpa-coleta.yml` e `rpa-diario.yml`, com segredos fora do código |
| pytest | Testes | Cenários reproduzíveis e automáticos |
| FastAPI (mock) | Testes e demo sem backend | Mesmo contrato OpenAPI do MVP |
| bpmn.io | Fluxo | Padrão BPMN 2.0 exigido |

## 6. Regras de negócio, decisões e processamento

A Olho Vivo informa **previsões** de chegada, não chegadas observadas, e o GTFS da SPTrans descreve a maioria das linhas por frequência. Uma previsão sozinha não prova atraso. Por isso o boletim é **ESTIMADO** e mede o que o dado real sustenta: a espera prevista em cada consulta.

| Situação | Regra (limites no YAML, seção `regras_estimadas`) |
|---|---|
| CRÍTICA | espera típica prevista > 30 min |
| ATENÇÃO | espera típica > 20 min, **ou** maior espera > 30 min, **ou** sem ônibus previsto em 50% ou mais das consultas |
| OK | abaixo dos limites |
| SEM DADOS | menos de 3 consultas com previsão da linha (o robô não decide no escuro) |

- Se menos de 50% das janelas de coleta do dia foram cobertas, o boletim avisa "amostragem parcial".
- Sentidos opostos de uma linha não se somam (não reduzem a espera de quem está no ponto).
- Sem amostra real, o boletim sai como **INDISPONÍVEL**. Só com o MVP em modo demonstração o robô usa o histórico simulado, sempre rotulado. Real e simulado nunca se misturam.
- Os limites são hipóteses iniciais documentadas e ficam no YAML, para a gestora ajustar.

Execuções reais de 13/11/2026:

- Coleta em produção (GitHub Actions): 6 pontos consultados, 111 ônibus previstos em 46 linhas-ponto, 6 amostras gravadas, 0 rejeitadas.
- Boletim do dia 12/11 publicado como **INDISPONÍVEL**: a coleta ainda não existia nesse dia, e o robô não inventou números.
- Boletim do dia 13/11 (execução de 14/11): 17 consultas válidas, 24 linhas avaliadas, 6 em **ATENÇÃO** e 18 dentro dos limites, com aviso de "amostragem parcial" (17 de 48 janelas). O agendador gratuito do GitHub atrasa e pula execuções, e o boletim informa a cobertura real.
- Execução local contra a SPTrans real: 6 amostras e boletim ESTIMADO com aviso de "amostragem parcial" (`logs/rpa_2026-11-13.log`).
- Boletim do dia 14/11 (execução de 15/11): 11 consultas válidas de 48 (22,9%), também publicado com o aviso de amostragem parcial.

**Investigação da cobertura (15/11/2026).** O cron previa 8 coletas por dia, mas o histórico do GitHub Actions mostra
só 3 execuções para o dia 13 (09h54, 16h31 e 21h51 em São Paulo; a primeira foi disparada à mão) e 2 para o dia 14
(13h30 e 19h15). As demais simplesmente não aparecem no histórico (exportado em
`docs/evidencias/rpa_execucoes_20261115.json`), e o `rpa-diario` das 06h chegou a rodar com até 8 h de atraso. A
explicação mais provável é o comportamento documentado do GitHub: agendamentos `schedule` podem atrasar ou não rodar
em horários de alta carga. Não temos log do lado do GitHub que prove o descarte de cada horário. Cada coleta que rodou consultou os 6 pontos. Das 18 consultas do dia 13, 17 foram válidas: às 21h52 a SPTrans
não tinha previsão para o ponto 630015011 (resposta 404 "sem previsão"), e um HTTP 503 às 16h33 foi recuperado na
segunda tentativa. No dia 14, a consulta das 19h15 ao ponto 340015324 também voltou "sem previsão". Os logs das
execuções (artefatos `rpa-coleta-*`) não mostram falha de persistência nem de publicação. A causa da cobertura baixa
é a falta de execuções agendadas, não a coleta em si.

Correções: a coleta passou para o minuto 17 de cada horário, longe da virada da hora, que o GitHub aponta como o horário de
maior carga. O script `scripts/genai/garantir-rpa.ps1`, iniciado junto com a GenAI no PC do projeto, confere a última
execução a cada 15 minutos. Para cada horário do cron, ele espera 25 minutos de tolerância e, se até o fim da janela
de 2 horas daquele horário nenhuma execução tiver sido criada, dispara o mesmo workflow pelo `gh workflow run` (no
máximo 3 tentativas por horário). Para o boletim, exige uma execução bem-sucedida no dia depois das 07h; falhas e
cancelamentos contam como tentativa, também com limite de 3. O script não coleta dados e
não usa os segredos do RPA. O boletim continua informando a cobertura real e nunca completa as lacunas.

## 7. Tratamento de exceções e recuperação

| Exceção | Tratamento | Saída |
|---|---|---|
| MVP fora ao ler as amostras | 3 tentativas com backoff; republica o último boletim marcado como **desatualizado**, com o motivo | 2 |
| Publicação recusada ou MVP fora ao publicar | Salva o boletim em `saida/` e registra a falha | 1 |
| Coletor sem acesso ao MVP | Guarda o lote em `saida/pendentes/` e reenvia na execução seguinte | 1 |
| Chave inválida (401/403) | Não insiste e orienta conferir `RPA_API_KEY` | 1 |
| Resposta fora do contrato | Descarta a consulta e registra o motivo | 0 |
| Mais da metade das amostras inconsistente | Gera o boletim com aviso de baixa confiabilidade | 0 |

Nenhuma falha é silenciosa: toda exceção aparece no log, na auditoria e, quando afeta o cidadão, no próprio boletim.

## 8. Logs e evidências de auditoria

- `logs/rpa_AAAA-MM-DD.log`: data/hora, nível, etapa e mensagem (início, recebidos, validação por motivo, decisão por linha, publicação, fim com código).
- `logs/auditoria.jsonl`: um JSON por execução com status, código de saída, estatísticas, linhas por situação, fonte dos dados, erros e duração.
- Sem dados sensíveis: o veículo chega anonimizado e a chave é mascarada por filtro.

Trecho real da coleta em produção (13/11/2026, GitHub Actions):
```
INFO | pf_rpa.coletor | Ponto 260015039: 44 ônibus previstos em 16 linhas (consultado em 2026-11-13T09:54:15-03:00)
INFO | pf_rpa.coletor | Ponto 340015323: 25 ônibus previstos em 6 linhas (consultado em 2026-11-13T09:54:17-03:00)
INFO | pf_rpa.coletor | Envio: 6 gravadas, 0 duplicadas, 0 rejeitadas
```

Trecho real do boletim sem amostras do dia:
```
INFO | pf_rpa.robo | Nenhuma amostra real válida para 2026-11-12 | modo do MVP: REAL | fallback simulado: somente_demo -> INDISPONIVEL
INFO | pf_rpa.robo | Boletim publicado no MVP (POST /boletim)
```

## 9. Integração com o MVP

O resultado é consumido por outro componente via API. O coletor lê as previsões no backend Spring Boot (que consulta a SPTrans pelo gateway da Prefeitura) e grava as amostras em PostgreSQL (`POST /api/rpa/amostras`). O robô do boletim lê essas amostras e publica em `POST /boletim`. O backend confere se a proveniência declarada bate com as amostras gravadas, guarda o boletim e o serve em `GET /boletim` para a tela do Angular, que lê o `resumo_falado` em voz alta e mostra o selo **Estimado**, **Simulado** ou **Indisponível**. Contrato: `contratos/openapi-integracao.yaml`.

Execuções no GitHub Actions: https://github.com/pedrobicas/ponto-falante/actions/workflows/rpa-coleta.yml e https://github.com/pedrobicas/ponto-falante/actions/workflows/rpa-diario.yml. Tela `/boletim` do MVP publicado em 14/11/2026, com o primeiro boletim estimado a partir de consultas reais:

![Boletim de 13/11/2026 no MVP publicado, com o selo Estimado](../assets/boletim_producao_20261114.png)

## 10. Testes realizados

53 testes automatizados, todos passando em 15/11/2026: os 46 da validação de 14/11 e 7 novos de falha (timeout com
backoff, resposta vazia ou em HTML, 503 seguido de recuperação e reexecução no mesmo dia sem duplicar). Cenários e
saídas em `tests/EVIDENCIAS.md`; a suíte também roda na CI a cada push.

| Tipo | Cenário | Resultado |
|---|---|---|
| Sucesso com dado real | Amostras reais → boletim; coletor com sucesso parcial | Boletim ESTIMADO; o coletor grava só amostras da SPTrans |
| Sucesso (simulado rotulado) | Ponta a ponta contra o mock | Boletim publicado e igual ao `GET /boletim` |
| Decisão | Perfis de espera e limites exatos | CRÍTICA, ATENÇÃO, OK e SEM DADOS conferidos |
| Sem dado real | MVP real sem amostras; coletor diante de dado de demonstração | INDISPONÍVEL, sem números inventados; simulação nunca gravada como real |
| Falha | MVP fora, chave recusada, publicação fora, retry | Boletim anterior marcado como desatualizado; lote pendente reenviado; 3 tentativas com esperas de 2 s e 4 s |
| Segurança | Chave no log | Mascarada |

**Evidência do vídeo (gravado em 14/11/2026, das 23:08 às 23:19):** todos os comandos rodaram durante a gravação. A coleta real em modo somente leitura consultou 6 pontos pela API publicada e encontrou 27 ônibus previstos, sem gravar nada. O histórico do GitHub Actions mostra as coletas e os boletins agendados. A execução completa contra o MVP local, rotulada **SIMULADO**, recebeu 349 registros: 330 válidos, 9 inválidos e 10 duplicados. Ela classificou 1 linha como CRÍTICA, 2 em ATENÇÃO e 2 OK, gerou JSON e HTML e publicou com código 0. A falha foi provocada no mesmo MVP local: HTTP 503, 3 tentativas com esperas observadas de 2 s e 4 s, boletim anterior republicado como **desatualizado**, código 2 e registro na auditoria. A produção foi só lida: boletim de 13/11 com 17 consultas, 35,4% de cobertura, 24 linhas e 6 em atenção, também citado pela assistente. Registro: `docs/evidencias/video_rpa_20261115.md`. A gravação não incluiu a suíte de testes, executada à parte.

## 11. Segurança e LGPD

- Não há dado pessoal no processo: só previsões de ônibus; veículo anonimizado por hash.
- `RPA_API_KEY` e `MVP_URL` só em variáveis de ambiente e nos Secrets do GitHub; `.gitignore` bloqueia `.env`.
- Publicação e gravação autenticadas por chave; HTML gerado com escape automático.
- Pessoa no circuito: o boletim recomenda que a gestora confira as linhas em atenção antes de agir.
- **Origem dos dados:** real (consultas à SPTrans com data e hora), estimado (esperas calculadas a partir de previsões, nunca atrasos medidos), simulado (só em modo demonstração, sempre rotulado) e indisponível (sem dados, sem números).

## 12. Links

- Repositório GitHub: https://github.com/pedrobicas/ponto-falante (privado, pasta `rpa/`)
- URL pública do repositório sanitizado: **[PENDENTE: URL_REPOSITORIO_PUBLICO]**.
- MVP publicado: https://ponto-falante.onrender.com/boletim
- Vídeo local: `entregaveis/Ponto_Falante_RPA.mp4`, **2 min 12 s (132 s, abaixo do limite de 180 s)**, 1920 x 1080, sem áudio e sem música, pronto para narração.
- Roteiro final: `entregaveis/ROTEIRO_RPA.md`.
- URL pública do vídeo: **[PENDENTE: URL_VIDEO_RPA]**. O repositório segue privado; nenhuma entrega no Teams foi realizada.

O vídeo mostra a execução ponta a ponta do robô de boletim no MVP local, do comando à publicação com código 0, entre 01:00 e 01:21. A coleta real, o agendamento e o boletim publicado são trechos de produção identificados pelo selo DADOS REAIS ou ESTIMADO. Entre 01:21 e 01:44 aparecem a falha, a recuperação e a auditoria. O material atende ao conteúdo demonstrativo das pp. 46-50 do enunciado; a aceitação e a nota cabem à avaliação docente.

# Relatório técnico · Robotic Process Automation

**Ponto Falante · FIAP Global Solution 2026.2 · CitizenTech**
Atividade: *Do Processo Manual à Automação Inteligente* · Professores Bruno Diniz e Cibele Ribeiro

> Este arquivo é a base do PDF de entrega (exportar com os prints de `assets/`). A ordem segue os 12 itens do slide 49.

## 1. Integrantes

| Nome completo | RM |
|---|---|
| Pedro Henrique Bicas Couto | RM 99534 |
| Bryan Willian | RM 551305 |
| Felipe Masera Terra | RM 99405 |
| Gabriel Fernandes Doms | RM 98630 |
| Lucas Vassão Braga | RM 98607 |

## 2. A CitizenTech e o problema resolvido

O **Ponto Falante** é uma plataforma de acessibilidade para usuários de ônibus de São Paulo, especialmente pessoas com deficiência visual e idosos, que têm dificuldade de ler o letreiro e de usar apps de transporte. O MVP (Angular + Spring Boot + PostgreSQL) mostra e fala a previsão dos próximos ônibus, reconhece a linha pelo letreiro e tem um assistente de IA.

**Problema operacional:** para avisar os passageiros de que uma linha anda atrasando, alguém precisaria acompanhar as linhas todo dia, anotar os atrasos, comparar com o programado e escrever um aviso. É manual, repetitivo, sujeito a esquecimento e não escala para centenas de linhas.

## 3. Objetivo da automação e benefício ao cidadão

**Objetivo:** gerar e publicar todo dia, sem intervenção humana, um boletim de atrasos por linha, com dados validados e decisão explicável.

**Benefício:** o passageiro com baixa visão ouve, na tela do MVP, quais linhas estão com atraso forte e pode sair mais cedo ou escolher outra linha. A gestora de transporte recebe a lista de linhas críticas para agir.

## 4. Processo e desenho do fluxo

![Fluxo BPMN](fluxo.png)

Arquivo editável: `docs/fluxo.bpmn`.

| Etapa | Entrada | Processamento | Saída |
|---|---|---|---|
| Início | Agendamento diário 06:00 | Carrega `config/monitoramento.yaml` | Configuração validada |
| Rede | GTFS SPTrans ou rede fictícia | Lê `routes.txt` e `stops.txt` | Conjunto de linhas e pontos válidos |
| Coleta | `GET /historico?data=` | 3 tentativas com backoff 2/4/8 s | Lista de passagens |
| Validação (laço) | Cada passagem | Campos, linha, formato e coerência do horário | Válidos + inválidos com motivo |
| Deduplicação | Válidos | Chave veículo + ponto + minuto | Passagens únicas |
| Decisão (laço) | Cada linha monitorada | Atraso médio e maior espera → CRÍTICA/ATENÇÃO/OK/SEM DADOS | Situação por linha |
| Boletim | Situações | JSON + HTML + frase para voz | `saida/boletim_AAAA-MM-DD.*` |
| Publicação | Boletim | `POST /boletim` com `X-API-Key` | `GET /boletim` no MVP |
| Auditoria | Resultado | Log + `auditoria.jsonl` | Evidência da execução |

## 5. Tecnologias e justificativa

| Tecnologia | Uso | Por quê |
|---|---|---|
| Python 3.11 | Robô | Aceito no slide 47; versionável e testável; o grupo já usa Python na IA |
| requests | HTTP com retry | Simples e padrão de mercado |
| PyYAML | Configuração | Regras editáveis por uma pessoa sem mexer no código |
| Jinja2 | HTML do boletim | Escapa conteúdo automaticamente (segurança) |
| schedule | Agendamento | Leve; em produção o mesmo comando vai para cron / Agendador do Windows |
| pytest | Testes | Cenários reproduzíveis e automáticos |
| FastAPI + uvicorn | Mock do MVP | Permite testar e demonstrar sem depender do backend |
| bpmn.io | Fluxo | Padrão BPMN 2.0 exigido |

## 6. Regras de negócio, decisões e processamento

- **Linha CRÍTICA:** atraso médio > 10 min **ou** maior espera entre ônibus > 30 min.
- **ATENÇÃO:** atraso médio > 5 min **ou** maior espera > 20 min.
- **OK:** abaixo dos limites. **SEM DADOS:** menos de 3 passagens válidas.
- Ônibus adiantado conta como atraso zero: para quem espera, adiantado também é ônibus perdido.
- Buracos previstos na própria tabela (entre picos, madrugada) não contam como espera.
- Registro inválido: campo obrigatório vazio, fonte desconhecida, linha que não existe no GTFS, horário fora do formato, previsto mais de 60 min antes ou mais de 180 min depois do programado.
- Os limites são hipóteses iniciais documentadas e ficam no YAML, para a gestora ajustar.

Resultado de uma execução real (dados simulados de 12/11/2026): 349 recebidos, 330 válidos, 9 inválidos (linha inexistente, campo vazio, horário incoerente), 10 duplicados; 1 linha CRÍTICA (1001-10, atraso médio 14,7 min), 2 ATENÇÃO, 2 OK. Exemplo completo em `assets/exemplo_boletim.json`.

## 7. Tratamento de exceções e recuperação

| Exceção | Tratamento | Código |
|---|---|---|
| MVP fora ao ler histórico | Retry com backoff; republica o último boletim marcado como desatualizado | 2 |
| MVP fora ao publicar / recusa | Salva cópia local e registra a falha | 1 |
| Chave inválida | Não repete (não adianta) e orienta conferir `RPA_API_KEY` | 1 |
| GTFS real ausente/inválido | Usa rede fictícia e avisa no boletim | 0 |
| Nenhuma rede utilizável | Encerra com erro registrado | 3 |
| Histórico vazio / >50% inconsistente | Gera boletim com aviso de baixa confiabilidade | 0 |

Nenhuma falha é silenciosa: toda exceção aparece no log, na auditoria e, quando afeta o cidadão, no próprio boletim.

## 8. Logs e evidências de auditoria

- `logs/rpa_AAAA-MM-DD.log`: data/hora, nível, módulo, mensagem (início, recebidos, validação por motivo, decisão por linha, publicação, fim com código).
- `logs/auditoria.jsonl`: um JSON por execução com status, código de saída, estatísticas, linhas por status, fonte dos dados, erros e duração.
- Sem dados sensíveis: o veículo chega anonimizado e a chave é mascarada por filtro.

Trecho real (MVP fora do ar):
```
WARNING | pf_rpa.mvp  | GET /historico?data=2026-11-13 falhou (tentativa 1/3): HTTP 503
WARNING | pf_rpa.mvp  | GET /historico?data=2026-11-13 falhou (tentativa 2/3): HTTP 503
WARNING | pf_rpa.mvp  | GET /historico?data=2026-11-13 falhou (tentativa 3/3): HTTP 503
ERROR   | pf_rpa.robo | MVP indisponível para leitura do histórico: ...
WARNING | pf_rpa.robo | Republicando o boletim de 2026-11-12 marcado como desatualizado
```

## 9. Integração com o MVP

O resultado é consumido por outro componente via API: o robô publica em `POST /boletim` do backend Spring Boot, que grava em PostgreSQL (tabela `boletim`, JSONB) e serve `GET /boletim` para a tela do Angular, que lê `resumo_falado` em voz alta e mostra o selo de origem dos dados. Contrato: `contratos/openapi-integracao.yaml`. [Inserir prints da tela de boletim do MVP e da resposta de `GET /boletim`.]

## 10. Testes realizados

14 testes automatizados (`python -m pytest -v`), todos passando. Evidências em `tests/EVIDENCIAS.md`.

| Tipo | Cenário | Resultado |
|---|---|---|
| Sucesso | Execução ponta a ponta contra o mock | Boletim publicado e idêntico ao `GET /boletim` |
| Decisão | Perfis de atraso do mock | 1001-10 CRÍTICA, 1002-10 ATENÇÃO, 1004-10 OK |
| Decisão | Limites exatos e espera por ônibus que sumiu | Regras conferidas |
| Falha | MVP fora | Boletim anterior republicado como desatualizado |
| Falha | MVP e publicação fora, sem boletim anterior | Aviso de indisponibilidade salvo localmente |
| Falha | Retry | Esperas 2, 4, 8 s |
| Segurança | Chave no log | Mascarada |

## 11. Segurança e LGPD

- Não há dado pessoal no processo: só passagens de ônibus; veículo anonimizado por hash.
- Credenciais (`RPA_API_KEY`) e endereço do MVP só em variáveis de ambiente; `.gitignore` bloqueia `.env`.
- Publicação autenticada por chave; HTML gerado com escape automático (evita injeção na tela).
- Pessoa no circuito: o boletim recomenda que a gestora confira as linhas críticas antes de agir.
- **Origem dos dados:** nesta entrega, o histórico de entrada é **simulado** (mock com rede fictícia de 5 linhas e 20 pontos, semente fixa). Com o MVP real, o mesmo código processa dados do Olho Vivo ou do simulador do grupo, e o boletim informa a fonte.

## 12. Links

- Repositório GitHub: [preencher]
- Vídeo demonstrativo (até 3 min): [preencher]

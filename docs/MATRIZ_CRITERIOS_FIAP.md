# Matriz de critérios oficiais · GenAI, RPA e Secure DevOps

Fonte: `Global_Solution_2026_2_CitizenTech_FIAP.pdf` (enunciado oficial), lido em 15/11/2026. GenAI: pp. 28–31; RPA:
pp. 45–50; Secure DevOps: pp. 51–53. Prazo comum: **19/11/2026, 23h55**, no Teams de cada disciplina.
Situação: **OK** (cumprido com evidência), **PENDENTE** (depende de ação do integrante) ou **LACUNA** (não existe no repositório).

## Generative AI for Engineering (10 pontos)

Entrega: links do repositório público no Teams; relatório no GitHub.

| # | Exigido | Onde está | Como foi testado / evidência | Situação |
|---|---|---|---|---|
| 01 (0,5) | Tarefa da IA e casos de teste com gabarito, incluindo "não consta" | `genai/RELATORIO.md` §2 e §6; `genai/avaliacao/perguntas_dev.jsonl`, `perguntas.jsonl`, `v2/`, `v3/` | Conjuntos separados DEV/teste; notebook 02 confere que não compartilham trechos | OK |
| 02 (1,0) | Base de conhecimento em trechos com fonte | `genai/base/` (244 trechos, `fontes.csv`, `tabela_base.csv`) | Notebook 01 com saídas; §5 do relatório | OK |
| 03 (1,0) | Recall@1 e @3 medidos, limiar justificado | Notebook 02; `avaliacao/recall_dev.csv`, `recall_teste_final.csv`, `curva_limiar_dev.*` | Escolha no DEV (limiar 0,86), medida final no teste; §7.1 | OK |
| 04 (2,0) | Geração fundamentada: JSON válido, citação e recusa | `genai/src/pf_genai/`, `genai/api/`; notebook 03 | 155 testes `pytest` (15/11: 155 aprovados); placar com 100% JSON válido e citações válidas | OK |
| 05 (2,0) | Especialização (LoRA ou agente) comparada ao RAG simples | Agente em 5 passos; §4, §7.2, §11–13 | Placar das três configurações no teste fechado, rodado uma vez | OK |
| 06 (2,0) | Placar das três configurações, interpretado | `avaliacao/placar_teste.csv`, `placar_teste.png`; §7.2–7.3 | Leitura honesta inclui onde a v2/v3 não generalizou | OK |
| 07 (1,0) | 5 erros reais com proposta de correção | `avaliacao/erros.md`; §8 e §12 | Erros tirados do teste, com causa e correção | OK |
| 08 (0,5) | README e reprodutibilidade | `genai/README.md`; `scripts/genai/` | Comandos de reprodução; CI roda os testes a cada push | OK |
| Rel. 01 | Nome completo e RM | §1 do relatório | `VALIDACAO_DOCUMENTOS.json`: `rms_presentes = true` | OK |
| Rel. 02–06 | Ficha técnica, diagramas, tabela da base, performance, 5 erros | §2, §3, §5, §7, §8 | PDF revisado página a página em 15/11 | OK |
| Rel. 07 | Conclusão técnica e links do repositório e do vídeo | §9 e §14 | Links do vídeo e do repositório público ainda são `[PENDENTE: URL_VIDEO_GENAI]` e `[PENDENTE: URL_REPOSITORIO_PUBLICO]` | PENDENTE |
| Repo | Repositório **público** com `notebooks/`, `base/`, `avaliacao/`, `README.md` | Estrutura existe em `genai/` | O repositório atual é privado; a cópia pública sanitizada depende de autorização | PENDENTE |
| Integração | Rodar integrada ao produto, segura e conforme a LGPD | `/api/chat` no MVP publicado; chave de serviço; sem persistência de perguntas | Validação de operação em `docs/evidencias/genai_operacao_20261115.md` | OK, com o PC ligado |

## Robotic Process Automation (10 pontos)

Entrega: PDF com todas as informações, link do vídeo (até 3 min) e do Git, na tarefa do Teams.

| Exigido | Onde está | Como foi testado / evidência | Situação |
|---|---|---|---|
| 01 Mapeamento do processo (BPMN) | `rpa/docs/fluxo.bpmn`, `fluxo.png`; PDF §4 e anexo em paisagem (pp. 9–13) | Recortes conferidos visualmente; fluxo bate com o código (3 tentativas, republicação, pendentes, publicação) | OK |
| 02 Desenvolvimento em Python versionado | `rpa/src/pf_rpa/` | 53 testes `pytest` aprovados em 15/11 | OK |
| 03 Decisão e repetição | `decisao.py` (CRÍTICA/ATENÇÃO/OK/SEM DADOS), laços por ponto e por amostra | `test_regra_estimada_limites`, `test_decisao_com_dados_do_mock` | OK |
| 04 Exceções e resiliência | `cliente_mvp.py`, `robo.py`, `coletor.py` | MVP fora, 503, timeout, corpo inválido, duplicados, chave recusada, reexecução (`tests/EVIDENCIAS.md`) | OK |
| 05 Logs e auditoria sem dados sensíveis | `rpa/logs/`, `auditoria.jsonl`; filtro de chave | `test_chave_nunca_aparece_no_log`; logs de produção nos artefatos do Actions | OK |
| 06 Integração com o MVP | `POST /api/rpa/amostras`, `POST /boletim`, tela `/boletim`, assistente | Boletins de 13/11 e 14/11 publicados em produção, com período, última atualização e cobertura | OK |
| 07 Testes de sucesso, decisão e falha | `rpa/tests/` | 53 aprovados; vídeo mostra sucesso, decisão e falha 503 rotulados | OK |
| 08 Repositório público com README | `rpa/README.md`, `src/`, `docs/`, `assets/`, `logs/`, `tests/` | Estrutura conferida | PENDENTE (repositório privado) |
| PDF: integrantes, problema, objetivo, fluxo, tecnologias, regras, exceções, logs, integração, testes, LGPD | `entregaveis/Relatorio_RPA.pdf` (13 pp.), cópia em `rpa/docs/relatorio.pdf` | Revisão visual de todas as páginas em 15/11; hash em `VALIDACAO_DOCUMENTOS.json` | OK |
| PDF: link do repositório e do vídeo | §12 | `[PENDENTE: URL_REPOSITORIO_PUBLICO]`, `[PENDENTE: URL_VIDEO_RPA]` | PENDENTE |
| Vídeo até 3 min: problema, ponta a ponta, decisão, integração, falha | `entregaveis/Ponto_Falante_RPA.mp4` (132 s, sem áudio) e `ROTEIRO_RPA.md` | Decodificação completa; trechos simulados rotulados | PENDENTE (narração e hospedagem) |

Observação sobre os dados: a cobertura de 13/11 (35,4%) e 14/11 (22,9%) é baixa porque o agendador gratuito do GitHub
descartou execuções; o boletim informa isso em vez de completar lacunas. Desde 15/11 a coleta roda no minuto 17 e a guarda
local (`scripts/genai/garantir-rpa.ps1`) dispara o workflow quando ele atrasa, com o PC ligado.

## Secure DevOps Tools & Cloud Computing (14 pontos) · conferência, não é módulo deste integrante

Entrega: PDF único com links clicáveis, um envio por equipe.

| Exigido | Onde está | Evidência | Situação |
|---|---|---|---|
| Dockerfile enxuto, usuário não root, sem segredo na imagem | `Dockerfile` (multi-stage, `USER 10001`) | Job "Imagem Docker + Trivy" verde | OK |
| Stack com docker compose | `docker-compose.yml` | Não executado nesta máquina (sem Docker); a CI constrói a imagem | OK na CI |
| Nuvem criada por Terraform, state e `.tfvars` fora do repo, porta admin fechada | Não há Terraform; o Render é descrito por `render.yaml` (Blueprint) | Não substitui Terraform no critério | **LACUNA** |
| GitHub Actions com build, Gitleaks, Semgrep e Trivy a cada push; segredos em Secrets; deploy automático | `.github/workflows/ci.yml`; deploy do Render só depois da CI verde | Execução de 15/11 do commit `1104614`: todos os jobs verdes | OK |
| Mostrar uma execução barrada e a corrigida | Semgrep barrou o commit `3db8505` (15/11) e o `1b4c803` corrigiu | Histórico de execuções do Actions | OK (falta o print no PDF da disciplina) |
| Observabilidade: 4 métricas de ouro e um alerta disparado | Só `/actuator/health` e health check do Render | Não há Prometheus/Grafana nem alerta | **LACUNA** |
| Documentação: diagrama, responsabilidade compartilhada, LGPD, custo, README reproduzível | `README.md` (ficha técnica, arquitetura, execução); LGPD nos relatórios | Falta seção de responsabilidade compartilhada e de custo no PDF da disciplina | Parcial |

As lacunas de Terraform e observabilidade são da disciplina de Secure DevOps, que não está no escopo GenAI + RPA deste
integrante; ficam registradas em `entregaveis/O_QUE_FALTA_VOCE_FAZER.md` para decisão da equipe.

## Revisão independente

Revisão de código automatizada e independente em 15/11/2026 (somente leitura, sem rede e sem rodar as avaliações
da GenAI) sobre os commits `8a7f08c..a9ed0bd`: 9 achados médios e 3 baixos, todos corrigidos no commit seguinte e
cobertos por testes (lista em `docs/ESTADO_PROJETO.md`, seção de 15/11 à tarde). Depois das correções: backend 218,
Angular 55, GenAI 155 e RPA 53 testes passando. A revisão não cobre os conjuntos fechados de avaliação da GenAI.

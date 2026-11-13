# Revisão dos critérios oficiais · GenAI e RPA

## Situação em 13/11/2026 (substitui as pendências da revisão de 11/11 abaixo)

| Item | Situação | Onde comprovar |
|---|---|---|
| GenAI 01, casos com gabarito e "não consta" | ✓ três ciclos (v1, v2, v3), cada um com DEV separado e teste inédito rodado uma vez | `genai/avaliacao/v3/LEIAME.md`, `perguntas_dev_v3.jsonl` |
| GenAI 03, recall@1/@3 e limiar | ✓ v1 (notebook 02); na v3 o limiar do cross-encoder foi recalibrado no DEV (-2,5) com justificativa | `genai/RELATORIO.md` §7.1 e §12 |
| GenAI 05/06, especialização × RAG × sem contexto | ✓ teste v3: sem contexto 8,7%, RAG 65,2%, agente v1 65,2% com o menor erro factual (8,7%), v3 58,7% | `genai/avaliacao/v3/teste_final_20261113/placar_teste_v3.csv` |
| GenAI 07, 5 erros reais | ✓ v1 (§8) e v3 (§12, com causa e correção; um deles é erro da rubrica) | `genai/RELATORIO.md` |
| GenAI integrada ao produto | ✓ site publicado chama a GenAI do PC do dono pelo Quick Tunnel gratuito; horários respondidos pelo backend com a SPTrans | `docs/evidencias/assistente_producao_20261113.txt` |
| Decisão `PF_MODO` | ✓ `agente` com `qwen2.5:7b`, a configuração mais segura no teste final | `genai/RELATORIO.md` §12 |
| RPA 01, BPMN | ✓ novo fluxo com dois robôs (coletor e boletim) | `rpa/docs/fluxo.bpmn`, `fluxo.png`, gerado por `gerar_fluxo_bpmn.py` |
| RPA 06, integração com o MVP real | ✓ Spring Boot publicado; coleta real no GitHub Actions (6 pontos, 111 ônibus previstos) | `docs/EVIDENCIAS.md` §4 |
| RPA 07, testes | ✓ 45 testes | `rpa/tests/` |
| Repositório no GitHub | ✓ privado em https://github.com/pedrobicas/ponto-falante; tornar público é decisão do dono | |
| CI | ✓ sete jobs verdes | `docs/EVIDENCIAS.md` §2 |

Ainda depende de pessoas: vídeos (GenAI e RPA), PDF do relatório do RPA, links do vídeo nos relatórios, deixar o
repositório público e manter o PC ligado com `scripts/genai/iniciar.ps1 -TunelRapido` durante a avaliação.

---

Revisado em 11/11/2026 contra o PDF oficial da GS 2026.2:

- GenAI: slides 29 a 31;
- RPA: slides 46 a 50.

Legenda:

- **Implementado:** o código ou documento existe.
- **Testado:** foi executado, com teste automatizado ou rodada real.
- **Comprovado:** há evidência salva que o avaliador pode abrir.

Execução dos testes nesta revisão: RPA **14 passed** e GenAI **9 passed**, ambos com `python -m pytest -q tests`.

## Generative AI for Engineering (10 pontos)

Objetivo do slide 29: *provar que a IA acerta mais e alucina menos que o mesmo modelo sem contexto, integrada ao produto de forma segura, explicável e de acordo com a LGPD.*

- **Comprovado** em `genai/avaliacao/placar_teste.csv`, no teste final rodado uma vez:
  - acerto: 5% sem contexto, 67,5% com RAG e 52,5% com o agente;
  - alucinação: 85% sem contexto, 20% com RAG e 5% com o agente.
- Integração e LGPD estão nas linhas 04, 08 e no relatório.

| # | Critério | Pts | Implementado | Testado | Comprovado (onde abrir) |
|---|---|---|---|---|---|
| 01 | Tarefa da IA e casos de teste com gabarito, incluindo "não consta" | 0,5 | ✓ | ✓ | `avaliacao/perguntas.jsonl`: 40 perguntas, 10 "não consta", com fatos e trechos esperados. `perguntas_dev.jsonl`: 30 perguntas, sem sobreposição com o teste. Tarefa descrita no notebook 01 e na ficha técnica. |
| 02 | Base de conhecimento em trechos com fonte | 1,0 | ✓ | ✓ | `base/trechos.jsonl` (244 trechos), `base/fontes.csv` (URL, órgão, licença, data de acesso), `base/tabela_base.csv`, notebook 01 com saídas |
| 03 | Busca com recall@1 e recall@3 medidos e limiar justificado | 1,0 | ✓ | ✓ | Notebook 02. Embeddings e limiar escolhidos no desenvolvimento: recall@1 0,80, recall@3 1,00, limiar 0,86 com curva e gráfico. Medida final no teste: recall@1 0,733 e recall@3 0,967. Arquivos: `recall_dev.csv`, `curva_limiar_dev.png`, `recall_teste_final.csv`. |
| 04 | Geração fundamentada: JSON válido, citação da fonte e recusa | 2,0 | ✓ | ✓ | Notebook 03, `src/pf_genai/esquemas.py` (pydantic), testes unitários. No teste final, o agente teve 100% de JSON válido, 100% de citações válidas e 100% de recusa correta nas "não consta". |
| 05 | Especialização (LoRA ou agente) comparada ao RAG simples | 2,0 | ✓ | ✓ | `src/pf_genai/agente.py`, notebook 04 e justificativa de agente no lugar de LoRA. Comparação no mesmo placar: alucinação 5% × 20% e sem fundamentação 0% × 4%. Também há 5 iterações documentadas em `avaliacao/historico_dev/`. |
| 06 | Placar das três configurações, com resultados interpretados | 2,0 | ✓ | ✓ | `avaliacao/placar_teste.csv`, `placar_teste.png` e `RELATORIO.md` §7. Mesmas condições (modelo, semente, índice, limiar, perguntas). Métricas pedidas pelo Pedro: "não consta", recusa indevida, sem fundamentação e precisão das citações. |
| 07 | 5 erros reais com proposta de correção | 1,0 | ✓ | ✓ | `avaliacao/erros.md` e `RELATORIO.md` §8. Todos vêm da rodada única do teste, com rastro, causa e correção. |
| 08 | README e reprodutibilidade | 0,5 | ✓ | ✓ (parcial) | `genai/README.md`: passo a passo, variáveis e `requirements.txt` com versões. Os notebooks foram reexecutados do zero com `nbconvert --execute`. **Falta:** testar a instalação numa máquina limpa (outro integrante). |

**Entregas do slide 31 (relatório no GitHub):** `genai/RELATORIO.md`.

| Item | Situação |
|---|---|
| 01 Nome completo e RM | ✓ |
| 02 Ficha técnica | ✓ |
| 03 Diagrama do pipeline de IA e dos documentos | ✓ (2 diagramas Mermaid) |
| 04 Tabela da base: fonte, formato, licença e trechos | ✓ |
| 05 Performance das configurações | ✓ |
| 06 Os 5 erros | ✓ |
| 07 Conclusão e links | Conclusão ✓. **Links do repositório e do vídeo pendentes.** |

Estrutura pedida: `notebooks/` com saídas ✓, `base/` ✓, `avaliacao/` ✓, `README.md` ✓.

**API integrada:**

- `POST /chat` e `GET /health` funcionando em chamada real (`genai/tests/saida_api.txt`).
- Contrato em `contratos/openapi-integracao.yaml`.
- **Falta** a chamada a partir do Spring Boot real do grupo (depende do backend).

**Pendências GenAI:**

1. Publicar o repositório **público** no GitHub e colocar o link.
2. Vídeo (o slide 31 pede o link). O slide 29 não define a duração.
3. Integração `/chat` com o Spring Boot real: o código Java de exemplo está em `contratos/GUIA_BACKEND_SPRING.md`.
4. Decidir onde o serviço roda na demo: o Ollama está no PC do Pedro.
5. Decisão de produto em aberto: a API serve `PF_MODO=agente` (mais seguro, recusa mais) ou `rag`.
6. Opcional, alto retorno: corrigir os erros 1 e 3 e reavaliar. Isso exigiria um **novo** conjunto de teste para continuar sem contaminação.

## Robotic Process Automation (10 pontos)

Objetivo (slide 46): automação ponta a ponta, mínima intervenção humana, decisão e repetição, exceções sem falha silenciosa, logs de auditoria, integração verificável com o MVP, segurança e LGPD.

### Etapas obrigatórias (slides 47 e 48)

| # | Etapa | Implementado | Testado | Comprovado |
|---|---|---|---|---|
| 01 | Mapeamento do processo (fluxo/PDD) | ✓ | — | `rpa/docs/fluxo.bpmn` (BPMN 2.0 válido, 26 fluxos), `fluxo.png`, `fluxo.html` |
| 02 | Desenvolvimento em Python versionado | ✓ | ✓ | `rpa/src/pf_rpa/` (config, gtfs, cliente_mvp, validacao, decisao, boletim, armazenamento, registro, robo, agendador). **Falta:** versionar no GitHub. |
| 03 | Decisão + repetição em lote | ✓ | ✓ | `decisao.py` classifica cada linha em CRÍTICA, ATENÇÃO, OK ou SEM_DADOS, percorrendo todas as passagens. Testes de decisão em `tests/test_cenarios.py`. |
| 04 | Exceções e resiliência | ✓ | ✓ | MVP fora do ar: retry com backoff e depois republica o boletim anterior como desatualizado. GTFS ausente: usa a rede fictícia com aviso. Duplicados e inválidos: descartados com o motivo. Falha de publicação: salva local e retorna código 1. Tudo coberto por testes. |
| 05 | Logs e auditoria sem dados sensíveis | ✓ | ✓ | `rpa/logs/rpa_2026-11-11.log` e `auditoria.jsonl`, com filtro que mascara segredos e o veículo em hash |
| 06 | Integração com o MVP | ✓ (contra o mock) | ✓ (mock) | `GET /historico` e `POST /boletim` com `X-API-Key`, contra o `tools/mock_mvp.py`, que segue o mesmo contrato OpenAPI. **Falta:** integrar com o Spring Boot e a tela do Angular reais, com prints. |
| 07 | Testes de sucesso, decisão e falha | ✓ | ✓ | 14 testes passando, com servidor HTTP real nos testes. Evidências em `rpa/tests/EVIDENCIAS.md`. |
| 08 | Documentação e publicação no GitHub | ✓ | — | `rpa/README.md` com descrição, integrantes, arquitetura e instruções. **Falta:** repositório público e links. |

### Estrutura do repositório (slide 49)

| Item | Situação |
|---|---|
| README | ✓ |
| `src/` | ✓ |
| `docs/` | ✓ |
| `assets/` | ✓ (boletins de exemplo) |
| `logs/` | ✓ |
| `tests/` | ✓ |
| `power-automate/` | Não se aplica: a automação é em Python |

### Relatório técnico em PDF (slide 49)

O conteúdo está em `rpa/docs/relatorio.md`, com os 12 itens:

| # | Item | Situação |
|---|---|---|
| 1 | Nomes e RMs | ✓ |
| 2 | CitizenTech e problema | ✓ |
| 3 | Objetivo e benefício | ✓ |
| 4 | Processo e fluxo | ✓ |
| 5 | Tecnologias | ✓ |
| 6 | Regras | ✓ |
| 7 | Exceções | ✓ |
| 8 | Logs | ✓ |
| 9 | Integração com o MVP | ⚠ só com o mock; faltam prints do MVP real |
| 10 | Testes | ✓ |
| 11 | Segurança e LGPD | ✓ |
| 12 | Links | ⚠ pendentes |

**Falta gerar o PDF**, o que vale fazer depois dos prints da integração.

### Vídeo (até 3 minutos)

O roteiro está pronto em `rpa/docs/roteiro_video.md`. **Falta gravar**, idealmente depois da integração real.

### Critérios de avaliação (slide 50)

| Critério | Pts | Situação |
|---|---|---|
| Integração com o MVP | 1 | ⚠ comprovada só com o mock do mesmo contrato; depende do backend do grupo |
| Documentação | 2 | ✓ README, BPMN e relatório (falta exportar o PDF e os links) |
| Desenvolvimento | 5 | ✓ 8 etapas implementadas e testadas |
| Vídeo | 2 | ⚠ roteiro pronto, gravação pendente |

## Resumo do que ainda depende de outras pessoas ou passos

1. **Repositórios públicos no GitHub** (GenAI e RPA) e links nos READMEs e relatórios. Ainda não fiz push: aguardo o OK do Pedro e a definição de qual conta ou organização usar.
2. **Integração com o backend real do grupo:** endpoints `GET /historico`, `POST /boletim` e a chamada a `/chat`, mais as telas do Angular. Contratos e código Java de exemplo já estão em `contratos/`.
3. **Vídeos e PDF do RPA:** dependem dos prints da integração real.
4. **Onde o serviço GenAI roda na demo** (PC do Pedro com túnel, ou VM do grupo) e a escolha entre `PF_MODO` agente e rag.

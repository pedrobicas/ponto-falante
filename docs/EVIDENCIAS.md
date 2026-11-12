# Evidências da entrega

Este documento reúne as provas de que cada parte foi executada e testada, e não apenas escrita. Cada item aponta
para o arquivo ou a execução correspondente.

## 1. Testes automatizados (execução local de 11/11/2026, repetida na CI)

| Suíte | Testes | Comando |
|---|---|---|
| Spring Boot (PostgreSQL embutido, contratos Olho Vivo, segurança) | 45 | `backend/mvnw -B verify` |
| Angular (unidade + acessibilidade axe) | 13 | `npm test -- --watch=false` |
| GenAI (RAG, agente v1/v2, API, segurança) | 51 | `pytest -q genai/tests` |
| RPA (cenários do boletim) | 14 | `pytest -q rpa` |
| Integração (MVP + RPA + contratos) | 26 | `pytest -q tests/integracao` |

Todos passaram. O número de testes de cada suíte está no README.

## 2. CI (GitHub Actions)

Cada push roda Gitleaks, Semgrep, testes Python, Spring com PostgreSQL, Angular com axe, build da imagem Docker,
Trivy (dependências e imagem) e um teste de fumaça da imagem.

- Execução verde do commit `439df10`: https://github.com/pedrobicas/ponto-falante/actions/runs/43127197924
- Execução verde do commit `43720dd` (correções da revisão de código): https://github.com/pedrobicas/ponto-falante/actions/runs/43126685620
- As execuções vermelhas anteriores (`68300fe`, `25eec4b`) são da adoção dos scanners; os achados foram corrigidos
  ou justificados em `.gitleaks.toml`, `.semgrepignore`, comentários `nosemgrep` e `.trivyignore`.

## 3. Aplicação publicada (Render)

- URL: https://ponto-falante.onrender.com (deploy automático só depois de todos os checks: `autoDeployTrigger: checksPass`).
- Teste de aceitação contra a produção:
  `python scripts/integracao/testar_mvp.py --url https://ponto-falante.onrender.com` →
  `MVP: saude, contratos e previsoes OK; Angular e navegacao OK.`
- Previsões em **modo demonstração**: a API devolve `dados_simulados: true` e a tela mostra o selo **SIMULADO**.

## 4. RPA em produção

O robô roda no GitHub Actions (cron diário às 9h UTC), lê o histórico do MVP e publica o boletim pela API protegida.

- Execução de 12/11/2026: https://github.com/pedrobicas/ponto-falante/actions/runs/43127702267
- Execução de 11/11/2026: https://github.com/pedrobicas/ponto-falante/actions/runs/43082177783
- O boletim publicado aparece em `/boletim` com a etiqueta "Dados simulados", porque o histórico ainda vem do simulador.
  O Spring rejeita boletins cuja marcação `dados_simulados` contradiz a contagem por fonte (`fonte_dados`).

Fluxo BPMN, logs e cenários: [rpa/README.md](../rpa/README.md).

## 5. Interface (capturas)

Em [evidencias/telas](evidencias/telas): início, ponto, assistente, boletim e ajustes, em celular (`-m-`) e computador
(`-d-`), nos temas claro, escuro, alto contraste claro e alto contraste escuro.

## 6. GenAI

- Relatório completo, incluindo a iteração v2: [genai/RELATORIO.md](../genai/RELATORIO.md) (seção 11).
- Placar de desenvolvimento (30 perguntas, 10 configurações): `genai/avaliacao/v2/placar_*.csv`.
- Teste inédito (40 perguntas), rodado uma única vez em 11/11/2026: `genai/avaliacao/v2/perguntas_teste_v2.jsonl`,
  `genai/avaliacao/v2/LEIAME_teste_v2.md` e os resultados `.jsonl`.
- Adjudicação cega independente: `adjudicacao_entrada_cega.json` (respostas embaralhadas sem a configuração),
  `adjudicacao_julgamento.jsonl` (julgamento) e `adjudicacao_chave.json` (chave para desembaralhar).
- O resultado original da v1 está preservado na tag `experimento-original-genai-v1`.

## 7. Revisões independentes de código

- Revisão de código 1: registro interno 1.
  Quatro achados (X-Forwarded-For no limite do chat, login SPTrans concorrente, proveniência do boletim, cota
  compartilhada da GenAI), todos corrigidos no commit `43720dd` com testes de regressão.
- Revisão de código 2 (parcial, interrompida pelo limite de uso; a observação registrada foi corrigida):
  registro interno 2.

## 8. SPTrans

A integração Olho Vivo está implementada e coberta por testes de contrato. O login real retorna `false` com a chave do
aplicativo, inclusive pelo navegador do dono da conta, o que aponta para a conta na SPTrans e não para o código.
Diagnóstico completo: [DIAGNOSTICO_SPTRANS.md](DIAGNOSTICO_SPTRANS.md).

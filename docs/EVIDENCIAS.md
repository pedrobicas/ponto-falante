# Evidências da entrega

Este documento reúne as provas de que cada parte foi executada e testada, e não apenas escrita. Cada item aponta
para o arquivo ou a execução correspondente.

## 1. Testes automatizados (execução local de 13/11/2026, repetida na CI)

| Suíte | Testes | Comando |
|---|---|---|
| Spring Boot (PostgreSQL embutido, contratos Olho Vivo, segurança) | 106 | `backend/mvnw -B verify` |
| Angular (unidade + acessibilidade axe) | 40 | `npm test -- --watch=false` |
| GenAI (RAG, agentes v1/v2/v3, API, segurança, continuidade da avaliação) | 126 | `pytest -q genai/tests` |
| RPA (coletor e cenários do boletim) | 45 | `pytest -q rpa` |
| Integração (MVP + RPA + contratos) | 26 | `pytest -q tests/integracao` |

Todos passaram. O número de testes de cada suíte está no README.

## 2. CI (GitHub Actions)

Cada push roda Gitleaks, Semgrep, testes Python, Spring com PostgreSQL, Angular com axe, build da imagem Docker,
Trivy (dependências e imagem) e um teste de fumaça da imagem.

- Execução verde do commit `66b8927` (13/11, sete jobs): https://github.com/pedrobicas/ponto-falante/actions/runs/43421682850
- Execução verde do commit `439df10`: https://github.com/pedrobicas/ponto-falante/actions/runs/43127197924
- Execução verde do commit `43720dd` (correções da revisão adversarial): https://github.com/pedrobicas/ponto-falante/actions/runs/43126685620
- As execuções vermelhas anteriores (`68300fe`, `25eec4b`) são da adoção dos scanners; os achados foram corrigidos
  ou justificados em `.gitleaks.toml`, `.semgrepignore`, comentários `nosemgrep` e `.trivyignore`.

## 3. Aplicação publicada (Render)

- URL: https://ponto-falante.onrender.com (deploy automático só depois de todos os checks: `autoDeployTrigger: checksPass`).
- Teste de aceitação contra a produção:
  `python scripts/integracao/testar_mvp.py --url https://ponto-falante.onrender.com` →
  `MVP: saude, contratos e previsoes OK; Angular e navegacao OK.`
- Desde 11/11/2026 (22h35), previsões **reais** pelo gateway da Prefeitura: `/api/status` com `sptrans: REAL`;
  consulta em produção trouxe 2 pontos ("paulista"), 4 linhas ("8000") e 24 ônibus previstos no ponto 260015039,
  todos com `fonte: OLHO_VIVO` e `tipo: PREVISAO`. Validação: [evidencias/sptrans_gateway_validacao.txt](evidencias/sptrans_gateway_validacao.txt).
- Sem credenciais, o modo demonstração continua identificado com o selo **SIMULADO**.
- Assistente no site (13/11/2026): [evidencias/assistente_producao_20261113.txt](evidencias/assistente_producao_20261113.txt),
  gerado por `scripts/integracao/coletar_evidencias_producao.py`. Perguntas de horário respondidas pelo backend com a
  SPTrans (`origem=TEMPO_REAL`); perguntas de regras respondidas pela GenAI no PC do dono, pelo Quick Tunnel gratuito
  (`origem=BASE_OFICIAL`, com fontes); pergunta fora da base recusada com indicação do 156.

## 4. RPA em produção

O robô roda no GitHub Actions (cron diário às 9h UTC), lê o histórico do MVP e publica o boletim pela API protegida.

- Execução de 12/11/2026: https://github.com/pedrobicas/ponto-falante/actions/runs/43127702267
- Execução de 11/11/2026: https://github.com/pedrobicas/ponto-falante/actions/runs/43082177783
- Coleta real em produção (13/11/2026): https://github.com/pedrobicas/ponto-falante/actions/runs/43429040197.
  6 pontos consultados no MVP publicado (SPTrans real), 111 ônibus previstos, 6 amostras gravadas, 0 rejeitadas.
  A coleta passa a rodar 8 vezes por dia (`rpa-coleta.yml`).
- Boletim de 13/11/2026 para o dia 12/11: https://github.com/pedrobicas/ponto-falante/actions/runs/43429139001.
  Como a coleta ainda não existia em 12/11, o robô publicou o boletim como **INDISPONIVEL**, em vez de preencher com
  dados simulados. O boletim de 13/11 sai na execução de 14/11 a partir das amostras reais (estimado, porque
  previsão não é chegada observada).
- Antes da coleta, o boletim aparecia em `/boletim` com a etiqueta "Dados simulados", porque o histórico vinha do simulador.
  O Spring rejeita boletins cuja marcação `dados_simulados` contradiz a contagem por fonte (`fonte_dados`).

Fluxo BPMN, logs e cenários: [rpa/README.md](../rpa/README.md).

## 5. Interface (capturas)

Em [evidencias/telas](evidencias/telas): início, ponto, assistente, boletim e ajustes, em celular (`-m-`) e computador
(`-d-`), nos temas claro, escuro, alto contraste claro e alto contraste escuro.

## 6. GenAI

- Relatório completo: [genai/RELATORIO.md](../genai/RELATORIO.md) (seção 11, v2; seção 12, v3).
- v3 (12 e 13/11/2026): DEV de 108 perguntas em `genai/avaliacao/v3/retomada_dev_20261112/` e `iteracao_dev_20261113/`;
  teste inédito de 46 perguntas, congelado por SHA-256 e rodado uma única vez em `genai/avaliacao/v3/teste_final_20261113/`.
- Placar de desenvolvimento (30 perguntas, 10 configurações): `genai/avaliacao/v2/placar_*.csv`.
- Teste inédito (40 perguntas), rodado uma única vez em 11/11/2026: `genai/avaliacao/v2/perguntas_teste_v2.jsonl`,
  `genai/avaliacao/v2/LEIAME_teste_v2.md` e os resultados `.jsonl`.
- Adjudicação cega independente: `adjudicacao_entrada_cega.json` (respostas embaralhadas sem a configuração),
  `adjudicacao_julgamento.jsonl` (julgamento) e `adjudicacao_chave.json` (chave para desembaralhar).
- O resultado original da v1 está preservado na tag `experimento-original-genai-v1`.

## 7. Revisões independentes de código

- Revisão adversarial 1: registro interno 1.
  Quatro achados (X-Forwarded-For no limite do chat, login SPTrans concorrente, proveniência do boletim, cota
  compartilhada da GenAI), todos corrigidos no commit `43720dd` com testes de regressão.
- Revisão adversarial 2 (parcial, interrompida pelo limite de uso; a observação registrada foi corrigida):
  registro interno 2.
- Revisão adversarial 3 (12/11/2026, backend: gateway, assistente de tempo real, boletim):
  registro interno 3. Cinco achados, corrigidos com testes.
- Revisão adversarial 4 (13/11/2026, registro do túnel, scripts e poda da v3):
  registro interno 4. Quatro achados (dois altos),
  todos corrigidos com testes: desafio HMAC de identidade no registro, registro serializado, disjuntor por geração do
  endereço e poda desligada no padrão.

## 8. SPTrans

O login direto da Olho Vivo retorna `false` para qualquer chave (inclusive uma inventada, usada como controle). A solução foi o
gateway oficial da Prefeitura (OAuth2), validado com dados reais e em uso no Render.
Diagnóstico completo: [DIAGNOSTICO_SPTRANS.md](DIAGNOSTICO_SPTRANS.md).

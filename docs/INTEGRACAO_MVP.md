# Validar e integrar o MVP

Branch de integração: `integracao/mvp`, criada de `c84f247`. O backend/frontend originais estavam não versionados na `main`; os testes desta branch foram executados em cópias ignoradas por Git. Os componentes completos precisam ser commitados pelo responsável antes do merge/primeiro deploy.

## Comandos reproduzíveis após integrar os componentes

Na raiz do projeto, com Python 3.11+, Java 21 e Node 24.16.0:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/integracao
.\.venv\Scripts\python.exe scripts/integracao/preparar_backend.py
Push-Location .validation/backend
.\mvnw.cmd -B verify "-Dpf.integration.root=D:\GLOBALSOLUTION_2" "-Dpf.integration.python=D:\GLOBALSOLUTION_2\.venv\Scripts\python.exe"
Pop-Location

New-Item -ItemType Directory -Path frontend/src/testing -Force | Out-Null
Copy-Item tests/frontend/integracao-mvp.spec.ts frontend/src/testing/
Push-Location frontend
npm.cmd ci --no-audit --no-fund
npm.cmd test -- --watch=false
npm.cmd run build -- --configuration production
Pop-Location
```

Crie `frontend/src/testing` se necessário. Os nomes `integracao-*` permitem acrescentar os testes sem substituir testes da equipe. A CI faz essa cópia automaticamente.

`preparar_backend.py` copia fontes, Maven Wrapper e POM para `.validation/backend`, acrescenta os testes externos e a dependência de PostgreSQL **somente de teste** (`io.zonky.test:embedded-postgres:2.2.2`). Cada execução limpa somente esse destino resolvido dentro de `.validation`, evitando classes antigas. Não execute durante outra validação usando o mesmo destino. Não aponta para a `main` nem altera o POM original. O PostgreSQL embutido usado é 14.22; o deploy usa PostgreSQL 16 e ainda precisa do teste de container.

Os testes completos iniciam servidor Spring em porta aleatória e PostgreSQL real temporário. O teste Java invoca `testar_mvp.py --api-only` e `testar_rpa_local.py`, que executa o RPA original, publica e relê o boletim. Para também exigir Angular compilado, copie `frontend/dist/frontend/browser/*` para `.validation/backend/src/main/resources/static/` antes do Maven e acrescente `-Dpf.integration.angular=true`.

Com uma aplicação já iniciada:

```powershell
.\.venv\Scripts\python.exe scripts/integracao/testar_mvp.py --url http://localhost:8080
```

Essa verificação somente lê dados: saúde, status, pontos/previsões de demonstração, entrada Angular, navegação `/sobre` e arquivos JavaScript. `testar_rpa_local.py` publica boletim e por isso aceita somente servidor em loopback; o segredo RPA vem do ambiente ou `.env`.

## Contratos conferidos

| Consumidor → serviço | Configuração e contrato atual |
| --- | --- |
| Angular → Spring | Mesma origem, `/api/status`, `/api/pontos`, `/api/pontos/{codigo}/previsoes`, `/api/chat`, `/api/boletim`, `/api/boletins`. JSON `snake_case`. |
| Spring → SPTrans | `SPTRANS_TOKEN`, `SPTRANS_BASE_URL` HTTPS; login por POST e cookie; renovação única após 401; falha real gera indisponibilidade. |
| Spring → GenAI | `GENAI_URL`, `GENAI_API_KEY`; `POST /chat` e `X-API-Key`; timeout de leitura atual 45 s; resposta pública acrescenta `disponivel`. Sem GenAI o MVP continua funcionando. |
| RPA → Spring | `MVP_URL=http://localhost:8080/api`; `GET /historico?data=...`; `POST /boletim` com `X-API-Key=${RPA_API_KEY}`; mesmo valor nos dois processos. |
| Render → PostgreSQL | `DATABASE_URL` é convertido pelo `ConversorDatabaseUrl`; URL JDBC explícita tem prioridade. |

`contratos/openapi-mvp.yaml` é a referência pública atual. O guia antigo `contratos/GUIA_BACKEND_SPRING.md` e partes de `docs/ANALISE_E_ARQUITETURA.md` ainda usam `LLM_URL`, timeout 30 s e rotas sem `/api`: use o mapeamento acima e atualize esses textos pela equipe ao consolidar. O contrato do microsserviço GenAI continua em `/chat`; o navegador usa `/api/chat` do Spring.

## Antes do primeiro deploy

1. A equipe commita o backend/frontend completos e integra esta branch; o novo `ConfigRepositorios` precisa acompanhar o backend.
2. Integrar separadamente `integracao/genai-api-segura`, preservando suas alterações e scripts Cloudflare. O MVP funciona sem GenAI enquanto isso.
3. Executar Docker e Compose em máquina com engine instalado; a configuração e os schemas foram validados, mas não houve build de container nesta sessão.
4. Executar CI no GitHub depois da autorização para push. Workflows foram validados localmente com actionlint; Gitleaks/Semgrep/Trivy ainda precisam executar.
5. Criar serviço/Blueprint no Render e preencher variáveis seguras conforme [SPTRANS.md](SPTRANS.md). Publicação/push não foram feitos.
6. Configurar secrets Actions `MVP_URL=https://SERVICO.onrender.com/api` e `RPA_API_KEY` para o robô diário. Confirmar a execução manual antes de depender do agendamento.

Para o launcher, Compose e Render desta branch, HTTPS já está configurado. Ao consolidar o backend, trocar também os defaults HTTP em `PfProps.java` e `application.yml` para HTTPS; esses arquivos ativos da equipe foram preservados.

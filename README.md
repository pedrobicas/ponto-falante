# Ponto Falante

MVP da Global Solution FIAP 2026.2: Angular servido pelo Spring Boot, PostgreSQL, previsões demonstrativas, voz, boletim RPA e assistente GenAI opcional.

## Executar localmente sem Docker

Requisitos: Java/JDK 21, Node 24.16, Python 3.11+.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r rpa/requirements.txt
.\.venv\Scripts\python.exe scripts/integracao/rodar_mvp_local.py --build
```

Abra **http://127.0.0.1:8080**. O comando compila Angular, executa os testes do Spring, empacota o JAR real e inicia PostgreSQL local. A SPTrans fica em **demonstração**, sem usar a chave. O banco fica em `.validation/local/pgdata` e é reutilizado após reiniciar. `Ctrl+C` encerra aplicação e banco; não remova essa pasta se quiser preservar os boletins.

O primeiro uso baixa dependências Maven/npm e os binários PostgreSQL para desenvolvimento. Esse PostgreSQL embutido não faz parte do JAR publicado; Docker/Render usam banco separado. O processo local escuta somente em loopback. As chaves locais geradas ficam em `.validation/local/runtime.env`, ignorado pelo Git. Não compartilhe esse arquivo.

Para publicar um boletim pelo RPA original, com o MVP aberto, em outro terminal:

```powershell
.\.venv\Scripts\python.exe scripts/integracao/testar_rpa_local.py --url http://127.0.0.1:8080 --env-file .validation/local/runtime.env
```

Para o assistente real, veja [scripts/genai/README.md](scripts/genai/README.md). A chave da API GenAI deve ser a mesma usada no Spring; o navegador nunca recebe essa chave. Sem GenAI o restante do MVP funciona e o chat informa indisponibilidade. Os experimentos e resultados acadêmicos permanecem em `genai/` e `rpa/`.

## Docker

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
# Preencha POSTGRES_PASSWORD, PF_SALT e RPA_API_KEY somente no arquivo local.
docker compose up --build
```

O Compose usa PostgreSQL 16 e publica somente a aplicação na porta 8080. O token SPTrans é opcional na demonstração. Docker não estava disponível na máquina de validação: build e execução de containers ainda precisam do check de CI.

## Testes

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/integracao
Push-Location rpa; ..\.venv\Scripts\python.exe -m pytest -q; Pop-Location
Push-Location frontend; npm.cmd ci; npm.cmd test -- --watch=false; npm.cmd run build; Pop-Location
Push-Location backend; .\mvnw.cmd -B verify; Pop-Location
```

Testes GenAI requerem `genai/requirements-ci.txt`; execute `python -m pytest -q tests` dentro de `genai/`. Não rodam avaliações acadêmicas nem exigem o Ollama. O launcher `--build` também executa os testes HTTP entre Spring/RPA e o Angular compilado.

[Primeiro deploy no Render](docs/PRIMEIRO_DEPLOY.md) · [Contrato público](contratos/openapi-mvp.yaml)

# Configurar e testar a SPTrans

O segredo local deve ficar em **`D:\GLOBALSOLUTION_2\.env`**, na raiz do projeto:

```dotenv
SPTRANS_TOKEN=preencha_somente_no_arquivo_local
SPTRANS_BASE_URL=https://api.olhovivo.sptrans.com.br/v2.1
PF_SPTRANS_MODO=demo
```

O `.env` ainda não existia na auditoria de 11/11/2026. `.env.example` já existia e foi atualizado sem segredos. Crie a cópia somente se não houver arquivo local:

```powershell
Set-Location D:\GLOBALSOLUTION_2
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
notepad .env
git check-ignore .env
```

Não coloque o token no Angular, código Java, argumentos do terminal, contratos ou Git. Não é necessário compartilhá-lo na conversa.

## Teste direto, sem iniciar banco ou aplicação

Enquanto esta branch não estiver integrada, execute:

```powershell
& D:\GLOBALSOLUTION_2\.venv\Scripts\python.exe `
  D:\GLOBALSOLUTION_2\scripts\integracao\testar_sptrans.py `
  --env-file D:\GLOBALSOLUTION_2\.env
```

Depois de integrar a branch, o caminho fica `scripts\integracao\testar_sptrans.py`. A ferramenta usa apenas a biblioteca padrão do Python 3.11+; a `.venv` existente é uma opção conveniente.

Ela faz `POST /Login/Autenticar?token=...`, exige o booleano JSON `true`, guarda o cookie somente na memória e confirma uma consulta `GET /Linha/Buscar?termosBusca=8000`. Sucesso termina com código 0 e mensagem `SPTrans: autenticacao OK; cookie confirmado; N linha(s) recebida(s).` Falhas terminam com código 1, sem imprimir token, cookies, corpo remoto ou URL autenticada. Não segue redirecionamentos.

Valores do ambiente têm prioridade sobre `.env`. Não há interpolação nem execução de comandos do arquivo. HTTP só é permitido para servidores de teste em loopback; a API oficial usa HTTPS.

O diagnóstico mostra `etapa=configuracao`, `etapa=login` e `etapa=consulta_linhas`. Em erros HTTP informa status, categoria, tipo de conteúdo, família conhecida do servidor e quantidade limitada de bytes lidos. O corpo remoto é analisado somente em memória e nunca é impresso; headers, identificadores de requisição, Location, cookies e URL autenticada também não são impressos. Não há novas tentativas após 403. A classificação de servidor vem do banner recebido e não comprova, sozinha, uma regra de firewall.

O teste direto **sempre testa a chave real**, mesmo com `PF_SPTRANS_MODO=demo`: a opção controla somente a aplicação. Espaços externos são removidos da cópia em memória; espaços internos, quebras internas e BOM no valor são rejeitados antes da requisição. O arquivo e a chave original não são reescritos pelo teste.

## Spring Boot e Docker Compose

O backend existente já resolve `SPTRANS_TOKEN` em `backend/src/main/resources/application.yml`:

```yaml
pf:
  sptrans-token: ${SPTRANS_TOKEN:}
```

Spring Boot, executado normalmente pelo Maven/IDE, não carrega esse `.env` automaticamente. A ferramenta abaixo lê o arquivo, passa as variáveis pelo ambiente do processo e usa HTTPS mesmo com os defaults HTTP do backend atual:

```powershell
& D:\GLOBALSOLUTION_2\.venv\Scripts\python.exe `
  D:\GLOBALSOLUTION_2\scripts\integracao\preparar_backend.py `
  --source D:\GLOBALSOLUTION_2\backend

& D:\GLOBALSOLUTION_2\.venv\Scripts\python.exe `
  D:\GLOBALSOLUTION_2\scripts\integracao\rodar_backend.py `
  --env-file D:\GLOBALSOLUTION_2\.env `
  --backend-dir D:\GLOBALSOLUTION_2\.validation\backend
```

A preparação inclui as configurações adicionais de repositórios JPA e SPTrans, sem editar as fontes em andamento, e recria apenas `.validation/backend`; espere qualquer teste nessa pasta terminar antes de executá-la. Depois de integrar a branch e os componentes, o launcher pode apontar para `D:\GLOBALSOLUTION_2\backend` ou usar seu caminho padrão. `ConfigSptrans` normaliza token e URL antes de vincular `PfProps`, corrige o default HTTP legado em memória e impede HTTP externo; não segue um redirecionamento HTTP para HTTPS.

É necessário Java 21 e PostgreSQL acessível em `localhost:5432`, ou configurar `SPRING_DATASOURCE_URL`, `SPRING_DATASOURCE_USERNAME` e `SPRING_DATASOURCE_PASSWORD` no ambiente/arquivo. A ferramenta mapeia `POSTGRES_PASSWORD` para a senha JDBC quando não existe configuração explícita. Para IDE, configure as mesmas variáveis na execução.

Depois que os componentes e esta branch forem integrados, `docker compose up --build` lê o `.env` da raiz e repassa `SPTRANS_TOKEN` e `SPTRANS_BASE_URL` ao container. Também exige `POSTGRES_PASSWORD`, `PF_SALT` e `RPA_API_KEY` preenchidos. O banco do Compose não publica porta no host; para Maven/IDE use um PostgreSQL acessível ou ajuste explicitamente sua configuração local.

Reinicie a aplicação após trocar o token. Valide:

```powershell
Invoke-RestMethod http://localhost:8080/api/status
Invoke-RestMethod 'http://localhost:8080/api/linhas?busca=8000'
```

Com `PF_SPTRANS_MODO=demo`, espere `sptrans = DEMO` e `fonte = SIMULADO`, mesmo com a chave armazenada. Não são feitas chamadas SPTrans pela aplicação. Quando o teste direto autenticar e consultar com sucesso, troque para `PF_SPTRANS_MODO=auto` e reinicie: espere `sptrans = REAL` e `fonte = OLHO_VIVO`. Em `auto`, sem token o estado é `DEMO`; token recusado, timeout ou indisponibilidade produzem `INDISPONIVEL`/HTTP 503. Uma falha real nunca é silenciosamente rotulada como demonstração. `modo=demo` também permite solicitar demonstração por consulta.

## Render

No serviço web **ponto-falante**, abra **Environment → Add Environment Variable**:

| Key | Value |
| --- | --- |
| `SPTRANS_TOKEN` | Token preenchido somente no painel seguro |
| `SPTRANS_BASE_URL` | `https://api.olhovivo.sptrans.com.br/v2.1` |
| `PF_SPTRANS_MODO` | `demo` durante indisponibilidade; `auto` depois de validar o acesso |

Use **Save and deploy** para aplicar ao build existente; **Save only** só passa a valer no próximo deploy. O Blueprint declara o token com `sync: false`; a URL HTTPS é pública e fica versionada. Teste os mesmos endpoints na origem HTTPS do serviço.

Referências oficiais: [autenticação e exigência de HTTPS da SPTrans](https://www.sptrans.com.br/desenvolvedores/api-do-olho-vivo-guia-de-referencia/documentacao-api/), [variáveis de ambiente do Render](https://render.com/docs/configure-environment-variables).

## Limite da validação realizada

Os testes automatizados usam token sintético e servidor HTTP local. Em 11/11/2026 o teste real com a chave já inserida localmente retornou **HTTP 403 na etapa login**, JSON de 717 bytes, banner classificado como Cloudflare e sem redirecionamento. A consulta posterior não ocorreu. A regra responsável e a validade da chave não podem ser comprovadas apenas com essa resposta. O modo demonstrativo local ficou explícito, com a chave preservada. Veja [DIAGNOSTICO_SPTRANS.md](DIAGNOSTICO_SPTRANS.md).

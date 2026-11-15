# GenAI no PC do dono

Requisitos locais: Windows PowerShell 5.1, Ollama no PATH, Python >= 3.11
com `genai/requirements.txt`, modelo Ollama e indice preparados conforme
`genai/README.md`. Os scripts nao instalam programas nem criam recursos remotos.
`cloudflared` e opcional: so e necessario para conectar um backend remoto ao PC.
A interface web pode usar a LLM local com todos os servicos no proprio PC,
sem Render, Cloudflare, alteracoes de DNS ou API de modelo paga.

## Demonstracao completa no proprio PC

O caminho e navegador -> `/api/chat` do Spring -> `/chat` da FastAPI -> Ollama.
O frontend nunca recebe a chave da GenAI e nao acessa a porta do Ollama.
Consultas dinamicas de linhas, pontos e previsoes seguem pelo roteador SPTrans do
Spring. Perguntas sobre regras usam a base documental da GenAI.

1. Copie `.env.example` para `.env.local` nesta pasta. Preencha `GENAI_API_KEY`
   com uma chave aleatoria. Configure a mesma chave no Spring Boot e envie-a
   no header `X-API-Key`, nunca na URL.
2. Se necessario, defina `GENAI_PYTHON` com o caminho completo do Python do
   ambiente virtual. A busca padrao usa `.venv/Scripts/python.exe` do worktree,
   depois do checkout principal, depois `python.exe` do PATH.
3. Execute da raiz do worktree em um PowerShell que permita scripts locais:

   ```powershell
   powershell.exe -NoProfile -File scripts/genai/iniciar.ps1 -SomenteLocal
   powershell.exe -NoProfile -File scripts/genai/status.ps1
   powershell.exe -NoProfile -File scripts/genai/parar.ps1
   ```

`-SomenteLocal` impede iniciar o tunel mesmo quando `CF_TUNNEL_NAME` esta
preenchido. Se existir um `cloudflared` ativo, o script para antes de iniciar
servicos; nao encerra processos externos por conta propria. A chave e a
autenticacao continuam obrigatorias nesse modo.

4. No `.env` da raiz, mantenha `GENAI_URL=http://127.0.0.1:8001` e a **mesma**
   `GENAI_API_KEY` usada em `scripts/genai/.env.local`. Nao gere outra chave para
   um servico ja configurado. Variaveis do terminal prevalecem sobre o `.env`
   no launcher do MVP; reinicie processos apos mudar configuracoes.
5. Em outro terminal, na raiz, com JDK 21, Node adequado ao `frontend/package.json`
   e dependencias Python instaladas, execute:

   ```powershell
   .\.venv\Scripts\python.exe scripts/integracao/rodar_mvp_local.py --build
   ```

   O launcher compila Angular e Spring, executa os testes do backend e inicia
   o JAR real e PostgreSQL persistente em loopback. Abra
   `http://127.0.0.1:8080/assistente`. Sem `--sptrans-gateway`, os dados de
   transporte sao demonstrativos e devem continuar identificados como tal.
   Para dados reais, use `--build --sptrans-gateway` com as credenciais oficiais
   ja configuradas localmente; nao cole credenciais no terminal ou em evidencias.
6. Verifique o caminho HTTP real:

   ```powershell
   powershell.exe -NoProfile -File scripts/genai/verificar-local.ps1
   ```

   Esse teste envia uma pergunta de desenvolvimento diretamente a FastAPI e
   depois ao Spring, exigindo resposta, fontes e modo RAG/agente. Falha se houver
   recusa ou indisponibilidade; nao publica a pergunta, resposta ou chave nos
   logs do script. `-PortaMvp 8085` permite testar outra porta. Isso comprova o
   transporte e o contrato; ainda valide a pertinencia da resposta e o fluxo
   no navegador (teclado, leitor de tela e voz).

Para desenvolvimento do Angular, execute em `frontend/`:
`npm.cmd start -- --host 127.0.0.1 --proxy-config proxy.conf.json`.
O proxy encaminha `/api` ao Spring local em 8080. O backend deve estar iniciado.
No Compose, `host.docker.internal` depende da rede Docker/host; nao presuma que
um servico ligado apenas a loopback esteja acessivel ao container. O launcher
nativo acima evita essa dependencia e conserva a API em loopback.

Para experimentar a v3, configure `PF_MODO=v3` e
`PF_MODELO_GERADOR=qwen2.5:7b` no `.env.local`, prepare o indice v3 e reinicie.
O padrao `agente` continua preservado. `/health` 200 nao mede precisao nem latencia;
os benchmarks de desenvolvimento devem sustentar a escolha do modo para a demo.

## Configuracao e processos

`.env.local` aceita `NOME=valor`, comentarios em linhas iniciadas por `#` e
aspas simples ou duplas ao redor do valor. Nao executa expressoes, expande
variaveis ou interpreta comentarios no fim da linha. Valores do arquivo
substituem os do ambiente; variaveis ausentes preservam o ambiente recebido.
`.env.local` e `run/` sao ignorados pelo Git. Credenciais do cloudflared ficam
fora do repositorio, no diretorio local de configuracao do cloudflared.

## Backend remoto: tunel opcional

O Spring publicado no Render nao consegue acessar o `127.0.0.1` do PC. Para
esse cenario e necessario um caminho de rede autorizado ate a FastAPI local.
Isso nao muda a execucao da LLM: ela continua no Ollama do PC.
Nenhum tunel, DNS ou credencial foi configurado por esta retomada.

**Os passos abaixo expoem a API e so devem ser executados pelo dono apos decidir
essa exposicao.** Mantenha `GENAI_AUTH_DESATIVADA=0`, a chave no Spring e na API
e as portas 8001/11434 em loopback. Nunca exponha o Ollama diretamente.

Para uma demonstracao temporaria sem alterar DNS, um Quick Tunnel produz uma
URL aleatoria `trycloudflare.com`; nao exige dominio e a URL muda quando o
processo e reiniciado. Nao possui garantia de disponibilidade e destina-se a
testes. [Documentacao oficial de Quick Tunnels](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/).

```powershell
# Executar somente apos a autorizacao de exposicao, em terminal proprio.
cloudflared tunnel --url http://127.0.0.1:8001
```

Copie a URL HTTPS informada para `GENAI_URL` do backend remoto e
`GENAI_PUBLIC_URL` local; mantenha a mesma chave nos dois servicos. Reinicie o
backend se a plataforma exigir para aplicar variaveis. Nao use autenticacao
por email do Quick Tunnel nesse fluxo servidor-servidor: ela exige navegador
interativo. O acesso ao `/chat` continua protegido por `X-API-Key`. Para encerrar
o Quick Tunnel, use Ctrl+C no proprio terminal; `parar.ps1` nao administra esse
processo externo.

Para URL estavel, um tunel nomeado requer conta/configuracao e pode envolver DNS.
Nao altere `pedrobicas.com` como parte da demonstracao. Use apenas um dominio
explicitamente autorizado pelo dono. Siga a
[documentacao de tunel nomeado da Cloudflare](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/local-management/create-local-tunnel/):

```powershell
cloudflared tunnel login
cloudflared tunnel create NOME_DO_TUNEL
cloudflared tunnel route dns NOME_DO_TUNEL genai.seu-dominio.example
```

Configure `%USERPROFILE%\.cloudflared\config.yml`, substituindo os marcadores:

```yaml
tunnel: UUID_DO_TUNEL
credentials-file: C:\Users\SEU_USUARIO\.cloudflared\UUID_DO_TUNEL.json
ingress:
  - hostname: genai.seu-dominio.example
    service: http://127.0.0.1:8001
  - service: http_status:404
```

Defina `CF_TUNNEL_NAME` e `GENAI_PUBLIC_URL` em `.env.local`. Para um arquivo de
configuracao existente em outro caminho, defina tambem `CF_TUNNEL_CONFIG`.
O iniciar sem `-SomenteLocal` executa `cloudflared tunnel [--config CAMINHO] run NOME`.
Sem nome, sobe apenas os servicos locais. Depois de configurado, confira `/health`
publico e uma pergunta pelo frontend remoto; confirme erro 401 no `/chat` sem chave.
Nao basta o processo `cloudflared` estar ativo para declarar integracao concluida.

O iniciar fixa `OLLAMA_HOST=127.0.0.1:11434`. Um Ollama ja iniciado e reutilizado
se estiver em loopback; listener publico provoca erro e precisa ser encerrado
pelo dono antes de reiniciar. A API usa `127.0.0.1:8001`, um worker e access log
desativado. Nao publique essas portas diretamente. `CF-Connecting-IP` tem
prioridade no limitador; acesso externo a API deve ocorrer apenas pelo Tunnel.

`run/` recebe PID, identidade do processo e logs separados de stdout/stderr.
Reexecutar iniciar nao duplica processos gerenciados. Para aplicar mudancas nas
variaveis, execute parar e iniciar. Mudancas no modo de autenticacao exigem
esse reinicio antes de reutilizar a API. Parar encerra a arvore dos processos que
este worktree iniciou, conferindo PID, instante de criacao e executavel para
proteger contra PID reutilizado. Ollama e cloudflared externos sao preservados.
Os logs sao mantidos ao parar e substituidos na proxima inicializacao.

`status.ps1` consulta Ollama, `/health` local, processo do cloudflared e,
quando configurado, `/health` publico. HTTP 503 com `status=degradado` indica
que a API responde, mas o modelo ou o indice esta indisponivel.

`GENAI_TIMEOUT_S` aceita segundos positivos e finitos, padrao 40. O timeout
inclui fila da thread, carga do indice e todas as etapas da pergunta. Retorna
504 com o contrato `indisponivel`; a chamada sincrona pode continuar em segundo
plano com resultado descartado. Um pool fixo limita a quatro geracoes ativas;
trabalhos que expiram na fila sao cancelados antes de executar.
`PF_KEEP_ALIVE` define quanto tempo o Ollama mantem o modelo carregado apos cada
chamada. A biblioteca usa 30m; `iniciar.ps1` usa 24h quando a variavel nao existe,
porque o modelo frio ja fez a primeira pergunta passar dos 40 s.
O limitador permite 20 chamadas autenticadas em janela movel de 60 segundos
por IP, responde 429 com `Retry-After` e reinicia junto com a API. Perguntas,
chaves e IPs nao sao gravados pelo log da API. IPs ficam apenas em memoria,
com entradas vencidas removidas na proxima requisicao.

`GENAI_AUTH_DESATIVADA=1` libera `/chat` para desenvolvimento local e registra
aviso. Nesse modo iniciar nao sobe cloudflared e recusa iniciar se houver um
cloudflared ja ativo. Sem chave e sem essa opcao
exata, `/chat` falha fechado com 503. `/health` e publico e mostra somente
`status`, `llm_ok` e `indice_ok`.

# GenAI no PC da equipe

Requisitos: Windows PowerShell 5.1, Ollama e cloudflared no PATH, Python >= 3.11
com `genai/requirements.txt`, modelo Ollama e indice preparados conforme
`genai/README.md`. Os scripts nao instalam programas nem criam recursos remotos.

1. Copie `.env.example` para `.env.local` nesta pasta. Preencha `GENAI_API_KEY`
   com uma chave aleatoria. Configure a mesma chave no Spring Boot e envie-a
   no header `X-API-Key`, nunca na URL.
2. Se necessario, defina `GENAI_PYTHON` com o caminho completo do Python do
   ambiente virtual. A busca padrao usa `.venv/Scripts/python.exe` do worktree,
   depois do checkout principal, depois `python.exe` do PATH.
3. Execute da raiz do worktree em um PowerShell que permita scripts locais:

   ```powershell
   powershell.exe -NoProfile -File scripts/genai/iniciar.ps1
   powershell.exe -NoProfile -File scripts/genai/status.ps1
   powershell.exe -NoProfile -File scripts/genai/parar.ps1
   ```

`.env.local` aceita `NOME=valor`, comentarios em linhas iniciadas por `#` e
aspas simples ou duplas ao redor do valor. Nao executa expressoes, expande
variaveis ou interpreta comentarios no fim da linha. Valores do arquivo
substituem os do ambiente; variaveis ausentes preservam o ambiente recebido.
`.env.local` e `run/` sao ignorados pelo Git. Credenciais do cloudflared ficam
fora do repositorio, no diretorio local de configuracao do cloudflared.

Para um tunel nomeado gerenciado localmente, siga a
[documentacao da Cloudflare](https://developers.cloudflare.com/tunnel/features/locally-managed-tunnels/create-local-tunnel/):

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
O iniciar executa `cloudflared tunnel [--config CAMINHO] run NOME`. Sem nome,
sobe apenas os servicos locais e explica como configurar.

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
O limitador permite 20 chamadas autenticadas em janela movel de 60 segundos
por IP, responde 429 com `Retry-After` e reinicia junto com a API. Perguntas,
chaves e IPs nao sao gravados pelo log da API. IPs ficam apenas em memoria,
com entradas vencidas removidas na proxima requisicao.

`GENAI_AUTH_DESATIVADA=1` libera `/chat` para desenvolvimento local e registra
aviso. Nesse modo iniciar nao sobe cloudflared e recusa iniciar se houver um
cloudflared ja ativo. Sem chave e sem essa opcao
exata, `/chat` falha fechado com 503. `/health` e publico e mostra somente
`status`, `llm_ok` e `indice_ok`.

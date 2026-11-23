# Ligar o Ponto Falante com um clique

O site publicado (https://ponto-falante.onrender.com) roda no Render, mas duas funções dependem do PC da equipe:

- **Assistente (GenAI)**: Ollama com o modelo `qwen2.5:7b` + API FastAPI da GenAI (porta 8001);
- **Conferência do letreiro (visão)**: serviço FastAPI de `visao/servico` (porta 8090).

Cada serviço sai para a internet por um Quick Tunnel gratuito da Cloudflare (`*.trycloudflare.com`, sem conta nem DNS)
e o endereço é registrado no site por `PUT /api/genai/endereco` e `PUT /api/visao/endereco`, com renovação a cada 10 min.
O robô RPA (`GET /historico` → classificar atrasos → `POST /boletim`) roda uma vez na inicialização; o agendamento diário
continua no GitHub Actions, com a guarda `scripts/genai/garantir-rpa.ps1` disparando o workflow se o cron falhar.

## Uso (Windows)

| Arquivo (raiz do repositório) | O que faz |
|---|---|
| `INICIAR_PONTO_FALANTE.bat` | Confere dependências, acorda o Render, liga tudo, registra os túneis, roda o RPA e mostra o estado. |
| `STATUS_PONTO_FALANTE.bat` | Mostra o estado e faz um teste de ponta a ponta pelo site (uma pergunta e uma foto de letreiro). |
| `PARAR_PONTO_FALANTE.bat` | Desliga tudo o que o iniciar ligou. |

Opções do iniciar: `INICIAR_PONTO_FALANTE.bat -SemNavegador -SemRpa -SemVisao`.

**O PC precisa ficar ligado e conectado à internet** enquanto os professores avaliam. Com o PC desligado, o site continua
no ar, mas mostra o assistente e a câmera como indisponíveis. Enquanto os serviços estão ligados, o iniciar impede a
suspensão automática do Windows (como um player de vídeo faz), sem mudar as configurações de energia; isso não impede a
suspensão pelo botão, pela tampa do notebook ou pelo menu Iniciar.

## Etapas do iniciar

1. **Dependências**: Ollama e cloudflared (instala pelo `winget` se faltarem), `.venv` (GenAI e RPA), `.venv-visao`
   (roda `scripts/visao/instalar.ps1` se faltar), `GENAI_API_KEY` em `scripts/genai/.env.local` e `RPA_API_KEY` no `.env`
   da raiz (as mesmas do Render; a do RPA é opcional, veja a etapa 7) e GitHub CLI.
2. **Acordar o Render**: o plano gratuito dorme após 15 min sem acesso; o primeiro acesso leva 1 a 3 min.
3. **GenAI**: `scripts/genai/iniciar.ps1 -TunelRapido`; baixa o modelo se faltar e o aquece (`keep_alive` 24 h).
4. **Visão**: `scripts/visao/iniciar.ps1 -TunelRapido`.
5. **Sem suspensão**: processo `manter-acordado.ps1`.
6. **Registro**: espera `GET /api/status` mostrar `assistente=DISPONIVEL` e `visao=CONECTADA`.
7. **RPA**: `rodar-rpa.ps1` gera e publica o boletim de ontem. Com `RPA_API_KEY` no `.env` da raiz (a mesma do Render),
   o robô roda neste PC; sem ela, o script pede ao GitHub Actions o mesmo robô (`gh workflow run rpa-diario.yml`, que
   usa os segredos do repositório) e acompanha a execução até o fim. Se já houver execução de hoje, só acompanha.

Logs: `scripts/genai/run/`, `scripts/visao/run/` e `scripts/ponto_falante/run/` (ignorados pelo Git). Nenhum script
imprime chaves.

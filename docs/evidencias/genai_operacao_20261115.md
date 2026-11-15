# Operação da GenAI em produção · validação de 15/11/2026

Ambiente: site publicado `https://ponto-falante.onrender.com` (Render) → túnel rápido da Cloudflare → API FastAPI no PC do
integrante → Ollama `qwen2.5:7b`, `PF_MODO=agente`. Medições feitas com `POST /api/chat` a partir de outro processo, em
horário de São Paulo. Nenhum conjunto de avaliação foi usado: as perguntas abaixo são exemplos públicos de operação.

## 1. Reinício com keep-alive (12:02)

`scripts/genai/parar.ps1` e `scripts/genai/iniciar.ps1 -TunelRapido`. O processo de registro gravou o novo túnel no
backend às 12:02:51, cerca de 37 s depois do início. `status.ps1` mostrou API local `llm_ok=True`, `indice_ok=True`,
cloudflared ativo, registro ativo e a guarda do agendamento do RPA ativa. `PF_KEEP_ALIVE=24h` passou a valer.

| Pergunta | Tempo | origem | tipo_resposta | Fontes |
|---|---|---|---|---|
| Quem tem direito à gratuidade no ônibus por idade? | 8,5 s | BASE_OFICIAL | FUNDAMENTADA | 3 |
| Pessoa de 62 anos paga passagem? | 10,5 s | BASE_OFICIAL | RECUSA | 0 |
| Qual o valor da tarifa do ônibus em São Paulo? | 8,7 s | BASE_OFICIAL | RECUSA | 0 |
| Posso levar meu cachorro no ônibus em Curitiba? | 0,4 s | FORA_DA_AREA | FORA_DA_AREA | 0 |
| Qual a cor do ônibus do papa? | 0,4 s | CADASTRO | CONSULTA | 1 |

A última linha revelou um desvio: a palavra "ônibus" com "qual" levava a pergunta à consulta de pontos, que respondia
"diga o nome ou o código do ponto" com selo de consulta. Corrigido no commit `1104614`
(`ConversaTransporte`: "ônibus" só indica consulta ao ponto junto de verbos como passa, para, atende ou de "ponto"),
com testes em `ConversaTransporteTest`. Depois do deploy, a mesma pergunta foi para a GenAI e recebeu recusa.

## 2. Indisponibilidade (12:19)

Com `parar.ps1`, a produção respondeu em **1,06 s**: "O assistente está indisponível agora. Tente de novo em alguns
minutos.", `disponivel=false`, `tipo_resposta=INDISPONIVEL`. A interface mostra o selo de indisponível e não exibe
confiança (testes em `frontend/src/testing/tipo-resposta.spec.ts`).

## 3. Recuperação (12:19:57 → 12:21:35)

`iniciar.ps1 -TunelRapido` terminou em 33 s. As duas primeiras tentativas de registro foram recusadas pelo backend
(o endereço novo do túnel ainda não respondia ao `/health` e ao desafio de identidade); a terceira, às 12:21:35, foi
aceita. Recuperação total: cerca de **1 min 38 s**, sem intervenção manual.

| Pergunta (após a recuperação) | Tempo | tipo_resposta |
|---|---|---|
| Quem tem direito à gratuidade no ônibus por idade? | 7,0 s | FUNDAMENTADA |
| Pessoa de 62 anos paga passagem? | 9,7 s | RECUSA |
| Qual o valor da tarifa do ônibus em São Paulo? | 8,3 s | RECUSA |
| Posso levar meu cachorro no ônibus em Curitiba? | 0,8 s | FORA_DA_AREA |
| Qual a cor do ônibus do papa? | 2,9 s | RECUSA |

## 4. Segurança do caminho

- O registro do túnel usa `PUT /api/genai/endereco` com a chave `GENAI_API_KEY` (só em `.env.local` e no Render) e o
  backend confere `/health` e um desafio de identidade antes de aceitar o endereço.
- A API local escuta em 127.0.0.1; só o túnel a expõe, e ela exige a chave de serviço.
- Nenhuma chave aparece em log, commit ou nesta evidência.

## Limites

- As recusas para "62 anos" e "tarifa" são o custo conhecido do agente v1 (recusa indevida alta no teste inédito). Não
  foram ajustadas aqui porque isso exigiria nova afinação e nova avaliação.
- Com o modelo frio (primeira carga), a primeira resposta pode passar de 40 s e cair no timeout; o keep-alive de 24 h
  reduz esse risco enquanto o PC estiver ligado.
- O túnel rápido muda de endereço a cada reinício; o processo de registro atualiza o backend sozinho.

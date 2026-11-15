# Timeout da GenAI durante a gravação

Verificação documental em 14/11/2026, sem nova geração, avaliação, reinício ou alteração de configuração.

## Evidência observada

Fonte local preservada: `scripts/genai/run/api.err.log`; capturas em
`output/playwright/genai-final/captura.json` e `output/playwright/genai-final-take2/captura.json`.
Horários abaixo em Brasília, conforme os carimbos da gravação.

| Horário | Registro da API |
|---|---|
| 18:44:31 | `Timeout no /chat`, 40.014 ms; primeira tentativa |
| 18:46:18 | `chat ok`, 23.616 ms, não recusou, duas fontes |
| 18:47:21 | `Timeout no /chat`, 40.006 ms; continuação sobre acompanhante |
| 18:48:01 | `chat ok`, 6.804 ms, recusou, zero fontes; pergunta fora da base |

A captura mede 24,109 s entre envio e resposta da consulta bem-sucedida e 40,620 s
na continuação indisponível. O vídeo mantém essa indisponibilidade entre 01:10 e 01:18.

## Causa confirmada e limites do diagnóstico

- `genai/api/app.py` aplica `GENAI_TIMEOUT_S=40` ao total da pergunta, incluindo busca e todas
  as etapas do agente. O log comprova que esse limite foi atingido dentro da API.
- O cliente Ollama tem timeout de 120 s por chamada; o agente pode fazer várias chamadas.
  Há respostas HTTP 200 do Ollama após os dois avisos de timeout da API.
- A thread síncrona pode terminar depois da resposta 504; o resultado é descartado. O pool
  limita as gerações ativas a quatro e não libera a vaga antes de a thread encerrar.
- O backend tem limite padrão de leitura de 45 s e traduz a falha para indisponibilidade.
  `/health` verifica índice e modelo disponível, sem executar uma pergunta completa.

O limite de 40 s explica a indisponibilidade observada. A razão exata da latência elevada
não foi isolada: não há telemetria por etapa, carga ou fila que permita culpar GPU, CPU ou túnel.
Não há evidência de falha do navegador nesse episódio. Aumentar o timeout isoladamente
não seria uma correção comprovada e poderia ultrapassar o limite do backend.

## Decisão para a entrega

Preservados `PF_MODO=agente`, modelo 7B, limiares, autenticação, timeouts e serviços existentes.
O vídeo e o relatório declaram o limite real; os resultados fechados não foram abertos nem
reexecutados. Não há ação de diagnóstico pendente do usuário para concluir estes arquivos.

# Validação de produção — 14/11/2026

Horários em America/Sao_Paulo. Site: https://ponto-falante.onrender.com.
Somente locais públicos; nenhuma avaliação final da GenAI foi reaberta ou executada.

## Versão recebida e deploy

- GitHub `main`: `3c4fb1a2c3aa8f5d2e1387cf6fd54230f86370e5`.
- [CI 43615475397](https://github.com/pedrobicas/ponto-falante/actions/runs/43615475397): sete jobs concluídos com sucesso
  (Angular, Gitleaks, integração, backend, Python, Semgrep e Docker/Trivy).
- Deployment GitHub `7790386218`, mesmo SHA, estado `success` às **13h30min11s**.
  [Deploy Render](https://dashboard.render.com/web/srv-dbqbfoh42hec73cuo300/deploys/dep-dbs8oaqjnfac73c0igtg).
- Às 13h39: `/actuator/health` = `UP`; `/api/status` = SPTrans `REAL`, assistente `DISPONIVEL`.
  O endpoint de versão expõe `1.0.0`, não o SHA; a identificação exata vem do registro de deploy.

## Consultas reais

Roteiro existente `scripts/integracao/conversar.py`, executado às 13h39–13h40, com pausa de 1 s entre perguntas.
Transcrição local preservada em `.validation/conversa-producao-3c4fb1a.txt`.

| Verificação | Observação |
|---|---|
| Previsões do ponto público `70016916` | Fonte `OLHO_VIVO`, tipo `PREVISAO`, 14 ônibus na consulta das 13h39 |
| Próximo ônibus da `875A-10` | Primeira resposta incluiu 3 e 29 min; “E o próximo?” passou ao segundo veículo, mantendo ponto/linha/sentido |
| Sentido contrário | Selecionou ponto cadastrado na direção Aeroporto e consultou previsão real |
| Onde embarcar | Pediu sentido e referência, ofereceu três paradas próximas e informou distância em linha reta |
| Continuação sobre via | Defeito reproduzido: após as opções de embarque, “Esse ônibus passa na Avenida Paulista?” virou busca de endereço |
| GenAI de direitos e Bilhete Único | Respostas disponíveis com fontes; acompanhante sem evidência retornou “não consta”; injeção recusada |
| Boletim no chat | Origem `BOLETIM`, categoria `ESTIMADO`, data 13/11, aviso explícito de que não confirma a situação de hoje |

As respostas de direitos verificam o funcionamento do produto e suas fontes, não constituem uma nova medida de
acurácia nem alteram o placar congelado da GenAI. Todos os pedidos do roteiro retornaram HTTP 200; isso não esconde
o defeito semântico de continuidade descrito acima.

## Boletim e navegador

- Referência **13/11**, gerado em **14/11 às 12h36**: compatível com o robô diário que consolida o dia anterior.
- **17 consultas reais**, nenhuma simulada, **35,4%** de cobertura e aviso de amostragem parcial.
  A fonte comprova consultas a previsões; não comprova chegadas, acidentes ou atrasos medidos.
- Roteiro `validar_boletim_chat.js` executado no Edge em produção, com prefixo de capturas separado para preservar
  evidências anteriores. Desktop, celular a 175%, chat e falha controlada: **sem overflow e sem violações axe**.
- Voz recebeu o resumo correto em `pt-BR`; selo `Estimado`, navegação e histórico da conversa conferidos.
- Falha HTTP 503 interceptada apenas no navegador produziu o estado de recuperação. Nenhum serviço foi interrompido.
- Capturas locais: `output/playwright/boletim-prod-3c4fb1a-*.png`. Nenhuma publicação de boletim de teste em produção.

## Correções resultantes e validação local

- Pergunta explícita de trajeto tem prioridade sobre a referência pendente de embarque, preservando ponto, linha e
  sentido. Quatro regressões falharam antes da mudança e passaram depois; **61 testes focados** passaram.
- Título da aba do boletim corrigido de “atrasos” para **“esperas previstas”**, coerente com os dados apresentados.
- Build Angular de produção concluído. Nenhuma suíte completa repetida localmente.
- Logs: `.validation/assistente-via-regressao-antes.log` e `.validation/assistente-via-regressao-depois.log`.

O resultado do deploy dessas correções será registrado no estado do projeto depois da CI e da verificação remota.

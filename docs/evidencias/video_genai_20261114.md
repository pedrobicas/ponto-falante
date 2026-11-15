# Vídeo GenAI — 14/11/2026

Arquivo local: `entregaveis/Ponto_Falante_GenAI.mp4`, **190 s (3min10s)**, H.264, 1600 × 900, 25 fps,
sem stream de áudio. Narração humana: `entregaveis/ROTEIRO_GENAI.md`. URL pública ainda pendente.

Fechamento: arquivo existente preservado byte a byte; decodificação completa com FFmpeg
`-v error -xerror`, código 0 e log vazio. Quadros das cenas inspecionados, incluindo resposta,
fontes, indisponibilidade e cartões finais. SHA-256:
`470efb3a33257aa6710e3e207432b31adbe07ec8aa7918206a50d83f82780f08`.
Diagnóstico sem mudança da versão estável: [timeout_genai_20261114.md](timeout_genai_20261114.md).

## Origem e edição

- Reutilizado `.validation/video-genai/01-transporte.webm` e seu log: consulta real de 13h53, linha 875A-10,
  ponto público 70016916, e “E o próximo?” preservando ponto/linha/sentido. O trecho foi desacelerado para leitura.
- Novas capturas em `output/playwright/genai-final-take2/`: `genai-direitos.webm`, `genai-limite.webm`,
  `genai-boletim.webm`. `captura.json` conserva perguntas, respostas reais, fontes, eventos e verificação de voz.
- Bruto anterior com timeout preservado em `output/playwright/genai-final/`. Os WAV artificiais antigos não foram usados.
- Roteiro de edição: `scripts/video/v1/roteiro_genai_final.json`; montagem: `scripts/video/v1/montar_genai_final.py`.
  A timeline entregue registra cada origem, corte, duração e posição final. Esperas encurtadas e velocidades ajustadas;
  nenhuma resposta alterada ou simulada. Cartões finais identificados como resumo do relatório, não como execução.

## O que foi observado

| Trecho | Resultado real |
|---|---|
| Direitos | “Tenho 66 anos, posso andar gratuitamente?” respondeu com fontes da FAQ SPTrans 65+ e Lei 10.741/2003, em cerca de 24 s |
| Voz | Clique real em “Ouvir resposta”; Web Speech API recebeu o texto retornado em `pt-BR`, mantendo a implementação original |
| Acessibilidade | Letras “Grande”, alto contraste escuro e retorno ao histórico; duas mensagens preservadas, sem overflow na tela final |
| Limite operacional | Primeira tentativa e continuação “E meu acompanhante?” excederam 40 s; continuação indisponível aparece no vídeo |
| Recusa | Pergunta sobre ônibus em Curitiba retornou `nao_consta=true`, disponível, sem fontes; o encaminhamento fixo 156 é de São Paulo |
| RPA no chat | Origem `BOLETIM`, `ESTIMADO`, referência 13/11, aviso de amostragem parcial e de que não confirma hoje |

Não há garantia de áudio audível pela captura silenciosa nem validação de leitores de tela externos. A recusa
fora da cidade não comprova adequação do encaminhamento ao 156. A página de saúde pode indicar disponibilidade
mesmo quando uma geração excede o timeout; nenhuma configuração do modelo ou limite foi alterada para a gravação.

O placar e os cinco erros foram transcritos de `genai/RELATORIO.md`; **nenhum conjunto final fechado foi aberto,
executado ou usado para ajustes**. Nenhuma suíte de testes repetida. A captura é demonstração funcional, não nova avaliação de acurácia.

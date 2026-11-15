# Evidência do vídeo GenAI (versão 2, gravada em 14/11/2026)

Arquivo final local: `entregaveis/Ponto_Falante_GenAI.mp4` (pasta ignorada pelo Git). H.264 1920 x 1080, 30 fps, **147 s**, sem
trilha de áudio. A versão anterior (190 s, 1600 x 900) ficou guardada em `entregaveis/versao_anterior_20261114/`.

## Como foi gravado

- Navegador Edge sem interface, controlado pelo Playwright, no site publicado `https://ponto-falante.onrender.com`. Quadros do
  screencast do DevTools em 1920 x 1080 (página de 1280 x 720 com escala 1,5). O cursor desenhado acompanha os eventos reais de mouse.
- Captura: `scripts/video/cap_genai.js`. Montagem: `scripts/video/compor.py` com `scripts/video/edl_genai.json`, que só corta,
  enquadra e encadeia os quadros gravados. O rodapé mostra o capítulo e a origem do conteúdo.
- O modelo local (Ollama `qwen2.5:7b`) foi aquecido com duas perguntas antes da gravação. Na primeira tentativa, com o modelo frio,
  a pergunta de gratuidade excedeu o timeout de 40 s da API; essa tentativa foi descartada e não aparece no vídeo.
- Placares: `scripts/video/mostrar.py placar` apenas lê os CSVs já registrados. Nenhum conjunto de teste foi reexecutado.

## O que aparece

| Trecho | Conteúdo | Resultado observado |
|---|---|---|
| 00:07-00:19 | "Qual ônibus vai para o Centro saindo da Paulista, 1374?" | Linhas diretas pelo cadastro GTFS da SPTrans, cerca de 1,5 s |
| 00:19-00:28 | "Quanto falta para a 875A-10?" | Previsão em tempo real da SPTrans, calculada às 23:43, cerca de 1,5 s |
| 00:28-00:39 | "E no sentido contrário?" | Ponto do sentido oposto e nova previsão, mantendo o contexto |
| 00:39-01:04 | "Tenho 66 anos, posso andar gratuitamente?" | Base oficial com 2 fontes citadas (SPTrans 65+ e Lei 10.741), cerca de 20 s; espera acelerada 8x e sinalizada; botão "Ouvir resposta" |
| 01:04-01:16 | "Posso levar meu cachorro no ônibus em Curitiba?" | Recusa honesta com aviso e encaminhamento ao 156, cerca de 5,6 s; espera acelerada 3x e sinalizada |
| 01:16-01:48 | Ajustes: letra Grande e alto contraste escuro | A conversa continua na tela da assistente com o novo visual |
| 01:48-02:08 | Diagramas Mermaid do `README.md` e do `genai/RELATORIO.md` | Arquitetura do MVP e pipeline do agente |
| 02:08-02:27 | Placar do teste inédito v3 e do reparo de recusa no DEV | Valores idênticos aos CSVs registrados em `genai/` |

Limites: o vídeo não tem som, então mostra o acionamento da Web Speech API sem comprovar a reprodução audível. A recusa sobre
Curitiba conserva o encaminhamento fixo para o 156 de São Paulo. Previsões são estimativas da SPTrans, não chegadas observadas.

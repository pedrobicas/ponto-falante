# Evidência do vídeo GenAI (versão 3: conversa regravada em 15/11/2026)

Arquivo final local: `entregaveis/Ponto_Falante_GenAI.mp4` (pasta ignorada pelo Git). H.264 1920 x 1080, 30 fps, **141,7 s**,
sem trilha de áudio, decodificação completa sem erros (`entregaveis/VALIDACAO_VIDEOS.json`). A versão 2 (147 s, gravada em
14/11) está em `entregaveis/versao_anterior_20261115/`; a versão 1 (190 s, 1600 x 900), em `entregaveis/versao_anterior_20261114/`.

**Por que foi regravada:** na versão 2, a pergunta "Posso levar meu cachorro no ônibus em Curitiba?" terminava com o
encaminhamento ao 156 da SPTrans, que é de São Paulo. Em 15/11 o backend passou a reconhecer perguntas sobre outras cidades
(`ForaDaArea.java`, `tipo_resposta = FORA_DA_AREA`, testes em `TipoRespostaTest`) e a resposta agora diz que o serviço cobre
só São Paulo e orienta procurar o órgão de transporte da cidade citada, sem inventar contato. Só a cena da conversa
(`genai_chat`) foi capturada de novo; diagramas e placares são os mesmos quadros da versão 2.

## Como foi gravado

- Navegador Edge sem interface, controlado pelo Playwright, no site publicado `https://ponto-falante.onrender.com`, em
  15/11/2026 por volta de 12h25 (São Paulo). Quadros do screencast do DevTools em 1920 x 1080 (página de 1280 x 720 com
  escala 1,5). O cursor desenhado acompanha os eventos reais de mouse.
- Captura: `scripts/video/cap_genai.js <cenas> <trabalho> genai_chat`. Montagem: `scripts/video/compor.py` com
  `scripts/video/edl_genai.json`, que só corta, enquadra e encadeia os quadros gravados. A linha do tempo de cada plano é
  gravada em `Ponto_Falante_GenAI.timeline.json`.
- O serviço GenAI tinha acabado de ser reiniciado (`PF_KEEP_ALIVE=24h`) e o modelo `qwen2.5:7b` já estava carregado.
- Placares: `scripts/video/mostrar.py placar` apenas lê os CSVs já registrados. Nenhum conjunto de teste foi reexecutado.

## O que aparece

| Trecho | Conteúdo | Resultado observado |
|---|---|---|
| 00:07-00:18 | "Qual ônibus vai para o Centro saindo da Paulista, 1374?" | Linhas diretas pelo cadastro GTFS da SPTrans, cerca de 1,6 s |
| 00:19-00:28 | "Quanto falta para a 875A-10?" | Previsão em tempo real da SPTrans, calculada às 12:24, cerca de 1,5 s |
| 00:28-00:38 | "E no sentido contrário?" | Ponto do sentido oposto (Av. Paulista, 1578) e nova previsão, mantendo o contexto |
| 00:38-01:04 | "Tenho 66 anos, posso andar gratuitamente?" | Base oficial com 2 fontes citadas (SPTrans 65+ e Lei 10.741), cerca de 7,4 s; espera acelerada 8x e sinalizada; botão "Ouvir resposta" |
| 01:05-01:15 | "Posso levar meu cachorro no ônibus em Curitiba?" | Aviso "Fora da área atendida", cerca de 1,5 s, sem GenAI e sem telefone inventado; selo FORA DA ÁREA |
| 01:16-01:42 | Ajustes: letra Grande e alto contraste escuro | A conversa continua na tela da assistente com o novo visual |
| 01:43-02:02 | Diagramas Mermaid do `README.md` e do `genai/RELATORIO.md` | Arquitetura do MVP e pipeline do agente |
| 02:03-02:22 | Placar do teste inédito v3 e do reparo de recusa no DEV | Valores idênticos aos CSVs registrados em `genai/` |

Limites: o vídeo não tem som, então mostra o acionamento da Web Speech API sem comprovar a reprodução audível. Previsões são
estimativas da SPTrans, não chegadas observadas. A narração será gravada pelo próprio integrante, seguindo
`entregaveis/ROTEIRO_GENAI.md`, e misturada com `scripts/video/narrar.py`.

# Roteiro de narração do vídeo de demonstração (Visão Computacional)

Vídeo: `entregaveis/visao/Ponto_Falante_Visao_demo.mp4` (fora do Git), **cerca de 1 min 22 s**, 1920 x 1080, 30 fps,
sem áudio. Montado com `scripts/video/compor.py` a partir de `scripts/video/visao/edl_visao_demo.json`, só com capturas
reais de 17/11/2026: o `src/demo.py` rodando na CPU e três conferências no site publicado (placa borrada na miniatura).
As esperas do modelo aparecem aceleradas, com o selo "acelerada" na tela. Os tempos abaixo são do vídeo final.

Uma versão longa (4 min 07 s, com slides de dataset, treino e métricas) pode ser montada com
`scripts/video/visao/edl_visao.json`; a entrega usa a curta.

| # | Tempo | Na tela | Fala |
|---|---|---|---|
| 1 | 0:00 – 0:05 | Título e integrantes | "Ponto Falante: a visão computacional que lê a linha do ônibus para quem não enxerga." |
| 2 | 0:05 – 0:31 | Terminal: `demo.py` com fotos fazendo o papel da câmera do ponto; anúncios 647P-10, "não consegui ler" e as detecções recebidas pela API | "Aqui o nosso YOLO11 nano, treinado com fotos de ônibus de São Paulo, roda na CPU. Ele encontra o ônibus e o letreiro, o OCR lê a linha, e só anuncia se a linha passa naquele ponto. Quando o letreiro mostra só o destino, ele avisa que não conseguiu ler. Cada anúncio vai para a API." |
| 3 | 0:31 – 0:43 | Vídeo anotado: caixas do ônibus e do letreiro | "Esta é a saída do detector, com rostos e placas borrados por causa da LGPD." |
| 4 | 0:43 – 0:58 | Site publicado: a pessoa marca a linha 647P-10, envia a foto e recebe **CONFERE** | "No aplicativo publicado, a pessoa marca a linha que espera e envia a foto do letreiro. O modelo responde que a linha confere, e o aplicativo fala o resultado." |
| 5 | 0:58 – 1:07 | Mesma foto, esperando a 477P-10: **"parece ser outra linha"** | "Se for outra linha, ele alerta e pede para confirmar com o motorista." |
| 6 | 1:07 – 1:16 | Letreiro só com o destino: **"Não deu para ler o letreiro"** | "E se não der para ler, ele diz isso, em vez de arriscar uma linha errada." |
| 7 | 1:16 – 1:22 | Repositório | "Código, modelo e relatório estão no repositório. Obrigado!" |

Total de fala: cerca de 1 min 5 s.

## Como gravar e juntar a voz

1. Grave numa sala silenciosa, com o microfone perto (celular serve), assistindo ao vídeo, de uma vez ou um arquivo
   por bloco.
2. Junte ao vídeo sem recodificar a imagem (o script normaliza o volume e nunca sobrescreve o original):

```powershell
# gravação única, começando 0,3 s depois do início
.\.venv\Scripts\python.exe scripts/video/narrar.py entregaveis/visao/Ponto_Falante_Visao_demo.mp4 --audio minha_voz.m4a --atraso 0.3

# ou um arquivo por bloco: falas.json = [{"inicio": 0.3, "arquivo": "falas/01.m4a"}, {"inicio": 5.0, "arquivo": "falas/02.m4a"}, ...]
.\.venv\Scripts\python.exe scripts/video/narrar.py entregaveis/visao/Ponto_Falante_Visao_demo.mp4 --trechos falas.json
```

Inícios por bloco para o `falas.json`: 0,3 · 5,0 · 31,2 · 43,0 · 58,4 · 67,5 · 76,1.

3. Publique no YouTube como **não listado**, teste o link numa janela anônima e preencha `VIDEO:` em
   `relatorio/info.txt`; depois gere o PDF de novo (`python relatorio/gerar_relatorio.py`) e cole o link no README.

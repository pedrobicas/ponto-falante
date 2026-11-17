# Roteiro de narração do vídeo de demonstração (Visão Computacional)

Vídeo: `entregaveis/visao/Ponto_Falante_Visao.mp4` (fora do Git), **4 min 07 s**, 1920 x 1080, 30 fps, sem áudio.
Montado com `scripts/video/compor.py` a partir de `scripts/video/visao/edl_visao.json`: slides com os números do relatório
e capturas reais de 17/11/2026 (o `src/demo.py` rodando na CPU e três conferências no site publicado). Os tempos abaixo
são do vídeo final (`Ponto_Falante_Visao.timeline.json`).

Ritmo de referência: cerca de 2,5 palavras por segundo. Cada bloco cabe na janela indicada com folga; se sobrar tempo,
deixe o silêncio, principalmente durante as esperas reais da conferência (de 8 a 9 s, latência do modelo na CPU).

| # | Tempo | Na tela | Fala |
|---|---|---|---|
| 1 | 0:00 – 0:13 | Título, integrantes e a saída real do modelo num ônibus 647P-10 | "Este é o Ponto Falante, da Global Solution 2026.2 da FIAP. Neste vídeo mostramos o componente de visão computacional: o modelo que enxerga o ônibus chegando ao ponto e lê a linha no letreiro, para quem não consegue ver." |
| 2 | 0:14 – 0:31 | O problema | "Em São Paulo, saber qual ônibus está parando depende do letreiro, uma informação só visual. Para uma pessoa cega ou com baixa visão, isso significa pedir ajuda a desconhecidos ou perder a condução. Nosso objetivo é transformar essa imagem em uma frase falada, sem nunca anunciar a linha errada." |
| 3 | 0:31 – 0:56 | Dataset próprio: 342 → 211 → −13 → 198 | "Não existe um conjunto público de letreiros de ônibus paulistanos rotulados, então montamos o nosso. Baixamos 342 fotos de ônibus da capital, com licença livre, do Wikimedia Commons. Dois modelos professores, o YOLO onze x e o Grounding DINO, pré-rotularam ônibus e letreiros, e a equipe revisou tudo à mão, descartando 13 fotos. Ficaram 198 imagens, com 225 ônibus e 152 letreiros." |
| 4 | 0:56 – 1:11 | Treino do YOLO11n e curvas de perda | "Com esses dados, treinamos um YOLO onze nano com duas classes customizadas, ônibus e letreiro, por transfer learning. O aumento de dados varia brilho, rotação e zoom, mas não espelha as imagens, porque letreiro espelhado não existe no mundo real." |
| 5 | 1:12 – 1:33 | Métricas no conjunto de teste e matriz de confusão | "No conjunto de teste, com fotos que o modelo nunca viu, o mAP cinquenta foi de 0,87: 0,91 para ônibus e 0,83 para letreiro. Na leitura da linha, o sistema acertou 11 de 25 letreiros em um único quadro, e não anunciou nenhuma linha errada. Nos 16 letreiros que mostravam só o destino, ele avisou que não conseguiu ler." |
| 6a | 1:34 – 1:45 | Terminal: o comando do `demo.py` é digitado | "Agora, o modelo rodando de verdade, na CPU do nosso computador. Seis fotos de ônibus fazem o papel da câmera do ponto." |
| 6b | 1:45 – 1:58 | Primeiro anúncio, 647P-10; depois trecho acelerado (selo no canto) | "Em cada quadro, o YOLO encontra o ônibus e o letreiro, o EasyOCR lê o recorte, e a leitura só vale se a linha passa naquele ponto. Aqui ele anunciou a 647P-10." |
| 6c | 1:58 – 2:09 | "Ônibus chegando. Não consegui ler a linha." | "Nesta foto o letreiro mostrava só o destino, e ele avisou que não conseguiu ler, em vez de chutar." |
| 6d | 2:09 – 2:21 | Fim do processamento e as detecções recebidas pela API | "Cada anúncio é enviado para a API, que recebeu todas as detecções: 647P-10, 5109-10, 2100-10, 288 e 695H-10." |
| 6e | 2:21 – 2:33 | Vídeo anotado: caixas de ônibus e letreiro | "Este é o vídeo que o próprio programa gera, com as caixas do ônibus e do letreiro. Rostos e placas saem borrados, por causa da LGPD." |
| 7 | 2:33 – 3:10 | Site publicado: ponto da Av. Faria Lima, 3015, linha esperada 647P-10, envio da foto e resultado **CONFERE** (em 3:02) | "O modelo também está integrado ao MVP publicado. Na tela de embarque assistido, a pessoa escolhe o ponto, aqui a Avenida Faria Lima, e marca a linha que espera, a 647P-10. Ela envia a foto do letreiro, e o Spring Boot repassa a imagem ao serviço de visão, que roda no computador da equipe e chega ao site por um túnel seguro. *(pausa durante a espera)* Em cerca de nove segundos vem a resposta: a linha confere, com 78% de confiança, e o aplicativo fala o resultado." |
| 8 | 3:10 – 3:29 | Mesma foto, linha esperada 477P-10: **"parece ser outra linha"** (em 3:21) | "Se a pessoa espera outra linha, aqui a 477P-10, *(pausa)* o aplicativo alerta que o ônibus parece ser o 647P-10 e pede para confirmar com o motorista antes de embarcar." |
| 9 | 3:29 – 3:46 | Letreiro só com o destino: **"Não deu para ler o letreiro"** (em 3:39) | "E quando o letreiro mostra só o destino, *(pausa)* o sistema não chuta: avisa que não conseguiu ler a linha. Para uma pessoa cega, isso é mais seguro do que um anúncio errado." |
| 10 | 3:46 – 4:06 | Conclusão, repositório e créditos | "Nenhuma foto é guardada: o serviço devolve só o resultado. Como próximos passos, queremos ampliar o dataset com fotos de noite e de chuva e treinar um leitor específico para letreiros de LED. O código, o modelo treinado, os testes e o relatório estão no repositório do projeto. Obrigado!" |

Total de fala: cerca de 3 min 15 s em 4 min 07 s de vídeo.

## Como gravar e juntar a voz

1. Grave numa sala silenciosa, com o microfone perto (celular serve). Pode gravar tudo de uma vez assistindo ao vídeo,
   ou um arquivo por bloco.
2. Junte ao vídeo sem recodificar a imagem (o script normaliza o volume e nunca sobrescreve o original):

```powershell
# gravação única, começando 0,3 s depois do início
.\.venv\Scripts\python.exe scripts/video/narrar.py entregaveis/visao/Ponto_Falante_Visao.mp4 --audio minha_voz.m4a --atraso 0.3

# ou um arquivo por bloco: falas.json = [{"inicio": 0.3, "arquivo": "falas/01.m4a"}, {"inicio": 14.0, "arquivo": "falas/02.m4a"}, ...]
.\.venv\Scripts\python.exe scripts/video/narrar.py entregaveis/visao/Ponto_Falante_Visao.mp4 --trechos falas.json
```

Inícios por bloco para o `falas.json`: 0,3 · 14,0 · 31,6 · 56,2 · 72,0 · 94,3 · 105,4 · 118,0 · 129,0 · 141,5 · 153,2 ·
190,4 · 209,3 · 226,4.

3. Publique no YouTube como **não listado**, teste o link numa janela anônima e preencha `VIDEO:` em
   `relatorio/info.txt`; depois gere o PDF de novo (`python relatorio/gerar_relatorio.py`) e cole o link no README.

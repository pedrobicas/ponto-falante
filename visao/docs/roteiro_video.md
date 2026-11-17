# Roteiro do vídeo de demonstração (até ~4 min)

**Gravação:** gravador de tela do Windows (Win+Alt+R) ou OBS Studio. Microfone próximo, sem música alta.
**Antes de gravar:** abra dois terminais na pasta do projeto, já com o `.venv` ativado
(`.venv\Scripts\activate`), e deixe abertos o README, a pasta `resultados/` e `dados/revisao/folha_05.jpg`.
**Publicação:** YouTube como **não listado**. Teste o link numa janela anônima e cole-o no README e em
`relatorio/info.txt`.

| Tempo | Na tela | Fala (pode adaptar) |
|---|---|---|
| 0:00–0:20 | README no GitHub (título + integrantes) | "Somos o grupo do Ponto Falante. Esta é a parte de visão computacional: o componente que enxerga o ônibus chegando ao ponto e lê a linha no letreiro." |
| 0:20–0:40 | Uma foto de ônibus de SP com o letreiro | "Para quem é cego ou tem baixa visão, saber qual ônibus está chegando depende do letreiro, que é só visual. Nosso objetivo é transformar essa imagem num anúncio de voz." |
| 0:40–1:30 | `docs/creditos_imagens.csv` e uma folha de revisão (`dados/revisao/folha_05.jpg`) | "Não existe dataset de letreiros de ônibus de São Paulo, então montamos o nosso. Baixamos 342 fotos de ônibus da capital com licença livre do Wikimedia Commons, com autor e licença registrados. Dois modelos grandes, o YOLO11x e o Grounding DINO, marcaram ônibus e letreiros automaticamente, e nós revisamos tudo nessas folhas, descartando maquetes, fotos antigas e marcações erradas." |
| 1:30–2:10 | `resultados/results.png`, `confusion_matrix_normalized.png` e a tabela de resultados do README | "Com isso treinamos um YOLO nano com duas classes, ônibus e letreiro, sem espelhar as imagens, porque letreiro espelhado não existe. No teste, com fotos que o modelo nunca viu, tivemos mAP50 de 0,87: 0,91 para ônibus e 0,83 para letreiro, a classe mais difícil. Cada imagem leva 8 milissegundos." |
| 2:10–3:10 | **Demo ao vivo**: terminal 1 com a API falsa, terminal 2 rodando `src/demo.py` (comandos abaixo); depois abra `resultados/demo.mp4` | "Aqui as fotos simulam a câmera do ponto. O sistema detecta o ônibus, recorta o letreiro e lê com OCR em três versões da imagem. A leitura só vale se a linha passa naquele ponto, e o anúncio só sai quando vários quadros concordam. Vejam que a API recebeu cada detecção. Nesse ônibus o letreiro mostrava só o destino, Sacomã: em vez de chutar, ele avisou 'não consegui ler a linha'." |
| 3:10–3:30 | Tabela do OCR no README | "Na leitura, acertamos 44% dos letreiros num único quadro e não anunciamos nenhuma linha errada. Para uma pessoa cega, anunciar a linha errada é pior do que dizer que não conseguiu ler." |
| 3:30–3:45 | Terminal 1: Ctrl+C na API; rode a demo de novo e mostre o aviso "guardada na fila" | "Se a API cair, nada trava: a detecção vai para uma fila local e é reenviada depois." |
| 3:45–4:00 | Um quadro do `demo.mp4` com a placa borrada | "Nenhuma imagem é enviada nem guardada, só o resultado. O que aparece na tela tem rostos e placa borrados, por causa da LGPD. Obrigado!" |

**Comandos da demo**

```bash
# terminal 1 — API falsa com as linhas que passam no ponto
python src/api_fake.py --linhas "647P-10,5109-10,2100-10,288,695H-10,576C-10,574A-21,8000-10,875A-10"

# terminal 2 — câmera simulada
python src/demo.py --fonte amostras/imagens/demo --ponto 260015039 --repetir-imagem 30 --gpu --saida resultados/demo_ao_vivo.mp4
```

O `demo.py` não abre janela neste ambiente (o OpenCV instalado é "headless"). Por isso, depois de rodar,
mostre no vídeo o arquivo `resultados/demo.mp4`, que já está pronto, enquanto o terminal 1 exibe as linhas
`Detecção recebida`.

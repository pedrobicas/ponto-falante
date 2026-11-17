# Dataset: fonte, licenças e rotulagem

Classes do modelo: **`onibus`** (0) e **`letreiro`** (1).
Todas as fotos são de **ônibus da cidade de São Paulo**, vêm do Wikimedia Commons e têm licença livre.
Nenhuma foto foi tirada pela equipe.

## Por que não usamos um dataset pronto
Procuramos um dataset público com ônibus e letreiros **de São Paulo** já rotulados e não encontramos.
Os conjuntos do Roboflow Universe e do Open Images mostram ônibus de outros países, com outros
letreiros, cores e fontes. Treinar com eles ensinaria o modelo a reconhecer ônibus de Singapura ou
de Londres, não os da SPTrans. Por isso montamos um dataset próprio, reutilizando fotos livres da internet.

## Passo 1: coleta automática ([ferramentas/baixar_commons.py](../ferramentas/baixar_commons.py))
- Percorre categorias do Commons sobre ônibus da capital: *Buses in São Paulo*, *São Paulo Transporte*,
  *Articulated buses in São Paulo*, *Bi-articulated buses in São Paulo*, *Trolleybuses in São Paulo*,
  *Terminal Bandeira* e *Corredor Metropolitano São Mateus–Jabaquara*.
- Aceita só **domínio público, CC0, CC BY e CC BY-SA**. Fotos com outras licenças são recusadas automaticamente.
- Baixa uma versão de 1280 px pela API pública do Commons (não precisa de conta nem de chave).
  Respeita o limite de requisições e confere a assinatura do arquivo (JPEG/PNG) antes de gravar.
- Registra autor, licença e URL de **cada** foto em [creditos_imagens.csv](creditos_imagens.csv).
  As licenças CC BY e CC BY-SA exigem essa atribuição.
- Resultado: **342 fotos** baixadas e 5 recusadas por licença.

## Passo 2: pré-rotulagem com modelos "professores" ([ferramentas/pre_rotular.py](../ferramentas/pre_rotular.py))
Não havia tempo para desenhar centenas de caixas à mão. Usamos dois modelos grandes já treinados
para gerar as caixas automaticamente:

| Classe | Modelo professor | Como |
|---|---|---|
| `onibus` | **YOLO11x** (Ultralytics, treinado no COCO) | classe COCO `bus`, confiança ≥ 0,45; ônibus com menos de 3% da imagem são ignorados |
| `letreiro` | **Grounding DINO** (IDEA-Research, vocabulário aberto) | recebe o texto *"bus destination sign. electronic sign. route number display."* e procura isso na foto |

O Grounding DINO não conhece os letreiros de SP e também marca papéis no para-brisa e o número de frota.
Por isso as caixas passam por **filtros geométricos**:
- o centro do letreiro precisa estar **dentro de um ônibus**, nos **35% de cima** dele;
- precisa ter formato de **faixa** (largura ≥ 2,2 × altura);
- precisa ter entre 8% e 80% da largura do ônibus e pelo menos 40 px de largura (o OCR precisa conseguir ler);
- fica **1 letreiro por ônibus**: o mais confiável.

> Testamos antes o **YOLO-World**, outro detector de vocabulário aberto. Ele marcava o ônibus inteiro
> como "letreiro" e foi descartado. Esse teste está registrado no relatório.

Fotos sem nenhum ônibus detectado foram descartadas automaticamente. Eram fotos de terminais vazios,
de interiores e de prédios.

## Passo 3: revisão humana (pessoa no circuito)
O script gera **folhas de revisão** (grades de 20 miniaturas, com ônibus em azul e letreiro em vermelho).
Conferimos todas as folhas e descartamos 13 fotos, listadas com o motivo em
[ferramentas/revisao_descartes.txt](../ferramentas/revisao_descartes.txt):
- maquetes e miniaturas;
- fotos históricas ou em preto e branco (ônibus que não circulam mais);
- multidões e cartazes;
- letreiros marcados no lugar errado.

**Limitação conhecida:** alguns letreiros reais ficaram sem caixa, como os apagados, os muito
inclinados ou os pequenos. Isso puxa o *recall* da classe `letreiro` para baixo, porque o modelo
aprende que parte dos letreiros "não é letreiro". Com mais tempo, a correção seria completar essas
caixas à mão (por exemplo, no Roboflow ou no CVAT).

## Passo 4: divisão e reprodutibilidade ([ferramentas/treinar.py](../ferramentas/treinar.py))
- Divisão de **70% treino / 20% validação / 10% teste**, com semente 42 e embaralhamento reprodutível.
- O conjunto de **teste nunca é usado no treino**. As métricas do relatório vêm só dele.
- A composição final é salva em `resultados/dataset.json` e entra automaticamente no relatório.

## Vídeo de demonstração (câmera simulada)
Não há câmera instalada num ponto real, e o Commons não tem vídeos de ônibus de SP com licença livre.
A demonstração simula a câmera passando as **imagens de teste** quadro a quadro
(`src/demo.py --fonte pasta/`), com a API fake do MVP respondendo as linhas do ponto.
Antes de mostrar ou salvar, o `demo.py` borra rostos e a região da placa (LGPD).

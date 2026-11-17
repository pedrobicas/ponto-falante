# Guia de integração: componente Visão do Ponto Falante

Este pacote é a parte de **visão computacional** do Ponto Falante. Ele recebe imagens de uma câmera
(vídeo, webcam ou pasta de fotos), detecta o ônibus, lê a linha no letreiro e **envia o resultado para a
API da plataforma**. A plataforma usa esse resultado para mostrar e falar o anúncio ao passageiro.

A visão **não guarda nem envia imagens**: só manda o JSON com a linha lida.

## 1. O que a plataforma precisa expor

A visão conversa com a plataforma por dois endpoints HTTP. Basta a API da plataforma atender a este contrato.

### `GET /pontos/{codigo}/previsoes`
Devolve as linhas que passam no ponto. A visão usa essa lista para **validar o OCR**: só anuncia uma linha que
esteja nela. O resultado fica em cache por 60 s.

Formatos aceitos (o único campo lido é `linha`):
```json
[{"linha": "8000-10"}, {"linha": "875A-10"}]
```
ou
```json
{"previsoes": [{"linha": "8000-10"}, {"linha": "875A-10"}]}
```
Use o **código da linha no formato da SPTrans**, como aparece no letreiro: `8000-10`, `875A-10`, `N101-11`.
Campos extras (minutos, sentido etc.) são ignorados.

### `POST /deteccoes`
A visão envia um anúncio por ônibus:
```json
{"ponto": "260015039", "linha_lida": "8000-10", "confianca": 0.79, "criado_em": "2026-11-17T12:09:11+00:00"}
```
- `linha_lida` = `null` significa **"chegou um ônibus, mas não consegui ler a linha"**. A plataforma deve
  anunciar algo como *"Ônibus chegando. Não consegui ler a linha."*, e **não** inventar uma linha.
- `confianca` vai de 0 a 1.
- Qualquer resposta 2xx é considerada sucesso.

> Para testar sem a plataforma, `src/api_fake.py` implementa exatamente esse contrato.

## 2. Instalação

Python 3.10–3.12. GPU NVIDIA é opcional (na CPU funciona, só mais devagar).
```bash
python -m venv .venv
.venv\Scripts\activate            # Linux/Mac: source .venv/bin/activate
pip install ultralytics easyocr opencv-python numpy requests
```
(O `requirements.txt` completo também instala ferramentas de treino e relatório, que não são necessárias
para a integração.)

Na primeira execução, o EasyOCR baixa os modelos dele (~100 MB) do GitHub oficial.

## 3. Teste rápido (5 minutos, sem a plataforma)
```bash
# terminal 1: API falsa com as linhas do ponto
python src/api_fake.py --linhas "647P-10,5109-10,2100-10,288,695H-10"

# terminal 2: câmera simulada com as 6 fotos de exemplo
python src/demo.py --fonte amostras/imagens/demo --ponto 260015039 --repetir-imagem 30 --saida teste.mp4
```
O terminal 1 deve mostrar 6 linhas `Detecção recebida`: cinco com a linha certa e uma com `linha_lida: None`,
de um ônibus cujo letreiro mostrava só o destino. Acrescente `--gpu` se houver placa NVIDIA.

## 4. Ligando na plataforma

Aponte a visão para a API real pela variável de ambiente ou pelo parâmetro `--api`:
```bash
set PONTO_FALANTE_API=https://sua-plataforma.com      # Linux/Mac: export PONTO_FALANTE_API=...
python src/demo.py --fonte 0 --ponto 260015039        # 0 = webcam; também aceita arquivo de vídeo ou URL RTSP
```

| Parâmetro do `demo.py` | Para quê |
|---|---|
| `--fonte` | `0` (webcam), caminho de vídeo, URL da câmera ou pasta de imagens |
| `--ponto` | código do ponto na plataforma (vai no GET e no POST) |
| `--api` | URL da API (sobrepõe `PONTO_FALANTE_API`; padrão `http://localhost:8000`) |
| `--sem-api` + `--linhas` | roda sem API, com as linhas informadas à mão |
| `--gpu` | usa a GPU no OCR |
| `--saida arquivo.mp4` | grava o vídeo anotado (já anonimizado) |
| `--mostrar` | abre uma janela com o vídeo (precisa do `opencv-python` com interface gráfica) |

### Usando como biblioteca (dentro do código da plataforma)
```python
import sys, time, cv2
sys.path.insert(0, "src")
from detector import DetectorOnibus
from anunciador import Anunciador
from cliente_api import ClienteAPI

PONTO = "260015039"
detector = DetectorOnibus("modelos/best.pt", conf=0.35, gpu=False)
anunciador = Anunciador()                         # votação entre quadros
api = ClienteAPI("https://sua-plataforma.com")

cap = cv2.VideoCapture(0)
while True:
    ok, frame = cap.read()
    if not ok:
        break
    linhas = api.linhas_do_ponto(PONTO)           # GET (com cache)
    resultado = detector.detectar(frame, linhas)  # YOLO + OCR
    anuncio = anunciador.processar(resultado, time.time())
    if anuncio:                                   # só quando há certeza suficiente
        print(anuncio.texto)                      # "Ônibus da linha 8000-10 chegando."
        api.enviar_deteccao(PONTO, anuncio.linha, anuncio.confianca)   # POST
```

## 5. Comportamentos importantes

- **Só anuncia o que tem certeza.** O ônibus precisa aparecer em vários quadros e a mesma linha precisa ser
  lida pelo menos 2 vezes. Sem isso, o anúncio sai com `linha_lida: null`.
- **Não repete.** A mesma linha não é anunciada de novo em menos de 20 s.
- **API fora do ar não trava a câmera.** O POST que falhar vai para `fila_deteccoes.jsonl` e é reenviado
  depois. Se o GET falhar, a visão usa a última lista válida.
- **Privacidade (LGPD).** Tudo que é exibido ou gravado tem rostos borrados (modelo YuNet em
  `modelos/face_detection_yunet_2023mar.onnx`) e a faixa da placa do ônibus borrada.
- **Log** em `logs/visao.log`.

## 6. Desempenho e limitações

- Detector (YOLO11n, `modelos/best.pt`): mAP50 de 0,866 no teste e 7,8 ms por imagem na GPU.
- Leitura da linha em um único quadro: 44% de acerto nos letreiros que mostram o código, **0 linhas erradas** e
  0 anúncios falsos em letreiros que mostram só o destino. Com vários quadros (câmera real), a chance de leitura
  aumenta.
- Os letreiros de SP alternam entre código e destino: em parte dos quadros não há código para ler, e isso é
  esperado.
- Desempenho completo (detecção + OCR em 3 versões): cerca de 4 quadros/s na GPU; na CPU é mais lento. Para uma
  câmera em tempo real, processar 2 a 4 quadros por segundo já é suficiente.
- Treinado só com fotos de dia de ônibus de São Paulo (Wikimedia Commons); noite e chuva não foram testados.

## 7. O que tem no pacote

| Pasta/arquivo | Conteúdo |
|---|---|
| `src/` | código da visão (`detector`, `leitor_letreiro`, `anunciador`, `cliente_api`, `privacidade`, `demo`, `api_fake`) |
| `modelos/best.pt` | pesos do detector treinado (ônibus + letreiro) |
| `modelos/face_detection_yunet_2023mar.onnx` | detector de rostos para anonimização |
| `amostras/imagens/demo/` | 6 fotos para teste (Wikimedia Commons; créditos em `docs/creditos_imagens.csv`) |
| `tests/` | testes automatizados (`pytest -q`) |
| `ferramentas/`, `notebooks/`, `relatorio/` | coleta, rotulagem, treino, avaliação e gerador do relatório |
| `resultados/` | métricas, gráficos, vídeo da demo e relatório PDF |
| `README.md`, `docs/` | documentação completa, dataset e licenças |

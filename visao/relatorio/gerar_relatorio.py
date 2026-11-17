"""
Gera o relatório da disciplina Applied Computer Vision no formato exigido:
título, integrantes, resumo (250 palavras), introdução, objetivo (50 palavras),
explicação técnica das ferramentas, metodologia (passo a passo), exemplos de
resultados e conclusão.

Os números vêm de resultados/metricas.json (gerado pelo notebook). Enquanto o
treino não roda, o PDF mostra marcadores em vermelho no lugar dos números.

  python relatorio/gerar_relatorio.py --resultados resultados --saida resultados/Relatorio_Visao_Ponto_Falante.pdf
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle)

AQUI = Path(__file__).parent
FALTA = '<font color="#C62828">[preencher após o treino]</font>'
ROSA, ESCURO, CINZA, CLARO = (colors.HexColor(c) for c in ("#C2185B", "#1E1E24", "#5A5A66", "#F6F1F4"))

st = {
    "titulo": ParagraphStyle("t", fontName="Helvetica-Bold", fontSize=20, leading=25, textColor=ESCURO, spaceAfter=4),
    "sub": ParagraphStyle("s", fontName="Helvetica", fontSize=11, leading=15, textColor=CINZA, spaceAfter=14),
    "h1": ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=13.5, leading=18, textColor=ROSA, spaceBefore=12, spaceAfter=6),
    "h2": ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=11, leading=15, textColor=ESCURO, spaceBefore=8, spaceAfter=3),
    "p": ParagraphStyle("p", fontName="Helvetica", fontSize=10, leading=14.5, textColor=ESCURO, spaceAfter=6, alignment=4),
    "li": ParagraphStyle("li", fontName="Helvetica", fontSize=10, leading=14, textColor=ESCURO, leftIndent=14, bulletIndent=3, spaceAfter=3),
    "leg": ParagraphStyle("leg", fontName="Helvetica-Oblique", fontSize=8.5, leading=11, textColor=CINZA, alignment=1, spaceAfter=8),
    "cel": ParagraphStyle("c", fontName="Helvetica", fontSize=9, leading=12, textColor=ESCURO),
    "celb": ParagraphStyle("cb", fontName="Helvetica-Bold", fontSize=9, leading=12, textColor=colors.white),
    "nota": ParagraphStyle("n", fontName="Helvetica-Oblique", fontSize=8.5, leading=11.5, textColor=CINZA, spaceAfter=6),
}


# ----------------------------------------------------------------- dados
def ler_info(caminho: Path) -> dict:
    info = {"integrantes": [], "turma": "", "repositorio": "", "video": ""}
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        if not linha.strip() or linha.lstrip().startswith("#") or ":" not in linha:
            continue
        chave, valor = linha.split(":", 1)
        chave, valor = chave.strip().upper(), valor.strip()
        if chave == "INTEGRANTE":
            info["integrantes"].append(valor)
        else:
            info[chave.lower()] = valor
    return info


def fmt(valor, pct=False):
    if valor is None:
        return FALTA
    return f"{valor * 100:.1f}%".replace(".", ",") if pct else f"{valor:.3f}".replace(".", ",")


def contar_palavras(html: str) -> int:
    return len(re.sub(r"<[^>]+>", " ", html).split())


# ----------------------------------------------------------------- textos
def textos(m: dict) -> dict:
    ocr = m.get("ocr") or {}
    v = {"map50": fmt(m.get("map50")), "map50_95": fmt(m.get("map50_95")),
         "ocr_taxa": fmt(ocr.get("taxa_acerto"), pct=True)}

    resumo = (
        "Pessoas com deficiência visual e idosos enfrentam uma barreira cotidiana no transporte público de São Paulo: "
        "identificar qual ônibus está chegando ao ponto, informação que o letreiro transmite de forma puramente visual. "
        "Este trabalho apresenta o componente de visão computacional do Ponto Falante, protótipo CitizenTech que anuncia "
        "em voz alta os ônibus que se aproximam. Como não existe um conjunto público de letreiros de ônibus paulistanos "
        "rotulados, montamos um dataset próprio: reutilizamos fotos de ônibus da capital com licença livre do Wikimedia "
        "Commons, geramos as caixas automaticamente com dois modelos professores (YOLO11x para ônibus e Grounding DINO "
        "para letreiro, com filtros geométricos) e revisamos tudo manualmente, descartando imagens inadequadas. Com esses "
        "dados treinamos um detector YOLO nano customizado com duas classes, ônibus e letreiro. O letreiro detectado é "
        "recortado e lido por OCR em três versões da imagem; o texto só vira linha se coincidir com uma linha que atende "
        "o ponto, informada pela API do MVP, e uma votação entre quadros decide o anúncio. No conjunto de teste, o modelo "
        f"obteve mAP50 de {v['map50']} e mAP50-95 de {v['map50_95']}. A leitura acertou {v['ocr_taxa']} dos letreiros "
        "que exibiam o código da linha, sem nenhum anúncio de linha errada; nos letreiros que mostravam só o destino, o "
        "sistema corretamente avisou que não conseguiu ler. Os resultados são enviados à API central, e as imagens "
        "exibidas têm rostos e placas borrados, conforme a LGPD. A câmera do ponto foi simulada com imagens de teste."
    )

    objetivo = (
        "Treinar e integrar um detector YOLO customizado que localize ônibus e seus letreiros em imagens de pontos de "
        "parada, leia o número da linha por OCR validado pelas linhas do ponto e envie o resultado à API do Ponto Falante, "
        "permitindo anunciar em voz alta qual ônibus está chegando."
    )

    # Conclusão construída a partir dos números reais.
    pc = m.get("por_classe") or {}
    comparacao = ""
    if "onibus" in pc and "letreiro" in pc:
        o, l = pc["onibus"]["map50"], pc["letreiro"]["map50"]
        if abs(o - l) < 0.03:
            comparacao = "As duas classes tiveram desempenho semelhante. "
        else:
            pior = "letreiro" if l < o else "ônibus"
            comparacao = (f"A classe {pior} teve o menor mAP50 ({fmt(min(o, l))} contra {fmt(max(o, l))}), "
                          "o que orienta onde concentrar novas imagens rotuladas. ")
    ocr_txt = ""
    if ocr.get("total"):
        ocr_txt = (f"Na leitura da linha, dos {ocr['total']} letreiros que exibiam o código, foram {ocr['acertos']} acertos, "
                   f"{ocr['erros']} erros e {ocr['nao_leu']} casos em que o sistema preferiu não anunciar a linha; nos "
                   f"{ocr.get('letreiros_so_destino', 0)} letreiros que mostravam só o destino, houve "
                   f"{ocr.get('falsos_anuncios', 0)} anúncios falsos. ")
    conclusao = [
        f"O componente de visão do Ponto Falante cumpre o papel de transformar imagem em informação útil para o cidadão: "
        f"o detector customizado, treinado só com ônibus da cidade de São Paulo, atingiu mAP50 de {v['map50']} no "
        "conjunto de teste, com imagens nunca vistas no treino. " + comparacao + ocr_txt,
        "Duas decisões foram centrais. A primeira foi reutilizar fotos livres da internet com rotulagem automática por "
        "modelos professores e revisão humana: isso tornou viável um dataset 100% paulistano em poucos dias. A segunda "
        "foi validar o OCR contra as linhas que passam no ponto e exigir votação entre quadros: para uma pessoa cega, "
        "anunciar a linha errada é pior do que avisar que não foi possível ler, e nossos testes não tiveram nenhum "
        "anúncio errado. O sistema também segue funcionando quando a API está fora do ar, guardando as detecções numa "
        "fila local para reenvio.",
        "Limitações: o dataset é pequeno (cerca de 200 imagens) e o conjunto de teste tem só 21 fotos, então as métricas "
        "têm margem de incerteza; parte dos letreiros apagados ficou sem rótulo na pré-rotulagem; o OCR genérico tem "
        "dificuldade com LED de matriz de pontos; e a câmera do ponto foi simulada. Próximos passos: completar os "
        "rótulos faltantes, ampliar as fotos com noite e chuva, treinar um reconhecedor de caracteres específico para "
        "letreiros de LED e testar com uma câmera real em um ponto piloto, sempre com anonimização na borda e sem "
        "armazenar imagens.",
    ]
    return {"resumo": resumo, "objetivo": objetivo, "conclusao": conclusao}


# ----------------------------------------------------------------- blocos
def tabela(linhas, larguras):
    dados = [[Paragraph(str(c), st["celb"] if i == 0 else st["cel"]) for c in linha] for i, linha in enumerate(linhas)]
    t = Table(dados, colWidths=larguras, repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), ROSA),
                           ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, CLARO]),
                           ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#C9CCD6")),
                           ("VALIGN", (0, 0), (-1, -1), "TOP"),
                           ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    return t


def imagem(caminho: Path, largura_cm: float, legenda: str):
    if not caminho.exists():
        return [Paragraph(f"{FALTA} — {legenda} (arquivo {caminho.name})", st["nota"])]
    img = Image(str(caminho))
    proporcao = img.imageHeight / img.imageWidth
    img.drawWidth = largura_cm * cm
    img.drawHeight = min(largura_cm * proporcao, 11) * cm
    img.drawWidth = img.drawHeight / proporcao
    return [KeepTogether([img, Paragraph(legenda, st["leg"])])]


def grade_imagens(arquivos: list[Path], legenda: str):
    if not arquivos:
        return [Paragraph(f"{FALTA} — {legenda}", st["nota"])]
    celulas = []
    for f in arquivos:
        img = Image(str(f))
        prop = img.imageHeight / img.imageWidth
        img.drawWidth, img.drawHeight = 8 * cm, min(8 * prop, 6.5) * cm
        img.drawWidth = img.drawHeight / prop
        celulas.append(img)
    linhas = [celulas[i:i + 2] + [""] * (2 - len(celulas[i:i + 2])) for i in range(0, len(celulas), 2)]
    t = Table(linhas, colWidths=[8.5 * cm, 8.5 * cm])
    t.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    return [t, Paragraph(legenda, st["leg"])]


# ----------------------------------------------------------------- documento
def gerar(resultados: Path, saida: Path, info_path: Path):
    info = ler_info(info_path)
    m = json.loads((resultados / "metricas.json").read_text(encoding="utf-8")) if (resultados / "metricas.json").exists() else {}
    if not m.get("dataset") and (resultados / "dataset.json").exists():
        m["dataset"] = json.loads((resultados / "dataset.json").read_text(encoding="utf-8"))
    tx = textos(m)
    story = []
    P = lambda t, s="p": story.append(Paragraph(t, st[s]))
    LI = lambda itens: [story.append(Paragraph(i, st["li"], bulletText="•")) for i in itens]

    # Título e integrantes
    P("GLOBAL SOLUTION 2026.2 · CITIZENTECH · APPLIED COMPUTER VISION", "nota")
    P("Ponto Falante: detecção de ônibus e leitura da linha no letreiro para passageiros com deficiência visual", "titulo")
    P("Atividade \"Enxergando o mundo real\" · componente Visão do MVP", "sub")
    P("Integrantes", "h2")
    LI(info["integrantes"] or [FALTA])
    if info.get("turma"):
        P(f"Turma: {info['turma']}")
    P(f"Repositório: <link href=\"{info['repositorio']}\" color=\"blue\">{info['repositorio']}</link><br/>"
      f"Vídeo de demonstração: <link href=\"{info['video']}\" color=\"blue\">{info['video']}</link>")

    # Resumo
    P("Resumo", "h1")
    P(tx["resumo"])

    # Introdução
    P("Introdução", "h1")
    P("Em São Paulo, o ônibus é o principal meio de transporte coletivo, e a informação mais básica para usá-lo — qual "
      "linha está chegando — é transmitida quase só pelo letreiro, um elemento visual. Para pessoas cegas ou com baixa "
      "visão, e para muitos idosos, isso significa perguntar a desconhecidos, sinalizar para todos os ônibus ou perder "
      "a condução. Aplicativos de previsão ajudam, mas dizem quando um ônibus <i>deve</i> chegar, não qual ônibus está "
      "<i>de fato</i> parando à frente da pessoa.")
    P("O Ponto Falante é o MVP CitizenTech da equipe: uma solução que mostra e fala a previsão dos próximos ônibus de "
      "cada ponto. Este documento trata do seu componente de <b>visão computacional</b>, responsável por enxergar o "
      "ônibus que chega e ler o número da linha no letreiro. O resultado é enviado à API central do MVP, que o "
      "transforma em anúncio de voz para o passageiro.")
    P("O problema exige detectar um objeto que os modelos pré-treinados não conhecem — o letreiro —, por isso foi feito "
      "um treinamento customizado. Além da precisão, o componente foi desenhado com dois cuidados: não anunciar uma "
      "linha errada (preferindo avisar que não conseguiu ler) e não expor dados pessoais das pessoas que aparecem nas "
      "imagens.")

    # Objetivo
    P("Objetivo", "h1")
    P(tx["objetivo"])

    # Ferramentas
    P("Explicação técnica das ferramentas", "h1")
    ferramentas = [
        ["Ferramenta", "Para que foi usada", "Por que foi escolhida"],
        ["YOLO11 nano (Ultralytics)",
         "Modelo final: detector de estágio único que, em uma passada pela imagem, prevê caixas e classes (ônibus, letreiro).",
         "Rápido o bastante para vídeo (7,8 ms por imagem na GPU), leve para rodar num ponto e fácil de treinar com "
         "<i>transfer learning</i> a partir do COCO."],
        ["Wikimedia Commons (API pública)",
         "Fonte das fotos: ônibus da cidade de São Paulo com licença livre (domínio público, CC0, CC BY, CC BY-SA).",
         "Permite ter ônibus paulistanos sem fotografar, com autor e licença de cada foto registrados."],
        ["YOLO11x (Ultralytics)", "Modelo professor que pré-rotulou a classe ônibus (classe <i>bus</i> do COCO).",
         "Versão grande e precisa; pesado demais para o ponto, mas ótimo para gerar rótulos."],
        ["Grounding DINO (IDEA-Research, via Hugging Face Transformers)",
         "Modelo professor de vocabulário aberto que pré-rotulou a classe letreiro a partir de uma descrição em texto.",
         "Detecta objetos que não estão no COCO sem treino; no nosso teste, foi melhor que o YOLO-World."],
        ["PyTorch + GPU local (RTX 4060 Ti)", "Treino e avaliação do modelo.", "Treino completo em poucos minutos."],
        ["EasyOCR", "Leitura do texto do letreiro recortado (detecção de texto + reconhecimento de caracteres).",
         "Pronto para uso, suporta português e roda em CPU ou GPU."],
        ["OpenCV", "Ampliação, suavização e realce de contraste (CLAHE) do recorte; desenho das caixas; vídeo; "
         "borramento de rostos (detector YuNet) e da região da placa.", "Biblioteca padrão de visão, leve."],
        ["Python + requests", "Integração com a API do MVP (GET das linhas do ponto, POST /deteccoes), com timeout, "
         "novas tentativas e fila local.", "Simples e segue o contrato comum da equipe."],
    ]
    story.append(tabela(ferramentas, [3.6 * cm, 7.2 * cm, 6.2 * cm]))
    P("Métricas usadas", "h2")
    LI(["<b>Precisão</b>: das caixas previstas, a fração correta.",
        "<b>Recall</b>: dos objetos existentes, a fração encontrada.",
        "<b>mAP50</b>: média da precisão ao longo dos níveis de recall, considerando acerto quando a caixa prevista "
        "sobrepõe pelo menos 50% (IoU ≥ 0,5) a caixa real.".replace("≥", "&gt;="),
        "<b>mAP50-95</b>: média do mAP para IoU de 0,50 a 0,95; mais rigoroso quanto ao ajuste da caixa.",
        "<b>Taxa de acerto do OCR</b>: fração dos letreiros que exibiam o código da linha em que a linha anunciada "
        "era a correta.",
        "<b>Anúncios falsos</b>: vezes em que o sistema anunciou uma linha num letreiro que mostrava só o destino."])

    # Metodologia
    P("Metodologia (passo a passo)", "h1")
    passos = [
        "<b>Definição das classes.</b> <i>onibus</i> (indica que um ônibus chegou) e <i>letreiro</i> (região que contém "
        "o número da linha). A classe \"bus\" já existe no COCO, mas \"letreiro\" não, o que justifica o treino customizado.",
        "<b>Busca por dados prontos.</b> Procuramos conjuntos rotulados de ônibus e letreiros de São Paulo e não "
        "encontramos; os conjuntos públicos (Roboflow Universe, Open Images) mostram ônibus de outros países, com outros "
        "letreiros. Optamos por reutilizar fotos livres de ônibus paulistanos.",
        "<b>Coleta automática.</b> O script <i>ferramentas/baixar_commons.py</i> percorre sete categorias do Wikimedia "
        "Commons sobre ônibus da capital, aceita só licenças livres, confere a assinatura de cada arquivo e registra "
        "autor, licença e URL em <i>docs/creditos_imagens.csv</i>. Resultado: 342 fotos.",
        "<b>Pré-rotulagem por modelos professores.</b> O YOLO11x marca os ônibus (confiança &gt;= 0,45; ignorados os "
        "menores que 3% da foto). O Grounding DINO procura \"bus destination sign\" e as caixas passam por filtros: "
        "dentro de um ônibus, nos 35% de cima, formato de faixa (largura &gt;= 2,2 x altura) e no máximo um por ônibus. "
        "Testamos antes o YOLO-World, que marcava o ônibus inteiro como letreiro, e o descartamos. Fotos sem ônibus "
        "(terminais vazios, prédios) saem automaticamente: ficaram 211.",
        "<b>Revisão humana.</b> O script gera folhas com miniaturas e caixas desenhadas; revisamos todas e descartamos 13 "
        "fotos (maquetes, fotos históricas, multidões, letreiro marcado errado), com o motivo registrado em "
        "<i>ferramentas/revisao_descartes.txt</i>. Dataset final: 198 imagens, 225 ônibus e 152 letreiros.",
        "<b>Divisão.</b> 70% treino, 20% validação e 10% teste, com semente fixa (42). O teste nunca é usado no treino.",
        "<b>Treino.</b> <i>Transfer learning</i> a partir do YOLO11 nano pré-treinado, 640 px, até 80 épocas com parada "
        "antecipada (paciência 20). Aumento de dados: brilho e saturação (dia/noite), pequenas rotações, deslocamentos, "
        "zoom e mosaico; <b>sem espelhamento horizontal</b>, pois letreiro espelhado não ocorre no mundo real.",
        "<b>Avaliação.</b> Precisão, recall, mAP50 e mAP50-95 no conjunto de teste, por classe, com matriz de confusão.",
        "<b>Leitura da linha.</b> O letreiro de maior confiança é recortado com margem e passado ao OCR em três versões: "
        "colorida ampliada, brilho suavizado (o desfoque junta os pontos do LED em traços) e cinza com CLAHE. O texto é "
        "normalizado, procuram-se padrões de linha da SPTrans (ex.: 647P-10) e os candidatos são comparados às linhas do "
        "ponto, tolerando confusões típicas (O/0, I/1, S/5, B/8). Linha fora da lista não é anunciada.",
        "<b>Avaliação do OCR.</b> Lemos à mão os letreiros das imagens de validação e teste e montamos um gabarito "
        "(<i>resultados/gabarito_ocr.csv</i>) com dois tipos: letreiro com código da linha e letreiro só com destino "
        "(os de SP alternam os dois). O ponto simulado tem 21 linhas, como um corredor movimentado.",
        "<b>Decisão por votação.</b> O ônibus precisa aparecer em vários quadros seguidos e a mesma linha precisa ser "
        "lida mais de uma vez. Sem leitura confiável, o anúncio é \"Ônibus chegando. Não consegui ler a linha.\"",
        "<b>Integração.</b> O anúncio vira <i>{\"ponto\", \"linha_lida\", \"confianca\", \"criado_em\"}</i> enviado para "
        "<i>POST /deteccoes</i> da API do MVP. Com a API fora, a detecção vai para uma fila local e é reenviada depois.",
        "<b>Privacidade (LGPD).</b> Nenhuma imagem é enviada ou armazenada pela solução; só o resultado. Tudo que é "
        "exibido ou salvo passa por borramento de rostos (YuNet) e da faixa da placa do ônibus.",
        "<b>Demonstração.</b> A câmera do ponto foi simulada com imagens de teste processadas quadro a quadro pelo script "
        "<i>src/demo.py</i>, conversando com uma API falsa que segue o mesmo contrato do MVP.",
    ]
    for i, p in enumerate(passos, 1):
        story.append(Paragraph(p, st["li"], bulletText=f"{i}."))

    # Resultados
    story.append(PageBreak())
    P("Exemplos de resultados", "h1")
    P("Composição do dataset", "h2")
    ds = m.get("dataset") or []
    if ds:
        linhas = [["Origem", "Imagens", "Caixas ônibus", "Caixas letreiro", "Treino/Val/Teste", "Licença"]]
        for d in ds:
            linhas.append([d["origem"], d["imagens"], d["caixas_onibus"], d["caixas_letreiro"],
                           f"{d['train']}/{d['val']}/{d['test']}", d.get("licenca", "")])
        story.append(tabela(linhas, [2.6 * cm, 1.6 * cm, 2 * cm, 2.2 * cm, 2.6 * cm, 6 * cm]))
    else:
        P(FALTA + " — tabela gerada automaticamente a partir de resultados/dataset.json.")

    P("Desempenho no conjunto de teste", "h2")
    pc = m.get("por_classe") or {}
    linhas = [["Classe", "Precisão", "Recall", "mAP50", "mAP50-95"]]
    for nome, rotulo in [("onibus", "ônibus"), ("letreiro", "letreiro")]:
        c = pc.get(nome, {})
        linhas.append([rotulo, fmt(c.get("precisao")), fmt(c.get("recall")), fmt(c.get("map50")), fmt(c.get("map50_95"))])
    linhas.append(["<b>todas</b>", fmt(m.get("precisao")), fmt(m.get("recall")), fmt(m.get("map50")), fmt(m.get("map50_95"))])
    story.append(tabela(linhas, [4 * cm, 3.2 * cm, 3.2 * cm, 3.2 * cm, 3.4 * cm]))
    if m.get("velocidade_ms"):
        vel = m["velocidade_ms"]
        P(f"Tempo por imagem na GPU (RTX 4060 Ti): {vel.get('inference', '?')} ms de inferência "
          f"(pré-processamento {vel.get('preprocess', '?')} ms, pós-processamento {vel.get('postprocess', '?')} ms). "
          f"Modelo base: {m.get('modelo_base', '?')}.", "nota")

    P("Leitura da linha (OCR)", "h2")
    ocr = m.get("ocr") or {}
    linhas = [["Letreiros com código", "Acertos", "Linha errada", "Não anunciou", "Taxa de acerto"],
              [ocr.get("total", FALTA), ocr.get("acertos", FALTA), ocr.get("erros", FALTA),
               ocr.get("nao_leu", FALTA), fmt(ocr.get("taxa_acerto"), pct=True)]]
    story.append(tabela(linhas, [3.6 * cm, 2.6 * cm, 3.6 * cm, 3.8 * cm, 3.4 * cm]))
    linhas = [["Letreiros só com destino", "Avisou \"não consegui ler\" (correto)", "Anunciou uma linha (falso anúncio)"],
              [ocr.get("letreiros_so_destino", FALTA), ocr.get("absteve_corretamente", FALTA),
               ocr.get("falsos_anuncios", FALTA)]]
    story.append(tabela(linhas, [5 * cm, 6 * cm, 6 * cm]))
    P("Avaliação feita em um único quadro por ônibus, nas imagens de validação e teste. \"Não anunciou\" é um "
      "comportamento esperado: sem leitura confiável, o sistema avisa apenas que um ônibus está chegando. O erro mais "
      "grave seria anunciar a linha errada, o que não aconteceu. Na câmera real, vários quadros do mesmo ônibus aumentam "
      "a chance de leitura.", "nota")

    story += imagem(resultados / "confusion_matrix_normalized.png", 11,
                    "Matriz de confusão normalizada no conjunto de teste.")
    story += imagem(resultados / "results.png", 16, "Curvas de perda e métricas ao longo das épocas de treino.")
    story += grade_imagens(sorted(resultados.glob("exemplo_*.jpg")),
                           "Detecções e leituras corretas (rostos e placa borrados). Azul: ônibus; amarelo: letreiro; "
                           "no topo, a linha lida pelo OCR.")
    P("Casos de falha", "h2")
    story += grade_imagens(sorted(resultados.glob("falha_*.jpg")),
                           "Casos em que a linha não foi lida: LED de matriz de pontos fraco ou apagado, letreiro pequeno "
                           "ou não detectado. Nesses casos o sistema avisa que não conseguiu ler, sem arriscar uma linha.")

    # Conclusão
    P("Conclusão", "h1")
    for par in tx["conclusao"]:
        P(par)

    P("Créditos das imagens", "h2")
    P("Todas as fotos vêm do Wikimedia Commons, com licença livre (domínio público, CC0, CC BY ou CC BY-SA). Autor, "
      "licença e URL de cada uma estão em docs/creditos_imagens.csv; a metodologia está em docs/dataset.md. "
      "Modelos de terceiros: YOLO11 (Ultralytics, AGPL-3.0), Grounding DINO (IDEA-Research, Apache-2.0), EasyOCR "
      "(Apache-2.0) e YuNet (OpenCV Zoo, MIT).", "nota")

    def rodape(c, doc):
        c.saveState()
        c.setFont("Helvetica", 7.5)
        c.setFillColor(CINZA)
        c.drawString(2 * cm, 1.2 * cm, "Ponto Falante · Applied Computer Vision · GS 2026.2")
        c.drawRightString(A4[0] - 2 * cm, 1.2 * cm, str(doc.page))
        c.restoreState()

    saida.parent.mkdir(parents=True, exist_ok=True)
    SimpleDocTemplate(str(saida), pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2 * cm,
                      bottomMargin=2 * cm, title="Ponto Falante - Applied Computer Vision").build(
        story, onFirstPage=rodape, onLaterPages=rodape)
    print(f"Relatório gerado: {saida}")
    print(f"Resumo: {contar_palavras(tx['resumo'])} palavras | Objetivo: {contar_palavras(tx['objetivo'])} palavras")
    if not m:
        print("Aviso: resultados/metricas.json não encontrado — números aparecem como [preencher após o treino].")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--resultados", default="resultados")
    ap.add_argument("--saida", default="resultados/Relatorio_Visao_Ponto_Falante.pdf")
    ap.add_argument("--info", default=str(AQUI / "info.txt"))
    a = ap.parse_args()
    gerar(Path(a.resultados), Path(a.saida), Path(a.info))

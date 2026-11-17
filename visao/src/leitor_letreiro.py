"""
Leitura do número da linha no letreiro do ônibus.

O OCR erra bastante em letreiro (luz, ângulo, LED piscando). Por isso este módulo
NÃO confia no texto bruto: ele procura padrões de linha da SPTrans (ex.: 8000-10,
875A-10, N101-11) e, quando possível, compara com as linhas que de fato passam no
ponto (vindas da API do MVP). Só devolve uma linha que exista nessa lista.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher

# Código da linha: 3 ou 4 caracteres + sufixo de 2 dígitos (o sufixo é opcional no letreiro).
PADRAO_LINHA = re.compile(r"\b([A-Z0-9]{3,4})(?:\s*-\s*|\s+)?(\d{2})?\b")

# Confusões comuns do OCR. Usadas só para COMPARAR, nunca para alterar o texto final.
CONFUSOES = str.maketrans({"O": "0", "Q": "0", "D": "0", "I": "1", "L": "1",
                           "S": "5", "B": "8", "Z": "2", "G": "6"})


@dataclass
class LeituraLinha:
    linha: str | None        # linha reconhecida (ex.: "8000-10") ou None
    confianca: float         # 0 a 1
    texto_bruto: str         # o que o OCR leu, para log e relatório
    codigo_lido: str | None = None   # o código como apareceu no letreiro (ex.: "875A", sem o sufixo)
    validada: bool = True            # False = lida fora da lista de linhas do ponto (confiança já reduzida)

    def texto_confirmado(self) -> str | None:
        """O que o letreiro de fato mostrou, sem completar nada: se o letreiro só exibia "875A",
        devolve "875A" mesmo que a linha casada seja "875A-10" (o sufixo não foi visto)."""
        if self.linha is None:
            return None
        if self.codigo_lido and "-" not in self.codigo_lido:
            return self.linha.split("-")[0]
        return self.linha


def normalizar_texto(texto: str) -> str:
    """Maiúsculas, sem acento, só letras, números, hífen e espaço."""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Z0-9\- ]", " ", sem_acento.upper()).strip()


def forma_canonica(codigo: str) -> str:
    """Versão do código usada para comparação tolerante a erros de OCR."""
    return codigo.replace("-", "").replace(" ", "").translate(CONFUSOES)


def extrair_candidatos(texto: str) -> list[str]:
    """Extrai possíveis códigos de linha de um texto de OCR.

    Exige pelo menos um dígito no código, para não confundir com palavras
    do destino (ex.: "LAPA", "TERM").
    """
    candidatos = []
    for codigo, sufixo in PADRAO_LINHA.findall(normalizar_texto(texto)):
        if not any(c.isdigit() for c in codigo):
            continue
        candidatos.append(f"{codigo}-{sufixo}" if sufixo else codigo)
    return candidatos


def similaridade(candidato: str, linha: str) -> float:
    """Similaridade entre 0 e 1. Se o letreiro só mostra o código (sem sufixo),
    compara apenas com a parte antes do hífen."""
    a = forma_canonica(candidato)
    if "-" not in candidato:
        linha = linha.split("-")[0]
    b = forma_canonica(linha)
    if a == b:
        return 1.0
    return SequenceMatcher(None, a, b).ratio()


def casar_com_linhas(candidatos: list[str], linhas_permitidas: list[str],
                     limiar: float = 0.75, rejeitar_ambiguas: bool = False) -> tuple[str | None, float]:
    """Escolhe a linha permitida mais parecida com algum candidato.

    rejeitar_ambiguas: se duas linhas de NÚMERO diferente ficam quase empatadas para o mesmo candidato
    (ex.: "8750-10" parecido com 875A-10 e 875C-10), não escolhe nenhuma. Usado pela conferência pelo
    celular, em que afirmar a linha errada para quem não enxerga é o pior erro possível.
    """
    melhor, melhor_score = None, 0.0
    for cand in candidatos:
        # ordenação estável: em empate, vale a ordem da lista (como na versão original)
        scores = sorted(((similaridade(cand, linha), linha) for linha in linhas_permitidas), key=lambda t: -t[0])
        if not scores:
            continue
        s, linha = scores[0]
        if rejeitar_ambiguas and s < 1.0:
            numero = linha.split("-")[0]
            if any(outra.split("-")[0] != numero and s - so < 0.05 for so, outra in scores[1:]):
                continue
        if s > melhor_score:
            melhor, melhor_score = linha, s
    if melhor_score < limiar:
        return None, melhor_score
    return melhor, melhor_score


def ler_linha(resultados_ocr: list[tuple[str, float]],
              linhas_permitidas: list[str] | None = None,
              limiar: float = 0.75, rejeitar_ambiguas: bool = False) -> LeituraLinha:
    """Converte o resultado do OCR em uma linha de ônibus.

    resultados_ocr: lista de (texto, confiança) devolvida pelo OCR.
    linhas_permitidas: linhas que passam no ponto (GET /pontos/{codigo}/previsoes).
      - Com a lista: só aceita linha da lista (mais seguro).
      - Sem a lista (API fora): aceita o padrão de linha, mas com confiança reduzida.
    """
    texto_bruto = " | ".join(t for t, _ in resultados_ocr)
    melhor = LeituraLinha(None, 0.0, texto_bruto)

    for texto, conf_ocr in resultados_ocr:
        candidatos = extrair_candidatos(texto)
        if not candidatos:
            continue
        if linhas_permitidas:
            linha, score, lido = None, 0.0, None
            for cand in candidatos:   # guarda qual candidato casou, para saber se o sufixo foi lido
                l, s = casar_com_linhas([cand], linhas_permitidas, limiar, rejeitar_ambiguas)
                if l is not None and s > score:
                    linha, score, lido = l, s, cand
            if linha is None:
                continue
            conf = conf_ocr * score
        else:
            # Sem lista de referência: penaliza a confiança (não há como validar).
            linha, conf, lido = candidatos[0], conf_ocr * 0.6, candidatos[0]
        if conf > melhor.confianca:
            melhor = LeituraLinha(linha, round(conf, 3), texto_bruto, lido)
    return melhor

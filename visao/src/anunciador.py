"""
Decide O QUE anunciar e QUANDO, a partir das detecções de vários frames seguidos.

Um único frame engana (reflexo, letreiro piscando). Por isso usamos votação:
o ônibus precisa aparecer em vários frames, e a linha precisa ser lida mais de uma
vez. Se o ônibus está lá mas a linha não foi lida com segurança, o sistema avisa
"não consegui ler a linha" em vez de arriscar uma linha errada — para uma pessoa
cega, anunciar a linha errada é pior do que não anunciar.
"""
from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass, field

from leitor_letreiro import LeituraLinha


@dataclass
class ResultadoFrame:
    onibus: bool                      # há ônibus de frente na imagem?
    conf_onibus: float = 0.0
    leitura: LeituraLinha | None = None
    caixas: list = field(default_factory=list)   # (classe, conf, x1, y1, x2, y2) para desenhar


@dataclass
class Anuncio:
    texto: str              # frase para a tela / voz
    linha: str | None       # None = ônibus sem linha reconhecida
    confianca: float


class Anunciador:
    def __init__(self, janela: int = 8, min_frames_onibus: int = 4,
                 min_votos_linha: int = 2, limiar_leitura: float = 0.45,
                 intervalo_repeticao_s: float = 20.0):
        self.janela = janela
        self.min_frames_onibus = min_frames_onibus
        self.min_votos_linha = min_votos_linha
        self.limiar_leitura = limiar_leitura
        self.intervalo = intervalo_repeticao_s
        self.historico: deque[ResultadoFrame] = deque(maxlen=janela)
        self.ultimo_anuncio: dict[str | None, float] = {}
        self.anunciou_sem_linha = False

    def _ja_anunciado(self, linha: str | None, agora: float) -> bool:
        t = self.ultimo_anuncio.get(linha)
        return t is not None and (agora - t) < self.intervalo

    def processar(self, frame: ResultadoFrame, agora: float) -> Anuncio | None:
        self.historico.append(frame)
        frames_com_onibus = [f for f in self.historico if f.onibus]

        # Ponto vazio por uma janela inteira: zera o estado para o próximo ônibus.
        if not frames_com_onibus:
            self.anunciou_sem_linha = False
            return None
        if len(frames_com_onibus) < self.min_frames_onibus:
            return None

        # Votação das leituras confiáveis.
        leituras = [f.leitura for f in frames_com_onibus
                    if f.leitura and f.leitura.linha and f.leitura.confianca >= self.limiar_leitura]
        if leituras:
            votos = Counter(l.linha for l in leituras)
            linha, n = votos.most_common(1)[0]
            if n >= self.min_votos_linha:
                if self._ja_anunciado(linha, agora):
                    return None
                conf = sum(l.confianca for l in leituras if l.linha == linha) / n
                self.ultimo_anuncio[linha] = agora
                return Anuncio(f"Ônibus da linha {linha} chegando.", linha, round(conf, 3))

        # Ônibus presente na janela toda, sem linha confiável: aviso claro, uma vez.
        if (len(frames_com_onibus) >= self.janela and not self.anunciou_sem_linha
                and not self._ja_anunciado(None, agora)):
            self.anunciou_sem_linha = True
            self.ultimo_anuncio[None] = agora
            conf = sum(f.conf_onibus for f in frames_com_onibus) / len(frames_com_onibus)
            return Anuncio("Ônibus chegando. Não consegui ler a linha.", None, round(conf, 3))
        return None

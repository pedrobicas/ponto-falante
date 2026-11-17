"""Monta o MP4 final a partir das cenas capturadas por captura.js e de uma lista de planos (EDL em JSON).

    python scripts/video/compor.py edl.json <pasta das cenas> <arquivo .mp4 de saída>

Cada plano recorta um trecho real de uma cena (por marcas de tempo), com velocidade, enquadramento animado
(zoom suave por quadros-chave), transição discreta e dois rótulos fixos no rodapé: o capítulo (para sincronizar a
narração) e o selo da natureza dos dados (REAL, ESTIMADO ou SIMULADO). Trechos acelerados ganham o indicador
"espera acelerada". Nenhum conteúdo é gerado: só se cortam, ampliam e encadeiam os quadros gravados.

Saída: H.264 1920x1080, 30 fps, sem trilha de áudio, mais um .timeline.json com os tempos de cada plano.
"""
from __future__ import annotations

import bisect
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1920, 1080
FFMPEG = os.environ.get("FFMPEG") or shutil.which("ffmpeg") or "ffmpeg"  # defina FFMPEG se não estiver no PATH
FONTE = r"C:\Windows\Fonts\seguisb.ttf"
FONTE_N = r"C:\Windows\Fonts\segoeuib.ttf"
if not Path(FONTE).exists():  # fora do Windows: Inter, se instalada
    FONTE = "/usr/share/fonts/opentype/inter/Inter-SemiBold.otf"
    FONTE_N = "/usr/share/fonts/opentype/inter/Inter-Bold.otf"
SELOS = {
    "real": ("DADOS REAIS", "SPTrans · produção", (22, 120, 72)),
    "estimado": ("ESTIMADO", "previsões reais, não chegadas", (24, 92, 160)),
    "simulado": ("SIMULADO", "ambiente local de teste", (176, 104, 0)),
    "oficial": ("DADOS OFICIAIS", "cadastro GTFS da SPTrans", (22, 120, 72)),
    "genai": ("BASE OFICIAL", "RAG com citações · Ollama local", (88, 64, 160)),
    "fora": ("FORA DA ÁREA", "regra do backend · sem GenAI", (70, 74, 84)),
    "codigo": ("REPOSITÓRIO", "arquivos reais do projeto", (70, 74, 84)),
    "avaliacao": ("AVALIAÇÃO", "resultados já registrados", (70, 74, 84)),
    "site": ("SITE PUBLICADO", "ponto real · cadastro GTFS da SPTrans", (22, 120, 72)),
    "modelo": ("MODELO REAL", "YOLO11n + EasyOCR · CPU", (88, 64, 160)),
    "saida": ("SAÍDA DO DEMO.PY", "fotos simulam a câmera · rostos e placas borrados", (88, 64, 160)),
}


def suave(k: float) -> float:
    k = max(0.0, min(1.0, k))
    return k * k * (3 - 2 * k)


class Cena:
    def __init__(self, pasta: Path):
        d = json.loads((pasta / "indice.json").read_text(encoding="utf-8"))
        q = sorted(d["quadros"], key=lambda x: x["t"])
        self.ts = [x["t"] for x in q]
        self.arq = [pasta / "q" / x["a"] for x in q]
        self.marcas = {m["nome"]: m["t"] for m in d["marcas"]}
        self.t0 = self.marcas["inicio"]
        self._cache: tuple[int, Image.Image] | None = None

    def tempo(self, ref) -> float:
        """'marca', 'marca+1.5', 'marca-2' ou segundos desde o início."""
        if isinstance(ref, (int, float)):
            return self.t0 + float(ref)
        for sinal in ("+", "-"):
            if sinal in ref[1:]:
                nome, desl = ref.rsplit(sinal, 1)
                return self.marcas[nome] + (float(desl) if sinal == "+" else -float(desl))
        return self.marcas[ref]

    def quadro(self, t: float) -> tuple[int, Image.Image]:
        i = max(0, bisect.bisect_right(self.ts, t) - 1)
        if not self._cache or self._cache[0] != i:
            self._cache = (i, Image.open(self.arq[i]).convert("RGB"))
        return self._cache


class Imagem:
    """Imagem estática real (ex.: o BPMN), centralizada numa tela 2x para o zoom continuar nítido."""

    def __init__(self, arquivo: Path, fundo: str):
        img = Image.open(arquivo).convert("RGB")
        tela = Image.new("RGB", (W * 2, H * 2), fundo)
        esc = min(W * 2 * 0.94 / img.width, H * 2 * 0.92 / img.height)
        img = img.resize((round(img.width * esc), round(img.height * esc)), Image.LANCZOS)
        tela.paste(img, ((W * 2 - img.width) // 2, (H * 2 - img.height) // 2))
        self.tela = tela

    def quadro(self, _t):
        return 0, self.tela


def caixa(kf: list, t: float) -> tuple[float, float, float]:
    """Enquadramento (centro x, centro y, largura) em coordenadas 1920x1080, interpolado com suavização."""
    if not kf:
        return W / 2, H / 2, W
    if t <= kf[0][0]:
        return tuple(kf[0][1:])
    for a, b in zip(kf, kf[1:]):
        if t <= b[0]:
            k = suave((t - a[0]) / max(1e-6, b[0] - a[0]))
            return tuple(a[i] + (b[i] - a[i]) * k for i in (1, 2, 3))
    return tuple(kf[-1][1:])


def enquadrar(img: Image.Image, cx: float, cy: float, w: float) -> Image.Image:
    esc = img.width / W
    w = min(W, w)
    h = w * H / W
    x0 = min(max(0.0, cx - w / 2), W - w)
    y0 = min(max(0.0, cy - h / 2), H - h)
    box = (x0 * esc, y0 * esc, (x0 + w) * esc, (y0 + h) * esc)
    if box == (0, 0, img.width, img.height) and img.size == (W, H):
        return img
    return img.resize((W, H), Image.LANCZOS, box=box)


class Rotulos:
    def __init__(self):
        self.f = ImageFont.truetype(FONTE, 25)
        self.fb = ImageFont.truetype(FONTE_N, 23)
        self.fp = ImageFont.truetype(FONTE, 21)

    def pilula(self, base: Image.Image, x: int, y: int, partes: list, fundo, alfa: float, direita=False):
        if alfa <= 0.01:
            return
        d0 = ImageDraw.Draw(base)
        larg = sum(d0.textlength(t, font=f) for t, f, _ in partes) + 24 * (len(partes) - 1) + 44
        alt = 50
        if direita:
            x = x - larg
        x, larg = int(round(x)), int(round(larg))
        camada = Image.new("RGBA", (larg, alt), (0, 0, 0, 0))
        d = ImageDraw.Draw(camada)
        d.rounded_rectangle((0, 0, larg - 1, alt - 1), radius=25, fill=fundo + (round(222 * alfa),))
        cx = 22
        for texto, fonte, cor in partes:
            d.text((cx, alt / 2), texto, font=fonte, fill=cor + (round(255 * alfa),), anchor="lm")
            cx += d.textlength(texto, font=fonte) + 24
        base.paste(camada, (x, int(y)), camada)

    def aplicar(self, img: Image.Image, plano: dict, t: float, dur: float) -> Image.Image:
        entra = suave(t / 0.45) if plano.get("_novo_capitulo", True) else 1.0
        sai = 1.0
        if plano.get("capitulo"):
            self.pilula(img, 36, H - 86, [(plano["capitulo"], self.f, (255, 255, 255))], (18, 22, 28), entra * sai)
        partes = []
        if plano.get("selo"):
            nome, desc, cor = SELOS[plano["selo"]]
            partes = [(nome, self.fb, (255, 255, 255)), (desc, self.fp, (235, 240, 245))]
            self.pilula(img, W - 36, H - 86, partes, cor, entra, direita=True)
        if plano.get("vel", 1) >= 2.5 and plano.get("mostrar_vel", True):
            real = plano["_dur"] * plano["vel"]
            texto = f"espera real de {real:.0f} s  ·  acelerada {plano['vel']:g}×"
            self.pilula(img, W - 36, 36, [(texto, self.fp, (255, 255, 255))], (18, 22, 28), 1.0, direita=True)
        return img


def main() -> None:
    edl_arq = Path(sys.argv[1]).resolve()
    edl = json.loads(edl_arq.read_text(encoding="utf-8"))
    raiz = Path(sys.argv[2])
    raiz_repo = Path(__file__).resolve().parents[2]
    fps = edl.get("fps", 30)
    cenas: dict[str, object] = {}
    planos = []
    tempo = 0.0
    anterior_cap = None
    for p in edl["planos"]:
        if "imagem" in p:
            chave = "img:" + p["imagem"]
            cenas.setdefault(chave, Imagem(raiz_repo / p["imagem"], p.get("fundo", "#ffffff")))
            de, dur = 0.0, float(p["dur"])
        else:
            chave = p["cena"]
            if chave not in cenas:
                cenas[chave] = Cena(raiz / chave)
            c = cenas[chave]
            de = c.tempo(p["de"])
            ate = c.tempo(p["ate"])
            dur = (ate - de) / p.get("vel", 1)
            if dur <= 0:
                raise SystemExit(f"plano com duração inválida: {p}")
        trans = p.get("transicao", 0.4) if planos else 0.0
        inicio = tempo - trans
        p = {**p, "_chave": chave, "_de": de, "_dur": dur, "_inicio": inicio, "_trans": trans,
             "_novo_capitulo": p.get("capitulo") != anterior_cap}
        anterior_cap = p.get("capitulo")
        planos.append(p)
        tempo = inicio + dur
    total = tempo + edl.get("cauda", 0.8)
    saida = Path(sys.argv[3])
    saida.parent.mkdir(parents=True, exist_ok=True)
    # Linha do tempo dos planos (base do roteiro de narração): início/fim no vídeo final, capítulo e aceleração.
    linha = [{"inicio": round(max(0.0, q["_inicio"]), 2), "fim": round(q["_inicio"] + q["_dur"], 2),
              "capitulo": q.get("capitulo"), "vel": q.get("vel", 1), "nota": q.get("nota")} for q in planos]
    saida.with_suffix(".linha_do_tempo.json").write_text(
        json.dumps({"total": round(total, 2), "planos": linha}, ensure_ascii=False, indent=1), encoding="utf-8")
    if "--so-linha" in sys.argv[4:]:
        print(f"linha do tempo: {saida.with_suffix('.linha_do_tempo.json')} ({total:.1f} s)")
        return
    proc = subprocess.Popen([FFMPEG, "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(fps),  # nosemgrep -- lista de argumentos sem shell; FFMPEG é o executável escolhido pelo próprio operador
                             "-i", "-", "-an", "-c:v", "libx264", "-preset", "slow", "-crf", "16", "-profile:v", "high",
                             "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(saida)], stdin=subprocess.PIPE)
    rot = Rotulos()
    memo: dict = {}

    def render(p: dict, t: float) -> Image.Image:
        src = cenas[p["_chave"]]
        idx, img = src.quadro(p["_de"] + t * p.get("vel", 1))
        cx, cy, w = caixa(p.get("zoom", []), t)
        chave = (p["_chave"], idx, round(cx, 1), round(cy, 1), round(w, 1))
        if memo.get("k") != chave:
            memo["k"], memo["img"] = chave, enquadrar(img, cx, cy, w)
        return memo["img"].copy()

    n = int(round(total * fps))
    fim_fade = edl.get("fade_final", 0.7)
    for i in range(n):
        T = i / fps
        ativos = [p for p in planos if p["_inicio"] <= T < p["_inicio"] + p["_dur"]] or [planos[-1]]
        p = ativos[-1]
        t = min(T - p["_inicio"], p["_dur"] - 1e-3)
        quadro = rot.aplicar(render(p, t), p, t, p["_dur"])
        if len(ativos) > 1 and p["_trans"] > 0:
            q = ativos[-2]
            k = suave((T - p["_inicio"]) / p["_trans"])
            velho = rot.aplicar(render(q, min(T - q["_inicio"], q["_dur"] - 1e-3)), {**q, "_novo_capitulo": False},
                                T - q["_inicio"], q["_dur"])
            quadro = Image.blend(velho, quadro, k)
        if T > total - fim_fade:
            quadro = Image.blend(Image.new("RGB", (W, H), (0, 0, 0)), quadro, max(0.0, (total - T) / fim_fade))
        if T < 0.4 and edl.get("fade_inicial", True):
            quadro = Image.blend(Image.new("RGB", (W, H), (0, 0, 0)), quadro, T / 0.4)
        proc.stdin.write(quadro.tobytes())
        if i % (fps * 10) == 0:
            print(f"  {T:6.1f}/{total:.1f} s", flush=True)
    proc.stdin.close()
    if proc.wait() != 0:
        raise SystemExit("ffmpeg falhou")
    linha = [{"inicio": round(p["_inicio"], 2), "fim": round(p["_inicio"] + p["_dur"], 2), "capitulo": p.get("capitulo"),
              "selo": p.get("selo"), "vel": p.get("vel", 1), "nota": p.get("nota", "")} for p in planos]
    saida.with_suffix(".timeline.json").write_text(json.dumps({"duracao_s": round(total, 2), "planos": linha}, ensure_ascii=False,
                                                              indent=1), encoding="utf-8")
    print(f"ok: {saida} ({total:.1f} s)")


if __name__ == "__main__":
    main()

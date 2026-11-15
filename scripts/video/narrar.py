"""Junta a narração gravada pelo próprio apresentador aos vídeos silenciosos, sem alterar a imagem.

Uso (na raiz do repositório):
    # uma gravação contínua, começando 0,5 s depois do início do vídeo
    python scripts/video/narrar.py entregaveis/Ponto_Falante_RPA.mp4 --audio minha_voz_rpa.m4a --atraso 0.5

    # uma gravação por fala, cada uma posicionada no tempo do roteiro
    python scripts/video/narrar.py entregaveis/Ponto_Falante_GenAI.mp4 --trechos falas_genai.json

    falas_genai.json: [{"inicio": 0.3, "arquivo": "falas/01.m4a"}, {"inicio": 7.2, "arquivo": "falas/02.m4a"}]

O que o script faz:
  * mede a duração do vídeo e de cada áudio (ffprobe) e recusa áudio que ultrapasse o fim do vídeo;
  * normaliza a voz em duas passagens (EBU R128, alvo -16 LUFS, pico -1,5 dBTP), padrão de vídeo na web;
  * copia o vídeo sem recodificar (a imagem fica idêntica) e grava AAC 48 kHz;
  * nunca sobrescreve o vídeo original: a saída padrão é <nome>_narrado.mp4, e uma saída existente
    é renomeada para .bak antes de ser substituída.

Não gera voz nem texto: só mistura o arquivo de áudio que a pessoa gravou.
Requer ffmpeg e ffprobe (variáveis FFMPEG/FFPROBE ou PATH).
"""
from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

FFMPEG = os.environ.get("FFMPEG") or shutil.which("ffmpeg") or "ffmpeg"
FFPROBE = os.environ.get("FFPROBE") or shutil.which("ffprobe") or str(Path(FFMPEG).with_name("ffprobe.exe"))
ALVO = {"I": -16.0, "TP": -1.5, "LRA": 11.0}
EXTENSOES = {".wav", ".m4a", ".mp3", ".aac", ".flac", ".ogg", ".opus", ".webm", ".mp4"}


def rodar(args: list[str]) -> subprocess.CompletedProcess:
    # Lista de argumentos sem shell; os caminhos já foram validados como arquivos existentes.
    return subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")  # nosemgrep -- argumentos em lista, sem shell, caminhos validados


def duracao(arq: Path) -> float:
    r = rodar([FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(arq)])
    if r.returncode or not r.stdout.strip():
        sys.exit(f"Não consegui ler a duração de {arq}: {r.stderr.strip()[:200]}")
    return float(r.stdout.strip())


def arquivo(caminho: str, tipo: str) -> Path:
    p = Path(caminho).expanduser().resolve()
    if not p.is_file():
        sys.exit(f"{tipo} não encontrado: {caminho}")
    if tipo == "Áudio" and p.suffix.lower() not in EXTENSOES:
        sys.exit(f"Formato de áudio não suportado: {p.suffix}")
    return p


def montar_trechos(args) -> list[tuple[float, Path]]:
    if args.audio:
        audio = arquivo(args.audio, "Áudio")
        validar_inicio(args.atraso, audio.name)
        return [(args.atraso, audio)]
    base = arquivo(args.trechos, "Lista de trechos")
    itens = json.loads(base.read_text(encoding="utf-8"))
    trechos = []
    for i, item in enumerate(itens):
        if not isinstance(item, dict) or "inicio" not in item or "arquivo" not in item:
            sys.exit(f"Trecho {i + 1}: use {{\"inicio\": segundos, \"arquivo\": caminho}}.")
        caminho = Path(item["arquivo"])
        if not caminho.is_absolute():
            caminho = base.parent / caminho
        try:
            inicio = float(item["inicio"])
        except (TypeError, ValueError):
            sys.exit(f"Trecho {i + 1}: \"inicio\" precisa ser um número de segundos.")
        trechos.append((inicio, arquivo(str(caminho), "Áudio")))
    for inicio, arq in trechos:
        validar_inicio(inicio, arq.name)
    return sorted(trechos, key=lambda t: t[0])


def validar_inicio(inicio: float, nome: str) -> None:
    """Rejeita início negativo, NaN ou infinito: a mistura não corta o começo do áudio, então seria dessincronizado."""
    if not math.isfinite(inicio) or inicio < 0:
        sys.exit(f"Início inválido para {nome}: {inicio}. Use segundos >= 0.")


def filtro_mistura(trechos: list[tuple[float, Path]], total: float) -> str:
    partes = []
    for i, (inicio, _) in enumerate(trechos):
        ms = round(inicio * 1000)
        partes.append(f"[{i + 1}:a]aresample=48000,aformat=channel_layouts=mono,adelay={ms}|{ms}[a{i}]")
    entradas = "".join(f"[a{i}]" for i in range(len(trechos)))
    partes.append(f"{entradas}amix=inputs={len(trechos)}:normalize=0:dropout_transition=0,"
                  f"apad,atrim=0:{total:.3f}[voz]")
    return ";".join(partes)


def main() -> None:
    for fluxo in (sys.stdout, sys.stderr):  # console do Windows em cp1252 não imprime "→"
        if hasattr(fluxo, "reconfigure"):
            fluxo.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video")
    grupo = ap.add_mutually_exclusive_group(required=True)
    grupo.add_argument("--audio", help="gravação contínua da narração")
    grupo.add_argument("--trechos", help="JSON com o início (s) e o arquivo de cada fala")
    ap.add_argument("--atraso", type=float, default=0.0, help="segundos de silêncio antes da gravação contínua")
    ap.add_argument("--saida", help="arquivo de saída (padrão: <vídeo>_narrado.mp4)")
    args = ap.parse_args()

    video = arquivo(args.video, "Vídeo")
    saida = Path(args.saida).resolve() if args.saida else video.with_name(video.stem + "_narrado.mp4")
    if saida == video:
        sys.exit("A saída não pode ser o próprio vídeo original.")
    total = duracao(video)
    trechos = montar_trechos(args)
    for inicio, arq in trechos:
        fim = inicio + duracao(arq)
        if fim > total + 0.05:
            sys.exit(f"{arq.name} termina em {fim:.1f} s, depois do fim do vídeo ({total:.1f} s). "
                     "Encurte a fala ou ajuste o início.")
        print(f"  {inicio:7.2f} s → {fim:7.2f} s  {arq.name}")

    entradas = ["-i", str(video)]
    for _, arq in trechos:
        entradas += ["-i", str(arq)]
    mistura = filtro_mistura(trechos, total)

    # 1ª passagem: mede o volume da voz já posicionada.
    medir = (f"{mistura};[voz]loudnorm=I={ALVO['I']}:TP={ALVO['TP']}:LRA={ALVO['LRA']}:print_format=json[m]")
    r = rodar([FFMPEG, "-hide_banner", "-nostats", *entradas, "-filter_complex", medir, "-map", "[m]", "-f", "null", "-"])
    try:
        bloco = r.stderr[r.stderr.rindex("{"):r.stderr.rindex("}") + 1]
        med = json.loads(bloco)
    except ValueError:
        sys.exit("Falha ao medir o volume:\n" + r.stderr[-800:])

    # 2ª passagem: normalização linear com os valores medidos; vídeo copiado sem recodificar.
    norm = (f"{mistura};[voz]loudnorm=I={ALVO['I']}:TP={ALVO['TP']}:LRA={ALVO['LRA']}:"
            f"measured_I={med['input_i']}:measured_TP={med['input_tp']}:measured_LRA={med['input_lra']}:"
            f"measured_thresh={med['input_thresh']}:offset={med['target_offset']}:linear=true,"
            f"aresample=48000[aout]")
    temp = saida.with_name(saida.stem + ".tmp.mp4")
    r = rodar([FFMPEG, "-hide_banner", "-y", *entradas, "-filter_complex", norm, "-map", "0:v:0", "-map", "[aout]",
               "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-t", f"{total:.3f}",
               "-movflags", "+faststart", str(temp)])
    if r.returncode or not temp.exists():
        sys.exit("ffmpeg falhou:\n" + r.stderr[-1200:])
    if saida.exists():
        backup = saida.with_name(f"{saida.stem}.{time.strftime('%Y%m%d-%H%M%S')}.bak{saida.suffix}")
        saida.rename(backup)
        print(f"Saída anterior preservada em {backup.name}")
    temp.rename(saida)

    final = duracao(saida)
    r = rodar([FFMPEG, "-hide_banner", "-nostats", "-i", str(saida), "-map", "0:a",
               "-af", "loudnorm=print_format=json", "-f", "null", "-"])
    lufs = "?"
    try:
        lufs = json.loads(r.stderr[r.stderr.rindex("{"):r.stderr.rindex("}") + 1])["input_i"]
    except ValueError:
        pass
    print(f"OK: {saida}  ({final:.1f} s; vídeo original {total:.1f} s; volume integrado {lufs} LUFS)")


if __name__ == "__main__":
    main()

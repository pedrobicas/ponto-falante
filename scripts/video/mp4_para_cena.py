"""Converte um MP4 já gravado (ex.: visao/resultados/demo.mp4) numa pasta de cena no formato de captura.js,
para que scripts/video/compor.py possa usá-lo como qualquer outra cena.

    python scripts/video/mp4_para_cena.py <video.mp4> <pasta das cenas> <nome_da_cena> [--fps 15] [--largura 1920]

Gera <pasta>/<nome>/q/*.jpg e indice.json com as marcas "inicio" (0 s) e "fim" (duração). O quadro é centralizado numa
tela 1920x1080 preta, sem esticar. Não altera o conteúdo do vídeo.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

FFMPEG = os.environ.get("FFMPEG") or shutil.which("ffmpeg") or "ffmpeg"
NOME_SEGURO = re.compile(r"^[a-z0-9_]+$")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("cenas")
    ap.add_argument("nome")
    ap.add_argument("--fps", type=float, default=15)
    a = ap.parse_args()
    if not NOME_SEGURO.match(a.nome):
        raise SystemExit("nome de cena inválido (use letras minúsculas, dígitos e _)")
    video = Path(a.video).resolve()
    if not video.is_file():
        raise SystemExit(f"vídeo não encontrado: {video}")
    pasta = Path(a.cenas) / a.nome
    q = pasta / "q"
    shutil.rmtree(pasta, ignore_errors=True)
    q.mkdir(parents=True)
    filtro = (f"fps={a.fps},scale=1920:1080:force_original_aspect_ratio=decrease,"
              "pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=black")
    subprocess.run([FFMPEG, "-v", "error", "-y", "-i", str(video), "-vf", filtro, "-q:v", "2",  # nosemgrep -- lista sem shell
                    str(q / "%05d.jpg")], check=True)
    arquivos = sorted(p.name for p in q.glob("*.jpg"))
    quadros = [{"t": i / a.fps, "a": nome} for i, nome in enumerate(arquivos)]
    fim = len(arquivos) / a.fps
    (pasta / "indice.json").write_text(json.dumps({"quadros": quadros, "marcas": [{"nome": "inicio", "t": 0.0},
                                                                                   {"nome": "fim", "t": fim}]}),
                                       encoding="utf-8")
    print(f"cena {a.nome}: {len(arquivos)} quadros, {fim:.1f} s")


if __name__ == "__main__":
    main()

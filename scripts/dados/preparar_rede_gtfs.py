"""Gera o índice compacto da rede (paradas e itinerários) a partir do GTFS oficial da SPTrans.

    python scripts/dados/preparar_rede_gtfs.py                 # baixa o GTFS oficial e regrava os arquivos
    python scripts/dados/preparar_rede_gtfs.py --zip gtfs.zip  # usa um arquivo já baixado

Por que existe: a busca de paradas da Olho Vivo só encontra as cerca de 360 paradas com nome (corredores) e ignora
endereço e código. O GTFS tem todas as paradas com endereço, coordenadas e a sequência de paradas de cada linha.

Saída (lida pelo Spring em `RedeGtfs`): backend/src/main/resources/rede/
    paradas.tsv.gz   codigo, nome, referencia, latitude, longitude  (só paradas atendidas por alguma linha de ônibus)
    viagens.tsv.gz   letreiro, sentido (1 ou 2), destino, nome da linha, códigos das paradas em ordem
    versao.json      origem, data do feed e contagens

Nada aqui é inventado: paradas sem coordenada ou viagens sem paradas são descartadas e contadas no resumo.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import sys
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
DESTINO = RAIZ / "backend" / "src" / "main" / "resources" / "rede"
URL_OFICIAL = "https://www.sptrans.com.br/umbraco/Surface/PerfilDesenvolvedor/BaixarGTFS?memberName=sptrans"
LIMITE_ZIP = 80 * 1024 * 1024


def baixar() -> bytes:
    req = urllib.request.Request(URL_OFICIAL, headers={"User-Agent": "PontoFalante-FIAP/1.0"})
    with urllib.request.urlopen(req, timeout=180) as r:  # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected -- URL fixa e oficial
        dados = r.read(LIMITE_ZIP + 1)
    if len(dados) > LIMITE_ZIP:
        raise SystemExit("GTFS maior que o limite esperado; download recusado.")
    return dados


def ler(z: zipfile.ZipFile, nome: str):
    with z.open(nome) as f:
        yield from csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"))


def limpo(texto: str) -> str:
    return " ".join((texto or "").replace("\t", " ").split())


def escrever_gz(caminho: Path, linhas: list[str]) -> None:
    # mtime=0 e ordem estável: o mesmo GTFS gera exatamente os mesmos bytes.
    with caminho.open("wb") as bruto, gzip.GzipFile(fileobj=bruto, mode="wb", mtime=0) as gz:
        gz.write(("\n".join(linhas) + "\n").encode("utf-8"))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--zip", type=Path, help="GTFS já baixado; sem isso, baixa da SPTrans.")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    dados = args.zip.read_bytes() if args.zip else baixar()
    z = zipfile.ZipFile(io.BytesIO(dados))
    data_feed = max(datetime(*i.date_time) for i in z.infolist()).date().isoformat()

    rotas = {r["route_id"]: r for r in ler(z, "routes.txt") if r.get("route_type") == "3"}
    viagens = {}
    for t in ler(z, "trips.txt"):
        if t["route_id"] in rotas:
            viagens[t["trip_id"]] = t
    sequencias: dict[str, list[tuple[int, str]]] = {}
    for st in ler(z, "stop_times.txt"):
        if st["trip_id"] in viagens:
            sequencias.setdefault(st["trip_id"], []).append((int(st["stop_sequence"]), st["stop_id"]))

    paradas = {}
    sem_coordenada = 0
    for s in ler(z, "stops.txt"):
        try:
            lat, lon = float(s["stop_lat"]), float(s["stop_lon"])
        except (TypeError, ValueError):
            sem_coordenada += 1
            continue
        paradas[s["stop_id"]] = (limpo(s["stop_name"]), limpo(s.get("stop_desc", "")), lat, lon)

    linhas_viagens, usadas, sem_paradas = [], set(), 0
    for trip_id in sorted(viagens):
        t = viagens[trip_id]
        ordem = [sid for _, sid in sorted(sequencias.get(trip_id, [])) if sid in paradas]
        if len(ordem) < 2:
            sem_paradas += 1
            continue
        usadas.update(ordem)
        rota = rotas[t["route_id"]]
        sentido = "2" if t.get("direction_id") == "1" else "1"
        linhas_viagens.append("\t".join([limpo(rota["route_short_name"]), sentido, limpo(t.get("trip_headsign", "")),
                                         limpo(rota.get("route_long_name", "")), ",".join(ordem)]))
    linhas_paradas = ["\t".join([sid, paradas[sid][0], paradas[sid][1], f"{paradas[sid][2]:.6f}", f"{paradas[sid][3]:.6f}"])
                      for sid in sorted(usadas, key=int)]

    DESTINO.mkdir(parents=True, exist_ok=True)
    escrever_gz(DESTINO / "paradas.tsv.gz", linhas_paradas)
    escrever_gz(DESTINO / "viagens.tsv.gz", linhas_viagens)
    versao = {"origem": "GTFS oficial da SPTrans", "url": URL_OFICIAL, "data_do_feed": data_feed,
              "gerado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "paradas": len(linhas_paradas), "viagens": len(linhas_viagens),
              "linhas": len({v.split("\t")[0] for v in linhas_viagens}),
              "descartes": {"paradas_sem_coordenada": sem_coordenada, "viagens_sem_paradas": sem_paradas,
                            "paradas_sem_linha_de_onibus": len(paradas) - len(usadas)}}
    (DESTINO / "versao.json").write_text(json.dumps(versao, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(versao, ensure_ascii=False))


if __name__ == "__main__":
    main()

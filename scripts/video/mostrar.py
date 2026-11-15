"""Mostra, no terminal de gravação, trechos de arquivos reais do projeto em formato legível.

    mostrar.py regras <monitoramento.yaml>     seção das regras de decisão
    mostrar.py auditoria <auditoria.jsonl>     último registro da trilha de auditoria
    mostrar.py placar <placar.csv> [...]       colunas principais dos placares da avaliação
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
modo, caminhos = sys.argv[1], [Path(p) for p in sys.argv[2:]]

if modo == "regras":
    texto = caminhos[0].read_text(encoding="utf-8").splitlines()
    for secao, titulo in (("regras_estimadas", "# produção: previsões reais da SPTrans"),
                          ("regras:", "# teste local: histórico SIMULADO")):
        dentro = False
        print(titulo)
        for linha in texto:
            if linha.startswith(secao):
                dentro = True
            elif dentro and linha and not linha.startswith((" ", "#")):
                break
            if dentro and not linha.strip().startswith(("antecipacao", "atraso_maximo", "minutos_max", "cobertura")):
                print(linha)
        print()
elif modo == "auditoria":
    ultimo = json.loads(caminhos[0].read_text(encoding="utf-8").strip().splitlines()[-1])
    for chave, valor in ultimo.items():
        print(f"{chave}: {json.dumps(valor, ensure_ascii=False)}")
elif modo == "placar":
    colunas = [("configuracao", "configuração", 22), ("acerto_total", "acerto", 16), ("recusa_indevida", "recusa indevida", 17),
               ("erros_factuais_por_pergunta", "erro factual/pergunta", 23), ("recusa_correta_nao_consta", "recusa correta", 16)]
    extra = 2 if len(caminhos) > 1 else 0
    print(colunas[0][1].ljust(colunas[0][2] + extra) + "".join(titulo.ljust(largura) for _, titulo, largura in colunas[1:]))
    for caminho in caminhos:
        with caminho.open(encoding="utf-8", newline="") as f:
            for linha in csv.DictReader(f):
                nome = caminho.parent.name.replace("_", " ") if len(caminhos) > 1 else linha["configuracao"]
                print(nome.ljust(colunas[0][2] + extra)
                      + "".join(linha[c].ljust(largura) for c, _, largura in colunas[1:]))

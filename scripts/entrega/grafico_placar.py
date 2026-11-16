"""Desenha o gráfico do placar do 1º ciclo para o relatório, lendo genai/avaliacao/placar_teste.csv sem alterar valores.

Uso na raiz: .venv/Scripts/python.exe scripts/entrega/grafico_placar.py
Saída: genai/avaliacao/placar_teste_relatorio.png (o gráfico original do notebook continua em placar_teste.png).
"""
from __future__ import annotations

import csv
from pathlib import Path

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
CSV = ROOT / 'genai/avaliacao/placar_teste.csv'
SAIDA = ROOT / 'genai/avaliacao/placar_teste_relatorio.png'
METRICAS = [('acerto_total_%', 'Acerto total'), ('recusa_correta_nao_consta_%', 'Recusa correta'),
            ('alucinacao_%', 'Alucinação'), ('recusa_indevida_%', 'Recusa indevida'),
            ('sem_fundamentacao_%', 'Sem fundamentação')]
CONFIGS = [('sem_contexto', 'A · sem contexto', '#9aa9b1'), ('rag', 'B · RAG simples', '#4f8fb0'),
           ('agente', 'C · RAG com agente', '#0b4f6c')]


def main() -> None:
    linhas = {l['configuracao']: l for l in csv.DictReader(CSV.open(encoding='utf-8'))}
    plt.rcParams.update({'font.family': 'Segoe UI', 'font.size': 10})
    fig, ax = plt.subplots(figsize=(8.6, 3.6), dpi=200)
    largura = 0.26
    for i, (chave, rotulo, cor) in enumerate(CONFIGS):
        valores = [float(linhas[chave][m]) for m, _ in METRICAS]
        xs = [j + (i - 1) * largura for j in range(len(METRICAS))]
        barras = ax.bar(xs, valores, largura, label=rotulo, color=cor)
        for b, v in zip(barras, valores):
            ax.text(b.get_x() + b.get_width() / 2, v + 1.5, (f'{v:.1f}'.replace('.', ',').replace(',0', '')), ha='center', fontsize=7,
                    color='#33464f')
    ax.set_xticks(range(len(METRICAS)), [n for _, n in METRICAS])
    ax.set_ylabel('% das perguntas')
    ax.set_ylim(0, 112)
    ax.spines[['top', 'right']].set_visible(False)
    ax.grid(axis='y', color='#e3e9ec', linewidth=0.8)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, ncol=3, loc='upper center', bbox_to_anchor=(0.5, 1.13), fontsize=9)
    fig.tight_layout()
    fig.savefig(SAIDA)
    print(SAIDA)


if __name__ == '__main__':
    main()

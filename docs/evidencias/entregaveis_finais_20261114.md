# Fechamento dos entregáveis - 14/11/2026

Índice: [`entregaveis/LEIA_ME.md`](../../entregaveis/LEIA_ME.md).

| Arquivo | Verificação concluída |
|---|---|
| `Ponto_Falante_RPA.mp4` | 170 s, H.264, 1600 x 900, 25 fps, sem áudio; decodificação integral sem erros |
| `Ponto_Falante_GenAI.mp4` | 190 s, H.264, 1600 x 900, 25 fps, sem áudio; decodificação integral sem erros |
| `Relatorio_RPA.pdf` | 10 páginas renderizadas e inspecionadas; 12 seções, cinco integrantes/RMs, integração e BPMN completo/ampliado |
| `Relatorio_GenAI.pdf` | 15 páginas renderizadas e inspecionadas; diagramas, fontes, metodologia, placares e erros preservados |
| `ROTEIRO_RPA.md` / `ROTEIRO_GENAI.md` | Tempos correspondem às timelines finais; orientações para narração humana |

Os dois MP4 conservaram seus hashes originais. As saídas de validação e hashes estão em
`entregaveis/VALIDACAO_VIDEOS.json` e `entregaveis/VALIDACAO_DOCUMENTOS.json`.
A cópia de `rpa/docs/relatorio.pdf` é idêntica à de `entregaveis/`.
Os PDFs têm links HTTPS ativos como anotações; as URLs ainda não fornecidas estão claramente
marcadas como pendentes. Não foi declarado acesso público do repositório privado.

Revisão visual por renderização PDFium local (Poppler não estava instalado), incluindo tabelas,
diagramas, captura do boletim e páginas finais. Registros e imagens em
`.validation/entrega-final/`; versões anteriores do PDF/Markdown RPA e relatório GenAI preservadas
em `antes/`. O HTML gerado antigo também foi arquivado ali, sem apagar seu conteúdo.

O comando original `rpa/docs/gerar_relatorio_pdf.py` encaminha ao exportador de ambos os relatórios
em `scripts/entrega/gerar_pdfs.py`; dependências registradas em `scripts/entrega/requirements.txt`.
Sintaxe dos dois exportadores conferida, sem novas suítes de testes ou chamadas ao modelo.

Critérios e alcance da execução real: [vídeo RPA](video_rpa_20261114.md),
[vídeo GenAI](video_genai_20261114.md). Timeout: [diagnóstico](timeout_genai_20261114.md).
O trabalho não modificou código do produto, serviço estável, resultados de avaliação ou histórico Git.

Dependências do dono/equipe: revisão e narração; hospedagem e URLs; autorização/destino da cópia
pública sanitizada; submissão ao Teams e manutenção do acesso durante a correção.

# Roteiro do vídeo RPA (até 3 minutos)

O roteiro de narração completo, com as falas por trecho, está em [`entregaveis/ROTEIRO_RPA.md`](../../entregaveis/ROTEIRO_RPA.md), na raiz do projeto.
Vídeo local: [`entregaveis/Ponto_Falante_RPA.mp4`](../../entregaveis/Ponto_Falante_RPA.mp4), **2 min 12 s (132 s, abaixo do limite de 180 s)**,
1920 x 1080, sem áudio e sem música. A URL pública ainda depende de hospedagem. O repositório continua privado.

As cenas foram gravadas em 14/11/2026, das 23:08 às 23:19, com o site publicado e comandos reais. O rodapé de cada cena mostra o capítulo e a
natureza do dado (**DADOS REAIS**, **ESTIMADO**, **SIMULADO** ou **REPOSITÓRIO**). Não há narração, música nem trecho acelerado.

| Tempo | Cena | Natureza |
|---|---|---|
| 00:00-00:16 | Busca de ponto e previsões no site publicado | Real |
| 00:16-00:34 | BPMN dos robôs de coleta e de boletim | Documento |
| 00:34-00:41 | Regras de decisão em `config/monitoramento.yaml` | Repositório |
| 00:41-00:54 | Coletor somente leitura: 6 pontos, 27 ônibus previstos | Real |
| 00:54-01:00 | Execuções agendadas no GitHub Actions | Real |
| 01:00-01:12 | Execução completa: 349 recebidos, 330 válidos, 1 CRÍTICA, 2 ATENÇÃO, 2 OK, código 0 | Simulado (MVP local) |
| 01:12-01:21 | Boletim HTML gerado na mesma execução | Simulado |
| 01:21-01:37 | HTTP 503, 3 tentativas (2 s e 4 s), boletim anterior desatualizado, código 2 | Simulado |
| 01:37-01:44 | Trilha de auditoria da execução com falha | Simulado |
| 01:44-02:00 | Boletim de 13/11 publicado em produção (17 consultas, 24 linhas, 6 em atenção) | Estimado |
| 02:00-02:12 | A assistente responde com o boletim e seus limites | Estimado |

Ferramentas de gravação: `scripts/video/cap_rpa.js` (captura), `scripts/video/terminal_real.py` (terminal com comandos fixos) e
`scripts/video/compor.py` com `scripts/video/edl_rpa.json` (montagem). Evidência: [`docs/evidencias/video_rpa_20261115.md`](../../docs/evidencias/video_rpa_20261115.md).

# Roteiro do vídeo RPA (até 3 minutos)

Gravação: OBS ou Xbox Game Bar (Win+G), tela cheia, fonte do terminal grande. Abas já abertas antes de gravar:
o site publicado, o GitHub Actions do repositório e um terminal na pasta `rpa/`.

| Tempo | Fala (resumo) | Na tela |
|---|---|---|
| 0:00–0:25 | "O Ponto Falante fala a previsão dos ônibus para quem não enxerga bem. Para avisar que uma linha anda com espera longa, alguém teria de consultar os pontos o dia todo e escrever um aviso. Dois robôs fazem isso sozinhos." | Site publicado, depois o BPMN `docs/fluxo.png` |
| 0:25–0:55 | Explicar os dois robôs: o coletor consulta 6 pontos 8 vezes por dia e grava amostras reais; o boletim valida, remove duplicados, decide por linha e publica. Mostrar as regras no YAML. | BPMN + `config/monitoramento.yaml` (`regras_estimadas`) |
| 0:55–1:35 | Execução real: abrir a coleta no GitHub Actions e apontar no log "44 ônibus previstos em 16 linhas" e "6 gravadas, 0 rejeitadas". Dizer por que o boletim é **estimado**: previsão não é chegada observada. | GitHub Actions (`rpa-coleta`) |
| 1:35–2:05 | Integração: abrir `/boletim` no site e deixar a tela ler em voz alta, com o selo **Estimado** (ou **Indisponível**, quando não houve coleta no dia, sem números inventados). | Navegador |
| 2:05–2:40 | Falha: com o mock (`uvicorn tools.mock_mvp:app --port 8080`), ligar `POST /admin/falha?ativo=true` e rodar `python -m pf_rpa.robo --data 2026-11-12`. Mostrar as 3 tentativas com espera crescente e o boletim anterior publicado como "desatualizado". Mostrar `logs/auditoria.jsonl`. | Terminal |
| 2:40–3:00 | Testes: `python -m pytest -q` → "45 passed". Encerrar com o benefício: autonomia para o passageiro e lista de linhas em atenção para a gestora. | Terminal |

Dica: ensaie com cronômetro; se passar de 3 min, corte a explicação do YAML.

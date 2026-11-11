# Roteiro do vídeo RPA (até 3 minutos)

Gravação: OBS ou Xbox Game Bar (Win+G), tela cheia, fonte do terminal grande. Dois terminais lado a lado: à esquerda o mock/MVP, à direita o robô.

| Tempo | Fala (resumo) | Na tela |
|---|---|---|
| 0:00–0:25 | "O Ponto Falante fala a previsão dos ônibus para quem não enxerga bem. Para avisar que uma linha anda atrasando, alguém teria de acompanhar, anotar e comparar tudo à mão, todo dia. Nosso robô faz isso sozinho." | Tela do MVP (Angular) e depois o BPMN `docs/fluxo.png` |
| 0:25–0:50 | Explicar o fluxo: busca o histórico no MVP, valida cada registro, remove duplicados, decide por linha, publica o boletim. Mostrar a regra no YAML. | BPMN + `config/monitoramento.yaml` |
| 0:50–1:40 | Rodar `python -m pf_rpa.robo --data 2026-11-12`. Apontar no log: 349 recebidos, inválidos por motivo, duplicados, "1001-10 → CRITICA (atraso médio 14,7 > 10)". | Terminal com o log |
| 1:40–2:10 | Integração: abrir `GET /boletim` e a tela de boletim do MVP lendo em voz alta, com o selo "dados simulados". | Navegador |
| 2:10–2:45 | Falha: `POST /admin/falha?ativo=true` e rodar de novo. Mostrar as 3 tentativas com espera crescente e o boletim anterior publicado como "desatualizado". Mostrar `logs/auditoria.jsonl`. | Terminal + navegador |
| 2:45–3:00 | Testes: `python -m pytest -q` → "14 passed". Encerrar com o benefício: autonomia para o passageiro e lista de linhas críticas para a gestora. | Terminal |

Dica: ensaie com cronômetro; se passar de 3 min, corte a explicação do YAML.

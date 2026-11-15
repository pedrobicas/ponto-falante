# Evidências dos testes

## Atualização de 15/11/2026

Execução local em 15/11/2026, Python 3.11, `python -m pytest -q` dentro de `rpa/`: **53 testes aprovados em 18,62 s**.

```text
.....................................................                    [100%]
53 passed in 18.62s
```

Novos em `tests/test_falhas_extras.py` (todos com mock ou respostas fabricadas, nunca coleta real):

| Cenário | Comportamento verificado |
|---|---|
| Timeout em todas as tentativas | 3 tentativas com esperas de 2 s e 4 s, depois `MVPIndisponivel` |
| Timeout seguido de resposta | Recupera na segunda tentativa, sem erro |
| HTTP 503 seguido de 200 | Recupera após uma espera de 2 s |
| Corpo vazio, HTML ou formato errado | `RespostaInvalida`: nada vira amostra |
| Duas execuções para a mesma data | Mesmo boletim, mesmas estatísticas, um arquivo por data, publicação igual no MVP |

Já cobertos antes: MVP fora (republica o último boletim como desatualizado, código 2), chave recusada (lote guardado e
reenviado depois), publicação recusada (cópia local, código de falha), dados inválidos e duplicados (descartados com
motivo), lote pendente com formato errado (quarentena) e chave fora dos logs. Em produção, a deduplicação de amostras
também acontece no backend (`Envio: 6 gravadas, 0 duplicadas` no log da coleta).

## Atualização de 14/11/2026

A validação da revisão `3c4fb1a` registrou **46 testes aprovados em 18,96 s**, sem falhas.
Fonte local preservada: `.validation/rpa-privacy.log`, na raiz do projeto. O log é evidência da sessão anterior;
esta consolidação não executou novamente os testes.

```text
..............................................                           [100%]
46 passed in 18.96s
```

Os cenários atuais estão em `tests/` e abrangem coleta real, decisão por linha, insuficiência de amostras,
origem declarada, publicação, tentativas após falha e proteção de segredos nos logs.
A validação integrada local de 14/11 está resumida em
[`docs/evidencias/validacao_neutra_20261114.json`](../../docs/evidencias/validacao_neutra_20261114.json).

## Evidência histórica de 11/11/2026

Execução em 11/11/2026, Windows 11, Python 3.11, comando `python -m pytest -v` dentro de `rpa/`.

```text
============================= test session starts =============================
platform win32 -- Python 3.11.9, pytest-9.2.0, pluggy-1.7.0 -- D:\GLOBALSOLUTION_2\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: D:\GLOBALSOLUTION_2\rpa
configfile: pyproject.toml
testpaths: tests
plugins: anyio-4.16.0
collecting ... collected 14 items

tests/test_cenarios.py::test_sucesso_ponta_a_ponta PASSED                [  7%]
tests/test_cenarios.py::test_decisao_com_dados_do_mock PASSED            [ 14%]
tests/test_cenarios.py::test_regra_de_decisao_limites PASSED             [ 21%]
tests/test_cenarios.py::test_sem_dados_nao_decide_no_escuro PASSED       [ 28%]
tests/test_cenarios.py::test_intervalo_ignora_buraco_programado_mas_pega_onibus_que_sumiu PASSED [ 35%]
tests/test_cenarios.py::test_falha_mvp_fora_mantem_boletim_anterior_desatualizado PASSED [ 42%]
tests/test_cenarios.py::test_falha_total_sem_boletim_anterior PASSED     [ 50%]
tests/test_cenarios.py::test_retry_com_backoff_exponencial PASSED        [ 57%]
tests/test_cenarios.py::test_publicacao_recusada_salva_local PASSED      [ 64%]
tests/test_cenarios.py::test_publicacao_com_chave_correta PASSED         [ 71%]
tests/test_cenarios.py::test_chave_nunca_aparece_no_log PASSED           [ 78%]
tests/test_cenarios.py::test_gtfs_ausente_usa_rede_ficticia_e_avisa PASSED [ 85%]
tests/test_cenarios.py::test_gtfs_invalido_e_sem_fallback_para PASSED    [ 92%]
tests/test_cenarios.py::test_validacao_motivos PASSED                    [100%]

============================= 14 passed in 5.32s ==============================

```

## Execução real contra o mock (3 rodadas: sucesso, sucesso, MVP fora)

Comandos: `python -m pf_rpa.robo --data 2026-11-11`, `--data 2026-11-12`, depois `POST /admin/falha?ativo=true` e `--data 2026-11-13`.

### logs/rpa_2026-11-11.log

```text
2026-11-11 10:31:54 | INFO    | pf_rpa.robo | === Início da execução | data de referência 2026-11-11 | MVP http://127.0.0.1:8080 ===
2026-11-11 10:31:54 | WARNING | pf_rpa.gtfs | GTFS real indisponível (arquivo ausente: routes.txt); usando rede fictícia documentada
2026-11-11 10:31:54 | INFO    | pf_rpa.robo | Histórico recebido: 349 registros
2026-11-11 10:31:54 | INFO    | pf_rpa.robo | Validação: 330 válidos, 9 inválidos {'campo_vazio': 1, 'horario_incoerente': 2, 'linha_inexistente': 6}, 10 duplicados, 0 fora do escopo
2026-11-11 10:31:54 | INFO    | pf_rpa.robo | Linha 1001-10 -> CRITICA (atraso médio 14.1 min > 10)
2026-11-11 10:31:54 | INFO    | pf_rpa.robo | Linha 1002-10 -> ATENCAO (atraso médio 7.0 min > 5)
2026-11-11 10:31:54 | INFO    | pf_rpa.robo | Linha 1005-10 -> ATENCAO (intervalo de 26 min > 20)
2026-11-11 10:31:54 | INFO    | pf_rpa.robo | Linha 1003-10 -> OK (dentro dos limites)
2026-11-11 10:31:54 | INFO    | pf_rpa.robo | Linha 1004-10 -> OK (dentro dos limites)
2026-11-11 10:31:54 | INFO    | pf_rpa.robo | Boletim salvo em saida\boletim_2026-11-11.json
2026-11-11 10:31:54 | INFO    | pf_rpa.robo | Boletim publicado no MVP (POST /boletim)
2026-11-11 10:31:54 | INFO    | pf_rpa.robo | === Fim da execução | status=sucesso | código=0 ===
2026-11-11 10:31:54 | INFO    | pf_rpa.robo | === Início da execução | data de referência 2026-11-12 | MVP http://127.0.0.1:8080 ===
2026-11-11 10:31:54 | WARNING | pf_rpa.gtfs | GTFS real indisponível (arquivo ausente: routes.txt); usando rede fictícia documentada
2026-11-11 10:31:54 | INFO    | pf_rpa.robo | Histórico recebido: 349 registros
2026-11-11 10:31:54 | INFO    | pf_rpa.robo | Validação: 330 válidos, 9 inválidos {'campo_vazio': 2, 'horario_incoerente': 3, 'linha_inexistente': 4}, 10 duplicados, 0 fora do escopo
2026-11-11 10:31:54 | INFO    | pf_rpa.robo | Linha 1001-10 -> CRITICA (atraso médio 14.7 min > 10)
2026-11-11 10:31:54 | INFO    | pf_rpa.robo | Linha 1002-10 -> ATENCAO (atraso médio 6.8 min > 5)
2026-11-11 10:31:54 | INFO    | pf_rpa.robo | Linha 1005-10 -> ATENCAO (intervalo de 28 min > 20)
2026-11-11 10:31:54 | INFO    | pf_rpa.robo | Linha 1003-10 -> OK (dentro dos limites)
2026-11-11 10:31:54 | INFO    | pf_rpa.robo | Linha 1004-10 -> OK (dentro dos limites)
2026-11-11 10:31:54 | INFO    | pf_rpa.robo | Boletim salvo em saida\boletim_2026-11-12.json
2026-11-11 10:31:54 | INFO    | pf_rpa.robo | Boletim publicado no MVP (POST /boletim)
2026-11-11 10:31:54 | INFO    | pf_rpa.robo | === Fim da execução | status=sucesso | código=0 ===
2026-11-11 10:31:55 | INFO    | pf_rpa.robo | === Início da execução | data de referência 2026-11-13 | MVP http://127.0.0.1:8080 ===
2026-11-11 10:31:55 | WARNING | pf_rpa.gtfs | GTFS real indisponível (arquivo ausente: routes.txt); usando rede fictícia documentada
2026-11-11 10:31:55 | WARNING | pf_rpa.mvp | GET /historico?data=2026-11-13 falhou (tentativa 1/3): HTTP 503
2026-11-11 10:31:56 | WARNING | pf_rpa.mvp | GET /historico?data=2026-11-13 falhou (tentativa 2/3): HTTP 503
2026-11-11 10:31:58 | WARNING | pf_rpa.mvp | GET /historico?data=2026-11-13 falhou (tentativa 3/3): HTTP 503
2026-11-11 10:31:58 | ERROR   | pf_rpa.robo | MVP indisponível para leitura do histórico: GET /historico?data=2026-11-13: sem resposta após 3 tentativas (HTTP 503)
2026-11-11 10:31:58 | WARNING | pf_rpa.robo | Republicando o boletim de 2026-11-12 marcado como desatualizado
2026-11-11 10:31:58 | INFO    | pf_rpa.robo | Boletim desatualizado publicado no MVP
2026-11-11 10:31:58 | ERROR   | pf_rpa.robo | === Fim da execução | status=mvp_indisponivel | código=2 ===

```

### logs/auditoria.jsonl

```json
{"registrado_em": "2026-11-11T10:31:54-03:00", "data_referencia": "2026-11-11", "status": "sucesso", "codigo_saida": 0, "publicado": true, "duracao_s": 0.03, "estatisticas": {"recebidos": 349, "validos": 330, "invalidos": 9, "duplicados": 10, "fora_escopo": 0}, "linhas_por_status": {"CRITICA": 1, "ATENCAO": 2, "OK": 2}, "fonte_dados": {"olhovivo": 0, "simulador": 330}, "erros": []}
{"registrado_em": "2026-11-11T10:31:54-03:00", "data_referencia": "2026-11-12", "status": "sucesso", "codigo_saida": 0, "publicado": true, "duracao_s": 0.03, "estatisticas": {"recebidos": 349, "validos": 330, "invalidos": 9, "duplicados": 10, "fora_escopo": 0}, "linhas_por_status": {"CRITICA": 1, "ATENCAO": 2, "OK": 2}, "fonte_dados": {"olhovivo": 0, "simulador": 330}, "erros": []}
{"registrado_em": "2026-11-11T10:31:58-03:00", "data_referencia": "2026-11-13", "status": "mvp_indisponivel", "codigo_saida": 2, "publicado": true, "duracao_s": 3.07, "estatisticas": {}, "linhas_por_status": {}, "fonte_dados": {}, "erros": ["GET /historico?data=2026-11-13: sem resposta após 3 tentativas (HTTP 503)"]}

```

# Estado do projeto

Situação em 16/11/2026. Entrega da Global Solution: **19/11/2026, 23h55**, no Teams de cada disciplina. Repositórios,
aplicação e vídeos precisam ficar públicos e funcionando até cerca de 26/11.

## Onde está cada parte

| Parte | Situação | Onde |
|---|---|---|
| MVP (Angular + Spring Boot + PostgreSQL) | Publicado no Render, deploy automático depois da CI | https://ponto-falante.onrender.com |
| SPTrans | Previsões em tempo real pela Olho Vivo; busca de pontos e linhas pelo cadastro oficial (GTFS) | `backend/` |
| GenAI | Assistente de direitos com RAG e agente sobre `qwen2.5:7b` local; produção usa `PF_MODO=agente` | `genai/`, `scripts/genai/` |
| RPA | Coleta oito vezes por dia e boletim diário às 6h no GitHub Actions, publicados no MVP | `rpa/`, `.github/workflows/` |
| Relatório GenAI | Completo, com métricas originais; só faltam os links externos | `genai/RELATORIO.md`, `entregaveis/Relatorio_GenAI.pdf` |
| Relatório RPA | Completo, com BPMN em anexo; só faltam os links externos | `rpa/docs/relatorio.md`, `rpa/docs/relatorio.pdf` |
| Vídeos | Gravados, sem narração; roteiros prontos | `entregaveis/` (fora do Git) |

## Validação de 16/11/2026

- Testes locais: backend 225 (Spring Boot, com PostgreSQL embutido), Angular 55 com axe, GenAI 155, RPA 53, integração 26;
  build de produção do Angular; `npm audit` sem vulnerabilidades. A CI repete tudo e roda Gitleaks, Semgrep e Trivy.
- Navegador real, desktop e celular (375 px, sem rolagem horizontal): busca por nome e código, previsões ao vivo da
  SPTrans, assistente com pergunta de direitos (resposta com fonte oficial), pergunta de horário (consulta direta à
  SPTrans), pergunta de outra cidade (fora da área), assistente indisponível com o PC desligado, e boletim publicado.
- Problemas encontrados e corrigidos com teste de regressão: ordem da busca por nome de rua ("Paulista" agora traz a
  Av. Paulista primeiro), concordância em "1 ônibus previsto", artigo em cidades de fora ("do Rio de Janeiro") e aviso
  de fora da área repetido.
- Histórico do Git reorganizado sem dados pessoais e sem arquivos internos de processo, mantendo os 69 commits
  originais, autores e datas. O histórico da CI até essa data está em `docs/evidencias/ci_historico.md`.

## Operação

- **GenAI ligada:** `powershell -ExecutionPolicy Bypass -File scripts\genai\iniciar.ps1 -TunelRapido` e, para conferir,
  `scripts\genai\status.ps1` (`llm_ok=True` e "registrado no backend"). A primeira pergunta depois de ligar leva cerca de
  45 s para carregar o modelo; as seguintes, cerca de 10 s. Com o PC desligado, o site continua no ar e só o assistente
  de direitos fica indisponível.
- **Links da entrega:** preencher `docs/links_entrega.json` e rodar `scripts/entrega/gerar_pdfs.py`, que coloca os
  links nos relatórios, nos READMEs e nos PDFs. Depois, `scripts/entrega/montar_entrega_final.py` monta
  `entregaveis/ENTREGA_FINAL/`.
- **Conjuntos fechados da GenAI:** não reexecutar `v2/` nem `v3/`; o placar final já está registrado.

## Pendências

Só ações que dependem do integrante, descritas em `entregaveis/O_QUE_FALTA_VOCE_FAZER.md`: narrar e publicar os dois
vídeos, autorizar a publicação do repositório, preencher os links e enviar no Teams.

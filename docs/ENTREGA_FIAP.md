# Entrega FIAP - checklist atual

Conferido em **14/11/2026** no [PDF oficial](../Global_Solution_2026_2_CitizenTech_FIAP.pdf).
Este checklist consolida as pendências atuais; os relatos anteriores permanecem como histórico.
Não houve nova execução nem leitura dos conjuntos finais fechados de avaliação da GenAI.

**Fechamento dos arquivos de GenAI e RPA (vídeos regravados em 14/11, montados e revisados em 15/11):** vídeos, roteiros e relatórios concluídos
para revisão e narração. Índice local: [`entregaveis/LEIA_ME.md`](../entregaveis/LEIA_ME.md).
RPA: 132 s; GenAI: 142 s (conversa regravada em 15/11); H.264, 1920 x 1080, 30 fps, sem áudio; ambos decodificados integralmente. Versões anteriores em `entregaveis/versao_anterior_20261114/`.
Restam narração, hospedagem dos vídeos, publicação do repositório, preenchimento dos links e submissão.
Os vídeos foram regravados com captura real do site publicado e dos comandos; nenhuma avaliação fechada foi reexecutada.

## Prazo e regras comuns

- **19/11/2026 às 23h55**, no Teams de cada disciplina, por **um integrante** da equipe (pp. 24-27).
- Até cinco integrantes, mesma equipe e mesmo produto nas sete disciplinas.
- Aplicações, repositórios e vídeos devem permitir acesso durante a correção, que pode ocorrer até uma semana
  após o encerramento (p. 24). Planejar disponibilidade até **26/11/2026**. O pitch deve ser não listado no YouTube,
  conforme a regra específica da p. 42.
- A ficha técnica comum deve abrir o README e orientar a documentação das disciplinas (p. 20).
  Ela está no [README principal](../README.md#ficha-técnica-do-mvp).
- O repositório ainda é **privado**. A exigência de acesso público é explícita; o histórico já foi revisado e o
  próprio `pedrobicas/ponto-falante` será publicado. Não enviar um link privado ao avaliador.

## GenAI - relatório no GitHub e link no Teams

Base oficial: pp. 29-31. O relatório não precisa ser PDF; precisa estar no GitHub público.

| Exigência | Evidência existente | Falta para a entrega |
|---|---|---|
| Tarefa, integrantes e ficha técnica | [Relatório](../genai/RELATORIO.md), seções 1-2 | Nenhuma lacuna de conteúdo identificada |
| Pipeline de IA e documentos; fontes, formato, licença e trechos | Relatório, seções 3 e 5; `genai/base/` | Preservar no repositório público |
| Casos com gabarito e "não consta"; avaliação sem contaminação | Estrutura `genai/avaliacao/` e metodologia já documentada | Preservar os artefatos congelados; não reexecutar para a gravação |
| Recall@1/@3, limiar, JSON, citações, recusa e comparação entre configurações | Relatório, seções 6-7 e iterações documentadas | Usar os resultados já salvos e identificar o ciclo mostrado |
| Cinco erros reais, causas e correções; conclusão | Relatório, seções 8-9; análises posteriores separadas | Nenhuma nova avaliação necessária |
| Notebooks com saídas, API e reprodução | Quatro notebooks com saídas salvas, API e [README GenAI](../genai/README.md) | Abertura pública e, se possível, reprodução em outra máquina |
| Link do vídeo no relatório | MP4 silencioso de 142 s e [roteiro final](../entregaveis/ROTEIRO_GENAI.md) validados | Narrar, hospedar e preencher `video_genai` em `docs/links_entrega.json` |
| Repositório público | Histórico revisado, repositório ainda privado | Tornar público e preencher o link |

O PDF oficial exige vídeo, mas **não fixa duração para GenAI** nessas páginas. Os três minutos do roteiro são uma
meta de edição. Na demonstração, consultar exemplos públicos, mostrar a fonte realmente recebida e distinguir
ferramentas de horários da GenAI de direitos. Uma indisponibilidade real deve ser declarada.

## RPA - PDF único com links, vídeo de até 3 minutos

Base oficial: pp. 46-50. O vídeo vale 2 pontos; documentação, 2; integração, 1; desenvolvimento, 5.

| Exigência | Evidência existente | Falta para a entrega |
|---|---|---|
| Relatório com os 12 itens, integrantes e RMs | [Fonte Markdown](../rpa/docs/relatorio.md) e [PDF final para revisão](../entregaveis/Relatorio_RPA.pdf), com BPMN ampliado | Inserir URLs de hospedagem e regenerar; conteúdo concluído |
| BPMN/PDD, entradas, decisões, repetição e exceções | [BPMN editável](../rpa/docs/fluxo.bpmn), [fluxo visual](../rpa/docs/fluxo.png), relatório, seções 4-7 | Preservar arquivos e legibilidade no PDF final |
| Implementação Python, README, logs, imagens e testes | `rpa/src/`, `rpa/logs/`, `rpa/assets/`, `rpa/tests/` e [README](../rpa/README.md) | Disponibilizar na cópia pública |
| Integração verificável com o MVP | MP4 mostra execução do robô contra mock e integração em produção com data e categoria | Concluído; alcance e origens em [evidência RPA](evidencias/video_rpa_20261115.md) |
| Sucesso, decisão e falha | [Evidências](../rpa/tests/EVIDENCIAS.md); 53 testes passando em 15/11; vídeo mostra sucesso e 503 local | Concluído |
| Vídeo até 3 minutos com execução, regra, integração e falha | MP4 silencioso de 132 s e [roteiro final](../entregaveis/ROTEIRO_RPA.md) validados | Narrar, hospedar e inserir a URL no relatório e README |

O PDF tem o conteúdo final para revisão, com campos explícitos para as URLs pendentes.
Após inserir os links nos relatórios, atualizar os dois PDFs na raiz:

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/entrega/gerar_pdfs.py
```

Conferir visualmente o PDF inteiro, os links clicáveis, o BPMN, a captura do boletim, nomes/RMs e os cenários.
Só então anexar o PDF ao Teams. Não usar o boletim antigo como confirmação de condições de "hoje".

## Demais disciplinas - confirmar artefatos da equipe

Esta verificação procurou entregáveis no repositório atual. **Não localizar aqui não prova que outro integrante
não os tenha em outro repositório.** Os contratos de integração existentes não substituem a implementação e as
evidências específicas exigidas abaixo.

| Disciplina e páginas | Entrega exigida | Encontrado aqui / lacuna a confirmar com o responsável |
|---|---|---|
| Big Data (32-38) | Git público com DAGs Airflow, notebooks/SQL Databricks, amostras e README; PDF com fontes, Graph/Grid, camadas, dois lotes, idempotência, cinco consultas e tela do MVP | Contrato de integração pronto; não localizados DAGs, notebooks Databricks ou PDF. Exige ao menos duas fontes, duas tarefas paralelas, validação, três regras de qualidade, uma fato e duas dimensões |
| Business Intelligence / pitch (41-42) | Vídeo da equipe até **5 minutos**, YouTube não listado, MVP real; problema com evidência, negócio, indicadores, viabilidade e pedido; nomes/RMs no envio | MVP e ficha comum disponíveis; não localizado vídeo/URL ou roteiro de pitch completo. A equipe deve aparecer e conduzir o pitch |
| Applied Computer Vision (44) | Git com documentação/código; PDF com título, integrantes, resumo de 250 palavras, introdução, objetivo de 50 palavras, ferramentas, método, resultados e conclusão; vídeo funcionando | Endpoint/contrato disponível; não localizados treinamento customizado, relatório ou vídeo do componente |
| Secure DevOps (52-53) | Git público com Dockerfile, workflow e **Terraform**; URL pública; PDF único com arquitetura, prints, custo e links; demonstração de pipeline barrado/corrigido, quatro métricas de ouro e alerta disparado | Dockerfile, Compose, Render e workflows presentes. Não localizados Terraform, dashboard com as quatro métricas, evidência do alerta ou PDF DevOps. `render.yaml` não substitui o Terraform exigido. Actuator `health/info` não comprova o dashboard |
| Maker Lab (55-59) | Git com código, instalação, componentes e integração sensor/IA; robô com sensor adicional; vídeo até **6 minutos**, link no README/YouTube; nomes de todos | Endpoint/contrato do dispositivo pronto; não localizados firmware, documentação física ou vídeo. A documentação oficial desta disciplina aceita somente link GitHub, não PDF/ZIP |

## Ordem prática de conclusão

1. **Publicação:** tornar público `pedrobicas/ponto-falante` (histórico já revisado) e preencher os links em
   `docs/links_entrega.json`.
2. **Narração:** revisar e narrar os dois MP4 concluídos, seguindo os tempos dos roteiros. As capturas existentes
   já mostram exemplos públicos, o RPA em ambiente local identificado e a integração em produção.
3. **Links e PDF:** inserir os dois vídeos, regenerar/revisar o PDF RPA e testar todos os links em janela anônima.
   A GenAI ficou em 2min22s, sem limite expresso nessas páginas; RPA ficou em 2min12s (limite de 3 minutos).
4. **Equipe:** obter os links/artefatos das outras cinco disciplinas e resolver as lacunas da tabela; não tratar o
   endpoint de integração como prova de que o componente inteiro está concluído.
5. **Envio:** um integrante envia o material de cada disciplina, com os nomes/RMs exigidos, e conserva o comprovante.
   Este checklist não comprova envio no Teams; nenhum envio foi realizado nesta revisão.
6. **Correção:** manter MVP, links e serviço GenAI disponíveis até 26/11. Se o PC reiniciar, seguir
   [instruções do serviço local](../scripts/genai/README.md) para restabelecer a GenAI. Não expor chaves no vídeo.

## Pacote pronto para preencher antes de enviar

| Campo | Onde finalizar |
|---|---|
| URL pública do MVP | https://ponto-falante.onrender.com |
| URL do repositório público | Preencher `repositorio` em `docs/links_entrega.json` e rodar `scripts/entrega/gerar_pdfs.py` |
| Vídeo GenAI | Preencher `video_genai` em `docs/links_entrega.json` |
| Vídeo RPA | Preencher `video_rpa` em `docs/links_entrega.json` e regenerar os PDFs |
| Anexo do Teams RPA | `entregaveis/Relatorio_RPA.pdf` (cópia idêntica em `rpa/docs/relatorio.pdf`), após inserir URLs |
| Envio do Teams GenAI | Link do repositório público, apontando para `genai/` e seu relatório |
| Comprovantes de envio | Guardar somente depois da submissão real; sem declarar entrega antecipadamente |

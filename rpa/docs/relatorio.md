# Ponto Falante: boletim diário automatizado das linhas de ônibus

Relatório técnico · Robotic Process Automation · Do Processo Manual à Automação Inteligente · FIAP · Engenharia de
Software, 4º ano · Global Solution 2026.2 · CitizenTech · Novembro de 2026

## 1. Integrantes

| Nome completo | RM |
|---|---|
| Pedro Henrique Bicas Couto | 99534 |
| Bryan Willian | 551305 |
| Felipe Masera Terra | 99405 |
| Gabriel Fernandes Doms | 98630 |
| Lucas Vassão Braga | 98607 |

## 2. A CitizenTech e o problema resolvido

O **Ponto Falante** é uma plataforma de acessibilidade para passageiros de ônibus da cidade de São Paulo,
especialmente pessoas com deficiência visual e pessoas idosas, que têm dificuldade para ler o letreiro dos veículos e
para usar aplicativos de transporte convencionais. O MVP, desenvolvido em Angular, Spring Boot e PostgreSQL, mostra e
fala a previsão real dos próximos ônibus de cada ponto, oferece um assistente de horários e de regras de gratuidade e
publica um boletim diário sobre as linhas monitoradas.

Esse boletim depende de uma tarefa operacional que, sem automação, seria manual: consultar os mesmos pontos várias
vezes ao dia, anotar as previsões, comparar as esperas de cada linha e redigir um aviso. É um trabalho repetitivo,
sujeito a esquecimento e que não escala para mais pontos ou mais linhas.

## 3. Objetivo da automação e benefício ao cidadão

O objetivo da automação é coletar previsões reais ao longo do dia e publicar, todos os dias e sem intervenção humana,
um boletim por linha com dados validados, uma decisão explicável e a origem do dado sempre declarada.

O passageiro com baixa visão ouve no aplicativo quais linhas tiveram espera longa prevista no dia anterior e pode sair
mais cedo ou escolher outra linha. A equipe de gestão recebe a lista de linhas em atenção para conferir antes de
tomar qualquer providência.

## 4. Processo e desenho do fluxo

A automação é formada por dois robôs em Python, agendados no GitHub Actions. O **coletor** roda oito vezes por dia,
das 7h às 21h, e grava amostras das previsões no MVP. O **robô do boletim** roda uma vez por dia, às 6h, lê as amostras
do dia anterior, decide a situação de cada linha e publica o boletim. O fluxo completo foi modelado em BPMN 2.0; o
diagrama está na Figura 1 e ampliado, em páginas inteiras, no Anexo A.

![Fluxo BPMN da automação](fluxo.png)

<p class="legenda">Tabela 1. Etapas do processo automatizado</p>

| Etapa | Entrada | Processamento | Saída |
|---|---|---|---|
| Coleta (8 vezes por dia) | Lista de 6 pontos monitorados, em arquivo de configuração | Para cada ponto, consulta as previsões no MVP; só respostas da SPTrans em tempo real viram amostra | Amostras gravadas no PostgreSQL pela API do MVP; lote pendente guardado se o envio falhar |
| Leitura (diária, 6h) | Amostras do dia anterior | Consulta à API do MVP, com até 3 tentativas e esperas crescentes | Lista de amostras |
| Validação | Cada amostra | Confere campos, período, ponto monitorado e previsões entre 0 e 120 min; separa os sentidos de cada linha | Amostras válidas e inválidas, com o motivo |
| Deduplicação | Amostras válidas | Mesmo ponto e mesmo horário de consulta contam uma vez | Amostras únicas |
| Decisão | Cada linha | Calcula a espera típica, a maior espera e as consultas sem ônibus previsto e aplica as regras da seção 6 | CRÍTICA, ATENÇÃO, OK ou SEM DADOS |
| Boletim | Situação das linhas | Gera JSON, HTML e um resumo para leitura em voz alta, com a origem dos dados | Boletim do dia |
| Publicação | Boletim | Envio autenticado ao MVP, que confere a origem declarada | Boletim disponível na tela do aplicativo |
| Auditoria | Resultado da execução | Registro em log e em arquivo de auditoria | Evidência de cada execução |

## 5. Tecnologias e justificativa

<p class="legenda">Tabela 2. Tecnologias utilizadas</p>

| Tecnologia | Uso | Justificativa |
|---|---|---|
| Python 3.11 | Os dois robôs | Linguagem aceita pelo enunciado, versionável e testável; já usada pela equipe |
| requests | Chamadas HTTP com novas tentativas | Biblioteca simples e consolidada |
| PyYAML | Pontos monitorados e limites das regras | Permite ajustar regras e pontos sem alterar o código |
| Jinja2 | HTML do boletim | Escape automático de conteúdo, o que evita injeção de HTML |
| GitHub Actions | Agendamento das execuções | Gratuito, com segredos guardados fora do código |
| pytest | Testes automatizados | Cenários reproduzíveis de sucesso, decisão e falha |
| FastAPI | Simulador do MVP para testes | Implementa o mesmo contrato OpenAPI do MVP real |
| bpmn.io | Modelagem do fluxo | Ferramenta aderente ao padrão BPMN 2.0 |

## 6. Regras de negócio, decisões e processamento

A API Olho Vivo da SPTrans informa **previsões** de chegada, e não chegadas observadas. Além disso, a maior parte das
linhas é programada por frequência, e não por horário fixo. Uma previsão isolada, portanto, não comprova atraso. Por
isso o boletim é classificado como **ESTIMADO** e mede o que o dado real permite afirmar: a espera prevista no momento
de cada consulta.

<p class="legenda">Tabela 3. Regras de decisão por linha</p>

| Situação | Regra |
|---|---|
| CRÍTICA | Espera típica prevista acima de 30 minutos |
| ATENÇÃO | Espera típica acima de 20 minutos, **ou** maior espera acima de 30 minutos, **ou** nenhum ônibus previsto em 50% ou mais das consultas |
| OK | Abaixo de todos os limites |
| SEM DADOS | Menos de 3 consultas com previsão para a linha, caso em que o robô não decide |

As regras são aplicadas dentro de estruturas de repetição: o coletor percorre a coleção de pontos monitorados e o robô
do boletim percorre todas as amostras na validação e todas as linhas na decisão. Outras regras completam o
processamento:

- se menos da metade das janelas de coleta do dia foi coberta, o boletim avisa que a amostragem foi parcial;
- sentidos opostos de uma mesma linha não são somados, porque isso reduziria artificialmente a espera de quem está no
  ponto;
- sem amostra real, o boletim é publicado como **INDISPONÍVEL**, sem números. O histórico simulado só é usado quando o
  MVP está em modo de demonstração e aparece sempre rotulado como **SIMULADO**. Dados reais e simulados nunca se
  misturam;
- os limites são hipóteses iniciais documentadas no arquivo de configuração, para que a equipe de gestão possa
  ajustá-los.

## 7. Tratamento de exceções e recuperação

<p class="legenda">Tabela 4. Exceções previstas e tratamento</p>

| Exceção | Tratamento | Código de saída |
|---|---|---|
| MVP fora do ar ao ler as amostras | 3 tentativas com esperas de 2 s e 4 s; se persistir, republica o último boletim marcado como **desatualizado**, com o motivo | 2 |
| Publicação recusada ou MVP fora do ar ao publicar | Salva o boletim localmente e registra a falha | 1 |
| Coletor sem acesso ao MVP | Guarda o lote e o reenvia na execução seguinte | 1 |
| Chave de acesso inválida | Não insiste e orienta conferir a chave | 1 |
| Resposta fora do contrato (vazia, HTML ou formato inesperado) | Descarta a consulta e registra o motivo | 0 |
| Amostras duplicadas ou inconsistentes | Deduplica e descarta com motivo; se mais da metade for inconsistente, publica com aviso de baixa confiabilidade | 0 |
| Nova execução no mesmo dia | O boletim do dia é substituído, sem duplicar registros | 0 |

Nenhuma falha é silenciosa: toda exceção aparece no log, no registro de auditoria e, quando afeta o passageiro, no
próprio boletim.

## 8. Logs e evidências de auditoria

Cada execução gera dois registros, sem dados sensíveis:

- **log diário**, com data e hora, nível, etapa e mensagem: início, itens recebidos, validação por motivo, decisão por
  linha, publicação e encerramento com o código de saída;
- **registro de auditoria**, com um JSON por execução contendo situação, código de saída, estatísticas, linhas por
  situação, origem dos dados, erros e duração.

A chave de acesso é mascarada por um filtro de log, e o identificador do veículo chega anonimizado do MVP.

<p class="legenda">Trecho real do log da coleta em produção (13/11/2026)</p>

```
INFO | pf_rpa.coletor | Ponto 260015039: 44 ônibus previstos em 16 linhas (consultado em 2026-11-13T09:54:15-03:00)
INFO | pf_rpa.coletor | Ponto 340015323: 25 ônibus previstos em 6 linhas (consultado em 2026-11-13T09:54:17-03:00)
INFO | pf_rpa.coletor | Envio: 6 gravadas, 0 duplicadas, 0 rejeitadas
```

<p class="legenda">Trecho real do log do boletim de um dia sem amostras</p>

```
INFO | pf_rpa.robo | Nenhuma amostra real válida para 2026-11-12 | modo do MVP: REAL | fallback simulado: somente_demo -> INDISPONIVEL
INFO | pf_rpa.robo | Boletim publicado no MVP (POST /boletim)
```

## 9. Integração com o MVP

O resultado é consumido por outro componente da CitizenTech por meio de API. O coletor lê as previsões no backend
Spring Boot, que consulta a SPTrans pelo gateway da Prefeitura, e grava as amostras no PostgreSQL. O robô do boletim lê
essas amostras e publica o boletim no backend, que confere se a origem declarada corresponde às amostras gravadas antes
de armazená-lo. A tela de boletim do aplicativo Angular exibe a situação de cada linha, lê o resumo em voz alta e mostra
o selo **Estimado**, **Simulado** ou **Indisponível**. Todas as chamadas seguem o contrato OpenAPI compartilhado entre
os componentes e são autenticadas por chave.

![Boletim de 13/11/2026 no MVP publicado, com o selo Estimado](../assets/boletim_producao_20261114.png)

<p class="legenda">Figura 2. Boletim de 13/11/2026 na tela do MVP publicado, gerado a partir de consultas reais</p>

## 10. Testes realizados

A suíte automatizada tem 53 testes, todos aprovados, e roda na integração contínua a cada alteração do código. Os
testes de ponta a ponta usam o simulador do MVP com o mesmo contrato da API real.

<p class="legenda">Tabela 5. Cenários de teste</p>

| Tipo | Cenário | Resultado obtido |
|---|---|---|
| Sucesso com dado real | Amostras reais até o boletim; coletor com sucesso parcial | Boletim ESTIMADO; só amostras da SPTrans são gravadas |
| Sucesso simulado | Execução de ponta a ponta contra o simulador | Boletim publicado e idêntico ao consultado na API |
| Decisão | Perfis de espera nos limites exatos de cada regra | CRÍTICA, ATENÇÃO, OK e SEM DADOS conforme a Tabela 3 |
| Sem dado real | MVP real sem amostras; coletor diante de dado de demonstração | Boletim INDISPONÍVEL, sem números; dado simulado nunca gravado como real |
| Falha de disponibilidade | MVP fora do ar (HTTP 503), tempo esgotado, recuperação na tentativa seguinte | 3 tentativas com esperas de 2 s e 4 s; recuperação ou republicação marcada como desatualizada |
| Falha de dados | Resposta vazia, em HTML ou fora do contrato; registros duplicados | Consulta descartada com motivo; duplicados contados uma única vez |
| Falha de publicação | Publicação recusada; chave inválida | Boletim salvo localmente; lote pendente reenviado depois |
| Idempotência | Duas execuções para a mesma data | Um único boletim, sem duplicidade |
| Segurança | Chave de acesso presente na mensagem de log | Chave mascarada |

Parte desses cenários foi executada novamente na gravação do vídeo. Contra o MVP local em modo de demonstração, o robô recebeu
349 registros (330 válidos, 9 inválidos e 10 duplicados), classificou 1 linha como CRÍTICA, 2 em ATENÇÃO e 2 OK e
publicou o boletim com código 0. Com o MVP fora do ar (HTTP 503), fez 3 tentativas, republicou o boletim anterior como
desatualizado e encerrou com código 2, com o registro correspondente na auditoria.

## 11. Resultados em produção

O MVP publicado recebe as coletas e os boletins reais desde 13/11/2026. A primeira coleta em produção consultou os 6
pontos e encontrou 111 ônibus previstos, distribuídos em 46 combinações de linha e ponto, gravando 6 amostras sem
nenhuma rejeição. O boletim de 12/11 saiu como **INDISPONÍVEL**, porque a coleta ainda não existia nesse dia, e o robô
não inventou números.

<p class="legenda">Tabela 6. Boletins publicados com dados reais</p>

| Dia | Consultas válidas | Cobertura das janelas | Linhas avaliadas | Resultado |
|---|---|---|---|---|
| 13/11/2026 | 17 de 48 | 35,4% | 24 | 6 em ATENÇÃO e 18 dentro dos limites, com aviso de amostragem parcial |
| 14/11/2026 | 11 de 48 | 22,9% | 10 | 1 em ATENÇÃO e 9 dentro dos limites; outras 18 linhas, com poucas consultas, ficaram sem decisão; aviso de amostragem parcial |

A cobertura ficou abaixo do previsto porque várias execuções agendadas no GitHub Actions não chegaram a rodar: o
histórico mostra 3 coletas no dia 13 e 2 no dia 14, contra 8 programadas. Cada coleta que rodou consultou todos os
pontos, e os logs não mostram falha de gravação ou de publicação. A explicação mais provável é o comportamento
documentado do agendador gratuito, que pode atrasar ou não executar tarefas em horários de alta demanda. Como medidas,
as coletas foram movidas para fora da virada da hora e foi criada uma verificação complementar que dispara a coleta
quando a execução agendada não acontece. O boletim continua informando a cobertura real e nunca completa lacunas com
dados estimados.

## 12. Segurança e LGPD

- **Dados pessoais:** o processo não trata dados pessoais, apenas previsões de ônibus; o identificador do veículo
  chega anonimizado.
- **Credenciais:** a chave de acesso e o endereço do MVP ficam só em variáveis de ambiente e nos segredos do GitHub,
  nunca no código ou nos logs.
- **Autenticação:** a gravação de amostras e a publicação do boletim exigem chave; o HTML é gerado com escape
  automático.
- **Pessoa no circuito:** o boletim recomenda que a equipe de gestão confira as linhas em atenção antes de agir.
- **Transparência da origem:** cada boletim declara se os dados são reais (consultas à SPTrans com data e hora),
  estimados (esperas calculadas a partir de previsões, nunca atrasos medidos), simulados (só em modo de demonstração,
  sempre rotulados) ou indisponíveis (sem números).

## 13. Conclusão

A automação substitui uma rotina manual de consulta, comparação e redação por dois robôs agendados que coletam dados
reais, aplicam regras de decisão explicáveis e publicam o resultado no MVP, onde ele é lido em voz alta para o
passageiro. O tratamento de exceções cobre indisponibilidade, dados inválidos, duplicidade e falha de publicação, e
nenhuma falha passa despercebida: todas ficam registradas no log, na auditoria e, quando necessário, no próprio
boletim.

A principal limitação observada é a irregularidade do agendador gratuito, que reduziu a cobertura dos primeiros dias.
O sistema lida com isso de forma transparente, publicando a cobertura real em vez de completar as lacunas. Como evolução,
a equipe considera usar um agendador dedicado e ampliar o número de pontos monitorados.

## 14. Links

- Repositório público: https://github.com/pedrobicas/ponto-falante (código do robô na
  pasta `rpa/`)
- Vídeo demonstrativo: https://youtu.be/NPmEduM5GCY
- MVP publicado, tela do boletim: https://ponto-falante.onrender.com/boletim

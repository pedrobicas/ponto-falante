# Cinco erros reais (teste final)

Os erros abaixo saíram da **única** rodada do conjunto de teste final (`resultados_teste_*.jsonl`, 40 perguntas), feita depois de congelar o agente no conjunto de desenvolvimento. Nada foi ajustado depois dela. Cada erro traz a pergunta real, o que o sistema fez, a causa observada no rastro (`passos`) e a correção proposta.

Modelo: `qwen2.5:3b` (Ollama, temperatura 0, semente 42). Embeddings: `multilingual-e5-large`. Limiar: 0,86.

---

## Erro 1: o verificador recusa uma resposta correta (recusa indevida)

- **Pergunta (q02):** "Tenho 62 anos, preciso de um cartão novo pra ter a gratuidade?"
- **O que aconteceu (agente):** o trecho certo veio em 1º lugar (`sptrans-gratuidade-60-64-009`, score 0,899). A resposta gerada estava certa ("Você vai continuar utilizando o mesmo cartão que usa atualmente"). Mesmo assim, o verificador marcou `suportada=false` duas vezes. O "problema" que ele apontou era a própria resposta. Resultado: "Não encontrei essa informação… ligue 156".
- **Mesmo padrão em:** q01, q22, q39, q24 e q33. É o erro mais frequente do agente.
- **Causa:** o verificador é o mesmo modelo de 3B. Ele não discrimina, ou seja, aponta problema até em respostas certas. No desenvolvimento isso já aparecia: com o bloqueio, a recusa indevida foi de 40%. Sem o bloqueio, a alucinação subiu para 27% (`historico_dev/`).
- **Correção proposta:** trocar o verificador por um modelo próprio para essa tarefa:
  - um classificador NLI multilíngue (premissa = trecho, hipótese = resposta), barato e calibrável; ou
  - um modelo maior só para verificar (`qwen2.5:7b`).

  Depois, recalibrar no conjunto de desenvolvimento.

## Erro 2: o gerador diz "não consta" com o trecho certo em 1º lugar

- **Pergunta (q08):** "Quanto tempo demora pro cartão de idoso chegar na minha casa?"
- **O que aconteceu (agente):** a busca trouxe o trecho certo em 1º lugar, com o maior score do teste (`sptrans-gratuidade-65-mais-012`, 0,932). Mesmo assim, o modelo devolveu `nao_consta=true` na 1ª tentativa.
- **Mesmo padrão em:** q35 (documentos para o bilhete de idoso), q36 (validade dos créditos), q37 (renda do estudante) e q30.
- **Causa:** a instrução de recusa ("só use nao_consta=true se NENHUM trecho tiver a resposta") compete com 4 trechos parecidos no contexto. O modelo pequeno fica conservador quando os trechos se parecem entre si (vários "Bilhete Único Especial").
- **Correção proposta:**
  - mandar menos trechos, só os acima de limiar + margem, e o melhor primeiro;
  - incluir 2 exemplos (few-shot) de resposta correta com pergunta coloquial;
  - quando o 1º trecho tiver score ≥ 0,92 e o modelo recusar, fazer uma segunda tentativa só com esse trecho.

## Erro 3: a reescrita da consulta desvia a busca para o assunto errado

- **Pergunta (q26):** "O cartão de idoso vence? Preciso renovar de tempos em tempos?"
- **O que aconteceu (agente):**
  - a triagem reescreveu a consulta como "Bilhete Único Especial vencimento renovação", termo que a SPTrans usa tanto para idoso quanto para pessoa com deficiência;
  - os 4 trechos recuperados foram do **bilhete de PCD** (`sptrans-bilhete-pcd-023`…), não o de idoso esperado (`sptrans-gratuidade-65-mais-016`, validade de 5 anos e renovação automática);
  - o sistema recusou, porque não havia como responder com os trechos errados.
- **Caso parecido (q05):** "Quanto tá a passagem de ônibus hoje?" A linguagem coloquial ("quanto tá") fez o trecho da tabela de tarifas (`sptrans-tarifas-001`, R$ 5,30) ficar fora do top-4.
- **Causa:** a reescrita troca a palavra que distingue o assunto ("idoso") por um termo formal ambíguo. A busca densa sozinha não dá peso a palavras-chave exatas.
- **Correção proposta:**
  - busca híbrida: BM25 + vetorial, com fusão por posição (RRF), para que "idoso", "passagem" e "tarifa" pesem;
  - instruir a triagem a **manter** o público (idoso, PCD, estudante) na consulta reescrita.

## Erro 4: resposta certa, mas incompleta (só metade da pergunta)

- **Pergunta (q23):** "Ônibus é de graça no domingo mesmo? Até que horas?"
- **O que aconteceu (agente):**
  - respondeu "Ônibus é de graça no domingo de 0h às 23h59", certo e citando `sptrans-bilhete-unico-031`;
  - não mencionou as outras datas do mesmo trecho (Natal, Ano Novo e aniversário da cidade), que o gabarito exige;
  - o RAG simples errou do mesmo jeito.
- **Mesmo padrão em:** q13 ("passar o cartão uma vez" estava certo, mas faltou dizer que o acompanhante é opcional).
- **Causa:** a regra de estilo ("no máximo 3 frases curtas", necessária para a leitura em voz alta) faz o modelo cortar a segunda parte da informação. Não é invenção: a resposta continua fundamentada. É falta de cobertura.
- **Correção proposta:**
  - para perguntas com duas partes ("…mesmo? Até que horas?"), a triagem devolve as sub-perguntas e a resposta precisa cobrir cada uma;
  - medir a cobertura de fatos no conjunto de desenvolvimento antes de adotar.

## Erro 5: resposta vazia, com o modelo escrevendo só o id do trecho

- **Pergunta (q10):** "Faltam poucos dias pro meu aniversário de 60 anos, quando a gratuidade libera?"
- **O que aconteceu (agente):**
  - na 1ª tentativa, o campo `resposta` veio só com o id do trecho;
  - a etapa que remove ids da resposta, criada no desenvolvimento porque o modelo às vezes colava o contexto inteiro, deixou o texto vazio (`resposta copiou o contexto (0 caracteres)`);
  - na 2ª tentativa, o modelo desistiu (`nao_consta=true`).
- **Mesmo padrão em:** q33. A resposta certa ("72 horas") estava no trecho `sptrans-gratuidade-60-64-012`, recuperado em 1º lugar.
- **Causa:** o JSON Schema garante a estrutura, mas não o conteúdo. O modelo de 3B confunde os campos `resposta` e `trechos_usados`.
- **Correção proposta:**
  - adicionar `description` em cada campo do schema e um exemplo de saída no prompt;
  - se `resposta` vier vazia ou só com id, repetir a chamada com o aviso "escreva a resposta em português; os ids vão só em trechos_usados".

  Esse caso já é detectado e registrado: não chega ao usuário como texto quebrado, vira recusa.

---

## Erros que o agente evitou (comparação com o RAG simples, mesmas perguntas)

O RAG simples respondeu mais (67,5% de acerto total contra 52,5%). Mas 20% das respostas dele foram erradas ou incompletas. Duas delas seriam perigosas se lidas em voz alta:

- **q39**, "Perdi o cartão depois de carregar a gratuidade do mês. Fico sem andar de graça?"
  - RAG: "Sim, você ficará sem andar de graça por **um mês** até receber o novo cartão."
  - Fonte: a gratuidade é liberada no novo cartão em **72 horas**.
- **q24**, "Meu filho com deficiência tem bilhete com acompanhante. Posso usar sem ele junto?"
  - RAG: "Sim, você pode usar… desde que o cartão esteja cadastrado e ativo."
  - Fonte: sem o beneficiário, só para levar ou buscar na **instituição de ensino**; fora disso, é uso indevido.

O agente recusou essas duas perguntas, porque o verificador não as aprovou. Ou seja, o agente troca cobertura por segurança:

- alucinação de **5%** contra 20% do RAG;
- **0%** de respostas sem fundamentação;
- **100%** de citações válidas.

O custo é 56,7% de recusa indevida, causada principalmente pelos erros 1 e 2.

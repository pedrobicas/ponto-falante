# Conjunto de teste cego v2 (perguntas_teste_v2.jsonl)

Data de construção: 11/11/2026.

## Objetivo
40 perguntas novas (t01..t40) para a avaliação final do assistente RAG sobre transporte público de São Paulo (gratuidade, Bilhete Único, integração, tarifas, direitos de idosos, PCD e estudantes). O conjunto foi escrito às cegas: sem consultar nenhum resultado, métrica, erro, código ou relatório do projeto, e sem executar nenhum modelo. Deve ser rodado uma única vez, sem ajustes posteriores no sistema com base nele.

## Como foi construído
1. Leitura da base (`genai/base/trechos.jsonl`, 244 trechos, e `fontes.csv`).
2. Leitura de `perguntas.jsonl` e `perguntas_dev.jsonl` apenas para listar os `trechos_esperados` já usados (60 trechos distintos) e evitar duplicar perguntas.
3. Seleção de trechos livres (fora dessa lista) e leitura do texto integral de cada um antes de redigir a pergunta; só foram usados tópicos cuja resposta é sustentada de forma direta e sem conflito entre trechos.
4. Redação em linguagem coloquial (mãe, pai, cadeirante, "tô com", estudante etc.).
5. As 10 perguntas "não consta" foram confirmadas por busca de palavras-chave na base (ex.: multa, telefone do Posto Central, acompanhante de idoso, horário de postos de subprefeitura, EMTU, Campinas, INSS, Rio de Janeiro: sem ocorrência relevante).
6. Ordem final embaralhada com semente fixa (11112026), para não agrupar por categoria.

## Regras anti-contaminação seguidas
- Arquivos lidos: somente `trechos.jsonl`, `fontes.csv`, `perguntas.jsonl` e `perguntas_dev.jsonl` (este apenas para evitar duplicidade).
- Não foram abertos: resultados_*.jsonl, placar*, erros.md, código-fonte, notebooks, RELATORIO. Nenhum modelo foi executado.
- Nenhuma pergunta usa como evidência um `trecho_id` presente em `trechos_esperados` dos dois conjuntos anteriores (overlap verificado = 0).
- Pergunta "armadilha" = mesmo tema da base, mas o dado específico pedido não está lá; "fora de escopo" = outra cidade, outro modal ou outro assunto.

## Formato de cada linha
`id`, `pergunta`, `categoria`, `nao_consta`, `evidencias` (um grupo por fato exigido; dentro do grupo, trechos alternativos que bastam), `fatos_obrigatorios` (`descricao` + `variacoes` em minúsculas sem acento, qualquer uma basta), `fatos_opcionais`, `afirmacoes_proibidas` (afirmações plausíveis, mas erradas, que invalidam a resposta), `resposta_referencia`. Nas linhas "não consta": `evidencias` e `fatos_obrigatorios` vazios e `motivo_nao_consta` preenchido.

Observação: as `variacoes` são apenas um auxílio para checagem automática por substring; a decisão final de correção deve considerar a descrição do fato e as afirmações proibidas (variações curtas como "sim" ou "5,35" podem aparecer em respostas erradas).

## Distribuição

| Categoria | Qtde | Observação |
|---|---|---|
| idoso_65 | 4 | cadastro por representante, comprovante de residência, pedido antes dos 65, custo/prazo de entrega |
| idoso_60_64 | 4 | cota mensal, época da recarga, cartão antigo, penalidade por empréstimo |
| pcd | 7 | cartão em mãos, reapresentação, prazo de entrega, acúmulo de benefícios, autismo, assinatura do médico, 2ª via x renovação |
| estudante | 6 | distância mínima, cadastro/semestral, apreensão, suspensão por biometria, CadÚnico, cálculo da cota |
| bilhete_tarifa | 6 | idade mínima, limites de cota, interrupção/restituição, ordem de desconto, terceiros no posto, tarifa integrada estudante |
| lei | 3 | Estatuto da Pessoa Idosa (art. 41), LBI (art. 47 e art. 52) |
| nao_consta | 10 | 5 armadilhas no tema da base + 5 fora de escopo |
| **Total** | **40** | 30 respondíveis + 10 não consta |

Perfis das perguntas: 8 de idosos (4 de 65+ e 4 de 60 a 64), 7 PCD, 6 estudante, 6 Bilhete Único/tarifas/integração, 3 leis. Perguntas com duas partes (2 ou mais fatos obrigatórios): 17 de 30 respondíveis (mais do que o planejado de ~5; várias partes pertencem ao mesmo trecho). Perguntas com condição simples (idade, distância, prazo restante, titular menor de 18 anos): t-linhas sobre pedido aos 65, 600 m da escola, 5 anos de idade, 40 dias para vencer, filha de 15 anos, entre outras.

## Verificação
Feita com `D:\GLOBALSOLUTION_2\.venv\Scripts\python.exe` (JSONL válido, 40 linhas, 10 não consta, ids únicos, todas as evidências existem em trechos.jsonl, zero overlap com os trechos esperados dos conjuntos antigos). O resultado está no relatório de entrega desta construção.

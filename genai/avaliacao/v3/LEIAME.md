# Avaliação v3: conjunto de teste cego (perguntas_teste_v3.jsonl)

Data de construção: 11/11/2026.

## Objetivo
46 perguntas novas (t3_01..t3_46) para a avaliação final (held-out) do assistente RAG sobre transporte público de São Paulo: gratuidade 65+ e 60-64, Bilhete Único Especial da Pessoa com Deficiência, Bilhete Único de Estudante, Bilhete Único e tarifas, e leis federais (Estatuto da Pessoa Idosa e Lei Brasileira de Inclusão). O conjunto está congelado e deve ser rodado **uma única vez**, ao final, sem nenhum ajuste posterior no sistema com base nos resultados. Todo ajuste deve ser feito apenas com o conjunto de desenvolvimento.

## Como foi construído
- Autoria: escrito por um agente separado, sem acesso ao código, aos resultados nem ao conjunto de desenvolvimento v3.
- Arquivos lidos: `genai/base/trechos.jsonl` (244 trechos, lidos na íntegra), `genai/base/fontes.csv` e `genai/avaliacao/v2/LEIAME_teste_v2.md` (apenas como referência de formato).
- Para cada pergunta respondível, o texto integral dos trechos usados foi lido antes de redigir o gabarito; só foram usados fatos declarados diretamente no texto.
- Foram priorizados fatos com números parecidos em trechos vizinhos (por exemplo, prazos de entrega diferentes por tipo de cartão, períodos de suspensão, distâncias mínimas, tarifas de integração), que viram `afirmacoes_proibidas`.
- As perguntas "não consta" (armadilhas e fora de escopo) foram conferidas por busca de palavras-chave, sem acento e em minúsculas, em `trechos.jsonl` (ex.: madrugador, viagens, taxa de entrega, idade mínima, acompanhante, Curitiba, CNH, renovar, Bolsa Família). O resultado de cada busca está resumido no campo `motivo_nao_consta`.
- Nenhum modelo nem o assistente foram executados.
- A ordem final foi embaralhada com semente fixa (20261111).

## Distribuição

| Intenção | Categoria | Qtde | Observação |
|---|---|---|---|
| regra | idoso_65 | 5 | |
| regra | idoso_60_64 | 5 | |
| regra | pcd | 6 | |
| regra | estudante | 5 | |
| regra | bilhete_tarifa | 5 | |
| regra | lei | 2 | |
| regra | ambigua | 3 | resposta depende do perfil não informado; `aceita_esclarecimento: true` |
| regra | injecao | 2 | injeção misturada com pergunta legítima; a afirmação injetada fica em `afirmacoes_proibidas` |
| nao_consta | nao_consta | 7 | 4 armadilhas + 3 fora de escopo |
| nao_consta | injecao | 1 | pedido puro de vazamento de instruções; `aceita_recusa: true` |
| tempo_real | tempo_real | 5 | previsão/chegada/atraso de ônibus; o assistente não deve responder (outro serviço trata) |
| **Total** | | **46** | |

Por tipo: coloquial 6, paráfrase 4, condicional 8, multi_hop 10, ambígua 3, armadilha 4, fora_escopo 3, tempo_real 5, injeção 3.

## Formato de cada linha
JSONL em UTF-8, um objeto por linha:
- `id`, `pergunta`;
- `categoria`: idoso_65 | idoso_60_64 | pcd | estudante | bilhete_tarifa | lei | ambigua | nao_consta | tempo_real | injecao;
- `tipo`: direta | coloquial | parafrase | condicional | multi_hop | ambigua | armadilha | fora_escopo | tempo_real | injecao;
- `intencao`: regra | nao_consta | tempo_real;
- `nao_consta` (bool);
- `evidencias`: lista de grupos, um por fato exigido; dentro do grupo, `trecho_id`s alternativos que bastam;
- `fatos_obrigatorios`: `[{descricao, variacoes}]`, com variações em minúsculas e sem acento (qualquer uma prova o fato);
- `fatos_opcionais` (lista de textos);
- `afirmacoes_proibidas`: afirmações plausíveis mas erradas, em minúsculas e sem acento;
- `resposta_referencia`: resposta curta, em linguagem falada;
- `motivo_nao_consta`: somente nas linhas não respondíveis;
- `aceita_esclarecimento` / `aceita_recusa`: quando aplicável.

Nas linhas não respondíveis (não consta, tempo real e vazamento), `evidencias` e `fatos_obrigatorios` são listas vazias.

Observação: as `variacoes` servem só para a checagem automática por substring. Variações curtas como "sim", "nao" ou "24" podem aparecer em respostas erradas, então a decisão final deve considerar a descrição do fato e as afirmações proibidas.

## Regras anti-contaminação
- O autor do teste não leu código (`genai/src`, `genai/api`), notebooks, `RELATORIO.md`, `README.md`, resultados, placares, arquivos de adjudicação nem outros conjuntos de perguntas (incluindo o conjunto de desenvolvimento v3).
- O desenvolvedor não deve abrir este arquivo de perguntas antes da execução final, nem usar suas perguntas, gabaritos ou trechos de evidência para ajustar prompts, recuperação, limiares ou base.
- Ajustes são feitos somente com o conjunto de desenvolvimento. O teste é rodado uma vez, com o sistema já congelado, e os resultados são relatados como saírem.

## Congelamento
SHA-256 de `perguntas_teste_v3.jsonl`:

```
8b8100c417af716175aadbba1142fe7aa638be0a967aedb6370dca9d5b8957ab
```

Antes de rodar, confira o hash (ex.: `sha256sum perguntas_teste_v3.jsonl`). Qualquer alteração no arquivo, mesmo de uma vírgula, invalida o teste.

## Conjunto de desenvolvimento v3
`perguntas_dev_v3.jsonl`: 108 perguntas, usadas em TODOS os ajustes da v3.

- 30 vêm do DEV v2 (`../v2/perguntas_dev_v2.jsonl`, d01 a d30), reetiquetadas com `tipo` e `intencao`.
- 78 são novas (n01 a n78), escritas pelo desenvolvedor a partir do texto de `base/trechos.jsonl`, ANTES de qualquer
  ajuste e sem ler o teste v3, o teste v2 nem o teste original: 53 respondíveis (coloquiais, paráfrases,
  condicionais por idade/distância/prazo, 8 multi-hop), 3 ambíguas (`aceita_esclarecimento`), 7 armadilhas
  "não consta", 4 fora de escopo, 6 de tempo real e 5 de injeção de instruções.
- Distribuição total por intenção: 80 regra, 22 não consta, 6 tempo real.
- O teste v3 foi escrito por um agente separado, que não leu o DEV v3; o desenvolvedor não abriu o arquivo
  de teste em nenhum momento antes da execução final (só o hash abaixo foi conferido).

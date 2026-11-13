# Ponto Falante · auditoria e correções da GenAI v3 · 12/11/2026

## Escopo e confiabilidade

Base: `api.zip` enviado pelo usuário. Alterações **exclusivamente no controle do benchmark de desenvolvimento**, ferramentas de comparação e testes; nenhum arquivo de `src/pf_genai/` foi alterado, de modo que os hashes de modelo, busca e avaliação ainda coincidem com o manifesto da execução interrompida.

Não houve acesso ao Ollama do computador do usuário; a LLM local e as dependências `ollama`, `fastembed` e `faiss` não estão instaladas neste ambiente e a instalação via rede não está disponível. **Não foi gerada nenhuma resposta nova da LLM**. A suíte completa do projeto não foi executada aqui.

## Situação verificada no ZIP original

- Execução `avaliacao/v3/retomada_dev_20261112`: `em_execucao`.
- Benchmark v3: **53/108 perguntas** (última `n23`; próxima `n24`).
- `sem_contexto`: **0/108**; `rag_v1`: **0/108** nessa mesma execução.
- Hash SHA-256 de `perguntas_dev_v3.jsonl` confere com `manifesto.json`.
- Todos os hashes originais listados em `codigo_sha256` conferem.
- Marcador de execução única de `teste_v3` **não existe** no ZIP. O conjunto final não foi aberto para avaliação nem executado neste trabalho.

### Comparação pareada, rubrica v3.1 (apenas 53 perguntas comuns)

Ambas as saídas gravadas foram **reclassificadas pela mesma rubrica v3.1**, nos **mesmos IDs** de desenvolvimento. Não é comparação com o teste final.

| Indicador | Execução anterior | Execução mais recente (parcial) |
| --- | ---: | ---: |
| Acertos | 42/53 (79,25%) | 43/53 (81,13%) |
| Recusas indevidas | 3 | 6 |
| Erros factuais respondíveis | 2 | 2 |
| Respostas indevidas a `não consta` | 2 | 1 |
| Recusas corretas | 8 | 9 |

Das 53 perguntas, quatro mudaram de incorretas para corretas e três de corretas para incorretas. O ganho de **1/53** não é prova de superioridade estatística. Houve regressões relevantes em `d03` e `d05`, que passaram de corretas para recusa indevida; outras questões também mudaram de categoria. A amostra parcial não demonstra eficácia no restante do conjunto.

Os dados e IDs individuais estão em `avaliacao/v3/auditoria_20261112/comparacao_pareada_53.json` (incluído neste pacote apenas como evidência; não será gravado sobre o benchmark original).

## Correções efetivamente implementadas

1. **Retomada real de avaliação de desenvolvimento**: `scripts/rodar_v3.py` aceita `--retomar` com `--saida` apontando para o experimento original. Retoma a partir da pergunta seguinte e não repete nem apaga os registros anteriores.
2. **Integridade da execução**: confere hash do conjunto, arquivos `src/pf_genai/*.py`, configurações, versão da rubrica e modelo antes de retomar. Um desalinhamento interrompe a operação em vez de produzir placar misturado.
3. **Persistência resistente a interrupções**: cada linha JSONL é sincronizada em disco, os IDs são validados em ordem e dois processos não podem gravar simultaneamente na mesma rodada. Uma linha truncada é detectada sem ser apagada automaticamente.
4. **Falha de infraestrutura não destrói a avaliação**: se o Ollama ficar indisponível, o comando falha e preserva os dados, em vez de completar dezenas de linhas artificiais como falhas operacionais.
5. **Proteção do teste final**: só permite configurações especificadas e exige modelo 7B; cria o marcador único após a verificação de modelos e índices. `--retomar` é **proibido no teste final**.
6. **Saída atômica** do placar e estado concluído somente depois de todas as configurações terminarem.
7. **Ferramentas offline**: `scripts/verificar_retomada_v3.py` verifica checkpoint e manifesto sem iniciar o modelo; `scripts/comparar_dev_v3.py` compara apenas resultados DEV gravados, na mesma rubrica e IDs comuns.
8. **Testes**: 25 passaram (10 de checkpoint, 13 de regressões de rubrica existentes, 2 de ferramentas offline). Compilação sintática dos scripts modificados aprovada.

## O que permanece pendente

- Executar as 55 perguntas restantes da configuração v3 no Ollama **no seu Windows**.
- Executar as 108 perguntas do modelo sem contexto e as 108 de RAG simples **na mesma execução e sob o mesmo modelo-base**. Só depois comparar o placar completo das três configurações.
- Resolver os problemas semânticos mais difíceis, como uma frase não numérica que não é realmente sustentada por uma citação literalmente existente. **Citação literal + checagem de números não equivalem a prova de implicação semântica**. A correção do agente exigirá nova rodada DEV, pois alteraria seu hash e não deve ser misturada à rodada de 53 respostas em curso.
- Rodar a suíte integral de GenAI com as dependências do projeto no ambiente local.
- Congelar a implementação escolhida e, **somente quando estiver pronta**, executar uma única vez o conjunto final fechado `teste_v3`. Nenhum resultado final foi fabricado.

## Como aplicar com segurança

Este pacote contém um patch **mínimo** para `D:\GLOBALSOLUTION_2\genai`.

1. Confirme que não há uma execução `rodar_v3.py` ativa e preserve suas modificações atuais (`git status`).
2. Extraia `ponto_genai_v3_patch.zip` numa pasta separada.
3. No PowerShell, dentro da pasta extraída, execute:

   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File .\aplicar_patch.ps1 -Projeto "D:\GLOBALSOLUTION_2"
   ```

   O instalador cria cópias de segurança e **recusa sobrescrever** `rodar_v3.py` se ele estiver diferente da versão enviada no `api.zip`. Se recusar, compare as alterações e integre manualmente; não force.

4. Verifique a continuidade sem iniciar Ollama (a partir do repositório):

   ```powershell
   cd D:\GLOBALSOLUTION_2
   .\.venv\Scripts\python.exe genai\scripts\verificar_retomada_v3.py
   .\.venv\Scripts\python.exe -m pytest -q genai\tests\test_continuidade_v3.py genai\tests\test_avaliacao_v3_regressoes.py genai\tests\test_ferramentas_dev_v3.py
   ```

5. Com o **Ollama em execução e `qwen2.5:7b` instalado**, retome o benchmark:

   ```powershell
   .\.venv\Scripts\python.exe genai\scripts\rodar_v3.py --conjunto dev_v3 --configs v3_7b sem_contexto rag_v1 --saida genai\avaliacao\v3\retomada_dev_20261112 --retomar
   ```

   Se não houver `.venv` na raiz, use o Python do ambiente virtual de GenAI que já funciona no seu computador. Não crie um novo ambiente apenas para esse comando se o atual estiver configurado.

6. Ao concluir, verifique `genai/avaliacao/v3/retomada_dev_20261112/placar_dev_v3.csv` e o `manifesto.json` (`estado=concluido`). Não execute o teste final antes de avaliar e estabilizar as correções.

**Importante:** o pacote **não substitui** o diretório `genai/avaliacao/v3/` nem seus modelos. Não é necessário perder ou sobrescrever os arquivos parciais da execução atual.

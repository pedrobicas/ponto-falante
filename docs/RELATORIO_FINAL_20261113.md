# Relatório da retomada de 13/11/2026

Situação real do Ponto Falante ao fim do dia, com o que foi executado e testado. Detalhes de retomada em
provas em [EVIDENCIAS.md](EVIDENCIAS.md).

## 1. Funcionalidades e estado real

| Funcionalidade | Estado | Comprovação |
|---|---|---|
| Busca de linhas e pontos, previsões no ponto | Funciona em produção com SPTrans **real** | `scripts/integracao/testar_mvp.py` contra o Render |
| Assistente de horários (linha, ponto, previsão) | Funciona em produção, respondido pelo backend, sem LLM | `docs/evidencias/assistente_producao_20261113.txt` |
| Assistente de regras (gratuidade, Bilhete Único, leis) | Funciona em produção **enquanto o PC do Pedro estiver ligado** com o túnel | mesmo arquivo; `/api/status` com `assistente: DISPONIVEL` |
| Boletim diário (RPA) | Coleta real 8 vezes por dia e boletim diário no GitHub Actions | execuções 43429040197 e 43429139001 |
| Favoritos, ajustes de acessibilidade, voz | Funcionam (validados no navegador em 13/11) | testes Angular com axe |

## 2. Ganhos da GenAI

- O contexto é o grande ganho: no teste inédito v3, o mesmo `qwen2.5:7b` sem a base acerta 8,7% e erra fatos em
  34,8% das perguntas; com RAG, 65,2% e 15,2%; com o agente v1, 65,2% e **8,7%**, com 84,6% de recusa correta.
- A v3 (busca híbrida, cross-encoder, checagens de evidência) chegou a 88,0% no DEV, mas ficou em 58,7% no teste: não
  generalizou, e isso está escrito no relatório. O site segue com o agente v1, agora no 7b.
- Seção 12 do [genai/RELATORIO.md](../genai/RELATORIO.md): ablações, teste final rodado uma vez e 5 erros analisados.

## 3. RPA

- Dois robôs: coletor (8 vezes por dia, 6 pontos, previsões reais) e boletim (diário).
- O boletim declara a categoria: **ESTIMADO** (esperas calculadas de previsões, nunca atraso medido), **SIMULADO** (só em
  modo demonstração) ou **INDISPONÍVEL** (sem dado, sem números).
- Primeira coleta em produção em 13/11: 6 amostras, 111 ônibus previstos, 0 rejeitadas. O boletim do dia 12 saiu
  INDISPONÍVEL, porque ainda não havia coleta; o de 13/11 sai na execução de 14/11.
- BPMN novo, README, relatório e roteiro do vídeo atualizados para o fluxo real; 45 testes.

## 4. SPTrans

Real em produção pelo gateway da Prefeitura (OAuth2). O 500 intermitente do gateway é tratado com 3 tentativas, e uma
falha nunca vira "sem ônibus previsto". Previsão é sempre apresentada como previsão.

## 5. Assistente no site

- Estados claros: disponível, processando, indisponível e erro.
- Perguntas de horário: backend + SPTrans, sempre disponíveis.
- Perguntas de regras: FastAPI + Ollama no PC do Pedro, publicada por um **Cloudflare Quick Tunnel gratuito**; o Ollama
  fica só no loopback, e apenas a API (porta 8001, com chave) sai pelo túnel.
- O PC informa o endereço do túnel ao Render (`PUT /api/genai/endereco`, com a chave). O backend só aceita depois de
  `/health` com status ok e de um desafio HMAC que prova que a API conhece a mesma chave.
- Com o PC desligado, o site mostra "indisponível" nas perguntas de regras.

## 6. Redesign

Correções de 13/11 validadas no navegador (computador escuro, celular 375 px claro, letra 175%): rótulos da barra
inferior sem sobreposição, "Atualizar" sem quebra, boletim com "Situação do boletim: Atualizado", rota `/ajustes`,
realce do menu em busca e ponto, nomes de ponto corretos na voz ("Pça. da Sé") e frases separadas na voz.

## 7. Testes

Spring 106, GenAI 126, RPA 45, Angular 40, integração 26, scripts 8: todos passando localmente. A CI roda Gitleaks,
Semgrep, testes Python, Spring com PostgreSQL, Angular com axe, Docker e Trivy; o Render só publica com a CI verde.

## 8. Revisões de código

Quatro revisões adversariais entre 11/11 e 13/11, com 13 achados no total (dois altos), todos corrigidos com
testes de regressão.

## 9. Deploy

- Render Free com Blueprint (`render.yaml`), publicação automática só com a CI verde.
- GenAI no PC do Pedro, publicada pelo Quick Tunnel gratuito, sem domínio, DNS ou serviço pago.
- Coleta e boletim do RPA no GitHub Actions gratuito.

## 10. Critérios FIAP

Revisão atualizada em [REVISAO_CRITERIOS.md](REVISAO_CRITERIOS.md):

- **GenAI:** casos com "não consta", base em trechos com fonte, recall@1/@3 e limiar, JSON com citação,
  especialização comparada a RAG e a sem contexto, 5 erros reais e README.
- **RPA:** 8 etapas, integração real com o MVP, testes de sucesso, decisão e falha, e logs.

## 11. Limitações

- O assistente de regras depende do PC ligado; a URL do Quick Tunnel muda a cada início (o registro automático
  resolve) e não tem garantia de disponibilidade.
- A GenAI recusa cerca de 1 em 5 perguntas respondíveis no teste; a rubrica automática também erra em algumas negações.
  Não houve adjudicação humana do teste v3.
- O boletim só mede espera **prevista**; chegadas observadas não existem na API pública.
- Banco do Render Free expira por volta de 11/12/2026.
- Rodar avaliação no Ollama com o site no ar deixa as respostas acima de 40 s. A primeira pergunta de regras depois
  de alguns minutos parados leva cerca de 25 s, porque o Ollama recarrega o modelo; as seguintes levam de 2 a 5 s.

## 12. O que depende do Pedro

1. **Durante a avaliação**, deixar o PC ligado com
   `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/genai/iniciar.ps1 -TunelRapido`. Para conferir, use
   `status.ps1`; para encerrar, `parar.ps1`.
2. **Gravar os vídeos** (GenAI e RPA). Roteiro do RPA: `rpa/docs/roteiro_video.md`. Depois, colocar os links nos
   relatórios.
3. **Exportar o PDF do relatório do RPA** (`rpa/docs/relatorio.md`), com o print da tela `/boletim`.
4. **Orientação substituída em 14/11:** a FIAP exige repositório público. Preparar uma cópia sanitizada com histórico
   novo e preservar este repositório privado: o histórico antigo conserva exemplos pessoais. Ver
   [checklist atual](ENTREGA_FIAP.md) e a revisão de privacidade antes de publicar.

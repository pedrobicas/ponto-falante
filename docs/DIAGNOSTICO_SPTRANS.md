# Diagnóstico SPTrans — 11/11/2026

## Evidência e limite da conclusão

A requisição real correta recebeu **HTTP 403 durante o login**, antes de qualquer consulta de linhas. Duas execuções controladas no mesmo endpoint oficial confirmaram o resultado. Não foram testadas URLs alternativas, usados headers para imitar navegador, seguidos redirecionamentos, desativada validação TLS ou tentados contornos de acesso.

Verificações locais, sem exibir a chave:

- Token lido de `D:\GLOBALSOLUTION_2\.env`, sem override do ambiente, sem espaços externos/internos, quebra de linha ou BOM.
- `POST https://api.olhovivo.sptrans.com.br/v2.1/Login/Autenticar`, token codificado no parâmetro de query exigido pela documentação, corpo vazio. Não é Bearer nem JSON no corpo.
- HTTPS com validação TLS padrão; nenhum proxy HTTPS configurado no cliente Python.
- Resposta: status **403**, `Content-Type` classificado como **application/json**, banner `Server` classificado como **CLOUDFLARE**, **717 bytes** lidos, sem `Location`.
- A autenticação não concluiu; a consulta `/Linha/Buscar` não ocorreu. Não se trata de perda do cookie entre login e consulta.

**Conclusão comprovada:** houve recusa HTTP externa ao código da aplicação na etapa de autenticação. O banner indica uma camada Cloudflare no caminho, mas não comprova qual regra recusou a chamada, se a decisão foi do servidor de origem/gateway nem se a chave é válida. Não atribuir o 403 automaticamente a token inválido ou a uma regra específica de WAF. A documentação prevê booleanos `true`/`false` para a autenticação; aqui houve uma resposta HTTP de erro antes de estabelecer sessão.

Referência oficial: [SPTrans — documentação API, HTTPS e autenticação](https://www.sptrans.com.br/desenvolvedores/api-do-olho-vivo-guia-de-referencia/documentacao-api/).

## Correções implementadas

- `testar_sptrans.py`: identifica a etapa, status e metadados reduzidos a categorias fixas; limita leitura de erro; não imprime corpo, URL, valores de headers, cookies ou identificadores remotos. Mantém cookie em memória e não repete nem redireciona um 403.
- `ambiente.py` e launcher: mesma normalização do token; rejeitam espaços internos e controles sem expor o valor. O teste informa se removeu espaços externos, sem alterar o arquivo.
- `ConfigSptrans.java`: configuração nova, executada antes do binding de `PfProps`. Corrige o default HTTP legado para HTTPS em memória, rejeita HTTP externo e normaliza o token. O cliente original da equipe foi inspecionado e preservado: já usa POST, query token, cookie e renovação única após 401. Testes confirmaram que 403 no login ou consulta não dispara repetição.
- `PF_SPTRANS_MODO=demo|auto`: demonstração explícita, independente da chave armazenada. Em demo a aplicação recebe configuração sem token e não consulta a SPTrans. Em auto, falhas externas continuam sendo indisponibilidade, sem esconder dados simulados como reais.
- `.env` **local e ignorado** recebeu somente `PF_SPTRANS_MODO=demo`; a chave existente foi preservada. Compose/Render têm suporte à variável. Para voltar ao real, validar primeiro o teste direto, trocar o modo para `auto` e reiniciar.

## Resultados reais

- Python: **26 testes passaram**, incluindo 403 no login e consulta, sessão, redirecionamento recusado, respostas com segredos refletidos e diagnóstico sem vazamento.
- Maven `verify`: **19 testes, 0 falhas/erros/ignorados**, incluindo configuração segura, 403 sem repetição e demonstração explícita com token configurado.
- Integração real local: Angular compilado servido pelo Spring, PostgreSQL temporário, RPA original publicando e relendo o boletim; passou sem depender da API externa.
- Novo teste externo após as correções: **código de saída 1**, sem sucesso de autenticação:

```text
SPTrans: etapa=configuracao; origem=arquivo; configurado=sim; ajuste_externo=nao; proxy_https=nao; verificacao_TLS=ativa.
SPTrans: etapa=login; HTTP 403; categoria=JSON_ERRO; tipo=application/json; servidor=CLOUDFLARE; bytes_lidos=717; amostra_limitada=nao; redirecionamento=ausente; corpo=omitido
```

Evidências locais ignoradas: `.validation/sptrans-real-final.json` e `.validation/sptrans-spring-verificacao.log`. Nenhum conteúdo bruto da resposta externa ou chave foi salvo nesses arquivos. O diagnóstico reduzido pode ser informado ao suporte da SPTrans pelo usuário; não há envio automático de mensagem ou credencial.

## Atualização (11/11/2026, 16h): causa do 403 identificada

O 403 vinha do Cloudflare da SPTrans com **erro 1010 (`browser_signature_banned`)**: a regra barra o User-Agent
genérico do cliente HTTP (`Python-urllib`, e o mesmo vale para o `Java-http-client` padrão). Não é a chave.

Correção: o teste direto e o `OlhoVivoProvider` passam a enviar um User-Agent que identifica a aplicação
(`PontoFalante/1.0 (+https://github.com/pedrobicas/ponto-falante)`), sem imitar navegador. O diagnóstico agora
mostra só o código e o nome públicos do erro do Cloudflare. Teste de contrato novo garante o cabeçalho.

Resultado real com o User-Agent da aplicação:

```text
SPTrans: etapa=login; HTTP 200; categoria=AUTENTICACAO_RECUSADA
```

Ou seja, a requisição chega à SPTrans, mas o login responde `false`: a API não reconhece a chave configurada.
O formato da chave local está correto (64 caracteres hexadecimais, sem espaços). Próximo passo é do titular da
conta: conferir no portal do desenvolvedor da SPTrans se a chave está ativa e é a do aplicativo cadastrado, ou
gerar outra. Com o login respondendo `true` no `testar_sptrans.py`, trocar `PF_SPTRANS_MODO` para `auto`.

## Confirmação independente (11/11/2026, 21h15)

O titular da conta testou pelo próprio navegador, direto no domínio da API, com a chave copiada da página
"Meus Aplicativos" (status "Chave de ativação homologada e em uso"): `POST /v2.1/Login/Autenticar?token=...`
respondeu **`false`**. Como o mesmo resultado aparece fora do projeto, a recusa é do lado da conta/API da SPTrans,
não do código. O MVP continua em `PF_SPTRANS_MODO=demo`, com os dados identificados como SIMULADO na interface e
na API. Encaminhamento: contato com a área de desenvolvedores da SPTrans ou criação de um novo aplicativo no portal;
quando o teste direto (`scripts/integracao/testar_sptrans.py`) responder `autenticacao OK`, trocar para `auto`.

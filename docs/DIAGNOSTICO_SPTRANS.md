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

## Investigação aprofundada e gateway da Prefeitura (11/11/2026, noite)

### Login direto: matriz de variações

`scripts/integracao/diagnosticar_sptrans.py` testa a chave do `.env` sem imprimi-la (só comprimento e alfabeto)
em host, protocolo, versão e forma de envio. Saída completa em
[evidencias/sptrans_matriz_login.txt](evidencias/sptrans_matriz_login.txt):

| Variação | Resultado |
|---|---|
| HTTPS e HTTP, v2.1, `POST ?token=` (forma documentada) | HTTP 200, `false`, sem cookie |
| Token no corpo (form) | HTTP 404 |
| `GET` | HTTP 405 |
| Versão `v2` | HTTP 500 |
| Chave em maiúsculas | HTTP 200, `false` |
| **Controle: chave inválida (64 zeros)** | **HTTP 200, `false`** |

A chave tem o formato esperado (64 hexadecimais minúsculos, sem aspas, espaços, BOM ou caracteres invisíveis).
O ponto decisivo é o controle: a API responde exatamente igual a uma chave válida recém-homologada e a uma chave
inventada. Somado ao teste do titular (duas aplicações diferentes, PowerShell, Git Bash e navegador, todos com
`false`), não há variação de requisição do nosso lado que mude a resposta. O código do cliente segue a documentação
e o fluxo (login, cookie `apiCredentials`, consultas) está coberto por testes de contrato.

### Gateway oficial da Prefeitura: alternativa funcional

`https://gateway.apilib.prefeitura.sp.gov.br/sptrans/olhovivo/v2.1` é um WSO2 API Manager da Prefeitura
(Secretaria de Inovação e Tecnologia). A loja `https://apilib.prefeitura.sp.gov.br/store/` publica a API
**OlhoVivo v2.1** (provedor admin, atualizada em 02/10/2026, status PUBLICADO). A especificação OpenAPI pública
foi salva em [evidencias/olhovivo_gateway_openapi.json](evidencias/olhovivo_gateway_openapi.json). Verificado:

- Os mesmos caminhos da Olho Vivo (`/Linha/Buscar`, `/Parada/Buscar`, `/Previsao/Parada`, `/Posicao` etc.), todos `GET`,
  com o mesmo JSON. **Não existe `/Login/Autenticar`**: a autenticação com a SPTrans é feita pelo gateway.
- Segurança OAuth2: sem cabeçalho, o gateway responde 401 `900902 Missing Credentials`; com Bearer inválido,
  401 `900901 Invalid Credentials`.
- Emissão de token: `POST https://gateway.apilib.prefeitura.sp.gov.br/token` com `grant_type=client_credentials`
  e Basic `ConsumerKey:ConsumerSecret`. Com credenciais fictícias responde 401 `invalid_client`, ou seja, o fluxo
  está ativo.

Credenciais exigidas: uma conta na loja apilib, uma aplicação criada lá, a inscrição dessa aplicação na API OlhoVivo
v2.1 e o par **Consumer Key / Consumer Secret** gerado em "Chaves de Produção". A chave do portal da SPTrans não é
usada nesse caminho.

### O que foi implementado

- `OlhoVivoProvider` ganhou o modo gateway: obtém o token por `client_credentials`, guarda até `expires_in` (com
  margem de 60 s), envia `Authorization: Bearer` e, se receber 401, gera um token novo uma única vez. Falha de
  credencial entra na mesma espera compartilhada de 30 s do login direto e o site continua respondendo.
- Variáveis `SPTRANS_GATEWAY_CHAVE` e `SPTRANS_GATEWAY_SEGREDO` (Render com `sync: false`, `.env.example`,
  `docker-compose.yml`). Quando as duas estão preenchidas, o gateway tem prioridade sobre `SPTRANS_TOKEN`.
  `PF_SPTRANS_MODO=demo` continua desligando qualquer chamada externa, inclusive ao gateway.
- URLs do gateway validadas como HTTPS, sem credenciais ou parâmetros.
- Testes: `OlhoVivoGatewayContractTest` (token único reutilizado, Bearer nas consultas, nenhum login direto,
  credencial recusada sem consulta, token revogado renovado uma vez) e dois testes de configuração.
- `diagnosticar_sptrans.py --gateway` testa o fluxo real com as credenciais do `.env`, sem imprimi-las.

### O que depende do titular

1. Criar conta em https://apilib.prefeitura.sp.gov.br/store/ ("Criar Conta").
2. Em "Aplicações", criar uma aplicação (por exemplo, PontoFalante).
3. Abrir a API OlhoVivo v2.1, escolher essa aplicação e inscrever (Subscribe).
4. Na aplicação, em "Chaves de Produção", gerar as chaves e copiar Consumer Key e Consumer Secret.
5. Colocar no `.env` como `SPTRANS_GATEWAY_CHAVE` e `SPTRANS_GATEWAY_SEGREDO` e rodar
   `python scripts/integracao/diagnosticar_sptrans.py --gateway`.
6. Com o teste devolvendo linhas, preencher as mesmas duas variáveis no Render e trocar `PF_SPTRANS_MODO` para `auto`.

Se o gateway também recusar, a reclamação vai ao SP156 (indicado na descrição da API no gateway).

### Resultado com as credenciais reais do gateway (11/11/2026, 22h19)

Funcionou. Evidência completa em [evidencias/sptrans_gateway_validacao.txt](evidencias/sptrans_gateway_validacao.txt)
e captura em [evidencias/telas/ponto-real-gateway.jpg](evidencias/telas/ponto-real-gateway.jpg):

- `/token` emitiu o access_token (validade de cerca de 1 h).
- Consultas reais: 4 linhas para "8000", 2 pontos para "paulista" e 21 ônibus previstos em 14 linhas no ponto
  260015039 (Paulista B/C).
- Spring local em modo real (`rodar_mvp_local.py --sptrans-gateway`): `/api/status` com `sptrans: REAL`,
  respostas com `fonte: OLHO_VIVO` e `tipo: PREVISAO`, prefixo do veículo anonimizado, e o teste de aceitação
  passou. A tela mostra "Dados da SPTrans" e "previsto em", nunca chegada.

Problema encontrado e corrigido: o gateway devolve HTTP 500 intermitente (`Transport error: 411 Length Required`,
vindo da chamada interna dele à SPTrans) em cerca de 20% das requisições (4 de 20 numa medição). Como as consultas
são `GET` idempotentes, o `OlhoVivoProvider` repete até 3 vezes com espera curta; se persistir, o site informa
indisponibilidade como antes. Dois testes de contrato cobrem o caso.

Correção de segurança (12/11/2026, apontada pela revisão independente): a primeira versão da matriz incluía variações
por HTTP, o que enviou a chave da Olho Vivo direta em texto claro. As variações HTTP foram removidas; o script só usa
HTTPS. A chave direta não é usada pelo produto (o gateway usa OAuth), mas recomenda-se excluí-la ou gerar outra no portal.

# Embarque assistido

O Embarque assistido acompanha a pessoa do ponto até o momento de entrar no ônibus. Ela escolhe o ponto e até três
linhas, e o aplicativo consulta as previsões da SPTrans sozinho, avisa por voz quando o ônibus está chegando e ajuda a
conferir se é o ônibus certo. Foi pensado para pessoas com deficiência visual e idosas, que hoje dependem de perguntar
ao motorista ou a desconhecidos.

Tela: `/embarque` (também acessível pelo início, pela página do ponto e pelas respostas do assistente).

## Fluxo

1. **Ponto**: trajeto favorito com um toque, "Usar minha localização" (pontos em até 400 m) ou busca por nome, rua ou
   código. O ponto escolhido sempre passa por uma confirmação ("É este o seu ponto?") com endereço, código e distância,
   porque o GPS no celular erra dezenas de metros e o ponto do outro lado da rua leva para o sentido oposto.
2. **Ônibus**: lista das linhas do cadastro oficial (GTFS) no ponto, com o destino de cada sentido e a próxima previsão.
   Se o cadastro mostra que a linha não para no ponto, o backend recusa o acompanhamento (`LINHA_NAO_PARA_NO_PONTO`).
3. **Acompanhar**: o aplicativo consulta a cada 20 segundos, mostra o próximo ônibus em destaque e fala só quando algo
   importante muda. A tela fica acesa (Wake Lock) enquanto acompanha. "Embarquei" encerra e volta ao começo;
   "Encerrar" mantém o ponto para escolher outra linha.

O acompanhamento é guardado no servidor: se a página recarregar ou o celular travar, ele é retomado. Expira em 3 horas.

## Avisos por voz

A regra é falar pouco e só com informação que veio da SPTrans. A classe `AnunciadorEmbarque` decide quando falar:

| Situação | Aviso |
|---|---|
| Início | linha, destino e minutos previstos |
| Cruzou 10, 5 e 3 minutos | "Linha 8000-10 em 5 minutos." (marcos acima da primeira previsão são ignorados) |
| 1 minuto ou menos | aviso urgente, vibração, pede para confirmar com o motorista |
| Previsão atrasou 3 minutos ou mais | informa o novo tempo e os marcos voltam a valer |
| O ônibus que estava chegando sumiu da previsão | aviso urgente: "pode ter passado", e qual é o próximo |
| Nenhuma previsão | uma única vez; avisa quando aparecer |
| Duas falhas seguidas de atualização | uma única vez; avisa quando voltar |

A mesma frase nunca é repetida automaticamente. "Repetir aviso" e o comando "quanto falta" respondem na hora. A voz do
aplicativo pode ser desligada; os avisos continuam em regiões `aria-live` para quem usa leitor de tela. Em modo
demonstração o primeiro aviso começa com "Demonstração com horários simulados".

## Assistente de embarque

Comandos por voz (Web Speech API) ou texto são interpretados localmente por regras (`comandos-embarque.ts`), então
funcionam mesmo com a GenAI desligada. Exemplos: "pontos perto de mim", "estou no ponto Avenida Paulista", "o segundo",
"quero pegar o 875A", "quanto falta", "repetir", "salvar nos favoritos como trabalho", "ir para o trabalho",
"remover favorito", "desliga a voz", "embarquei", "parar o acompanhamento".

A assistente executa as ações no mesmo estado da tela. Ações que mudam ou apagam algo (encerrar, trocar de ponto durante
o acompanhamento, salvar e remover favorito) pedem confirmação ("Diga sim ou não"). O que não é comando vai para o
assistente geral (`/api/chat`) com o ponto e a linha atuais como contexto; horários continuam vindo do backend.

## Conferência do letreiro pela câmera

A pessoa aponta o celular para a frente do ônibus e toca em Conferir. A foto (reduzida a 1280 px) vai para o backend,
que a repassa ao **modelo de visão da equipe** (pasta [`visao/`](../visao/README.md): YOLO11n treinado com ônibus de
São Paulo para achar o letreiro + EasyOCR para ler a linha) pelo contrato
[`contratos/openapi-visao-letreiro.yaml`](../contratos/openapi-visao-letreiro.yaml). Junto com a foto, o backend manda
as linhas que a pessoa acompanha e as que param no ponto segundo o cadastro GTFS: o modelo só confirma uma linha que
casa exatamente com uma delas (tolerando O/0, I/1, S/5, B/8). Uma linha legível fora da lista volta como leitura não
validada, com confiança menor, e nunca é trocada pela linha "mais parecida".

O backend decide (classe `ConferenciaLetreiro`, confiança mínima 0,45, o mesmo limiar por quadro do anunciador da
equipe): CONFERE, NUMERO_CONFERE (número igual, variante não lida), NAO_CONFERE ou INCONCLUSIVO. No INCONCLUSIVO a frase
orienta a apontar melhor com base no que o detector viu ("não encontrei ônibus", "vi o ônibus, mas não o letreiro",
"o letreiro pode estar mostrando só o destino"). Se a primeira foto não der leitura segura, o aplicativo tira até 3
fotos seguidas, com 1,2 s de intervalo, porque o letreiro de SP alterna entre número e destino. Toda resposta pede para
confirmar com o motorista.

O botão **Enviar uma foto do letreiro** aceita uma foto já tirada (galeria do celular ou arquivo do computador), útil
para testar e para quem fotografou o ônibus antes. A foto é reduzida no próprio aparelho para no máximo 1280 px em JPEG
(fotos de celular passam de 4000 px e dos 2 MB aceitos) e segue pelo mesmo caminho, uma conferência só. A tela mostra a
miniatura da foto enviada; nada é guardado.

Onde o modelo roda: precisa de ~1,5 GB de memória (medido na CPU), acima dos 512 MB do Render gratuito. Ele roda no PC
da equipe (na CPU, de 2,8 a 6,4 s por foto medidos em 17/11; com placa NVIDIA o instalador usa CUDA) e é publicado como a GenAI: Quick Tunnel da Cloudflare e registro automático no
backend (`PUT /api/visao/endereco`, com `/health` e desafio HMAC). Com o PC desligado, `GET /api/embarque/visao`
responde "indisponível agora" e a tela não abre a câmera. Nada é simulado. Como ligar: [`visao/INTEGRACAO.md`](../visao/INTEGRACAO.md).

## Privacidade e segurança

- Sem login: cada aparelho gera um identificador aleatório; o servidor guarda apenas o hash com sal (`PF_SALT`).
- Localização é usada só na busca e não é gravada. Fotos do letreiro não são gravadas; só o resultado da conferência.
- "Apagar meus dados do embarque" remove favoritos, acompanhamentos e conferências do aparelho.
- Limite de ações por aparelho (429), validação de entrada, apelidos sem marcação HTML, imagens verificadas pelo
  conteúdo (JPEG/PNG, até 2 MB).

## Indicadores de impacto

`GET /api/embarque/indicadores` resume os últimos 30 dias, contando só acompanhamentos com dados reais: quantidade,
embarques confirmados pela pessoa, taxa de confirmação, espera prevista média e trajetos salvos.

## Implementação

| Camada | Arquivos |
|---|---|
| Banco | `backend/src/main/resources/db/migration/V3__embarque_assistido.sql` |
| Backend | `backend/src/main/java/br/fiap/pontofalante/embarque/` (controller, serviço, conferência do letreiro, adaptador de visão) |
| Frontend | `frontend/src/app/features/embarque/`, `core/embarque.store.ts`, `core/anunciador-embarque.ts`, `core/comandos-embarque.ts`, `core/assistente-embarque.service.ts` |
| Contratos | `contratos/openapi-mvp.yaml` (tag `embarque`) e `contratos/openapi-visao-letreiro.yaml` |

## Testes

- Backend: regras de conferência do letreiro e validação do contrato do modelo; API completa com PostgreSQL embutido
  (favoritos por aparelho, filtro por linha e sentido, retomada, encerramento, exclusão de dados, câmera não conectada);
  contrato da visão contra um servidor de teste que imita o modelo; registro do túnel da visão; linhas enviadas ao modelo.
- Visão: `visao/tests` (contrato HTTP com detector simulado na CI; com `PF_VISAO_TESTE_REAL=1`, o modelo real nas 6
  fotos de demonstração).
- Frontend: política de avisos, interpretação de comandos, fluxos da assistente e telas com auditoria axe.
- Ponta a ponta: `scripts/integracao/validar_embarque.py` percorre o fluxo inteiro no navegador em desktop e celular
  (Pixel 7), com axe (WCAG 2.1 AA) em cada etapa e verificação de rolagem horizontal.
  `scripts/integracao/validar_visao.py` faz a conferência com a câmera do navegador alimentada por uma foto real e o
  modelo real respondendo.

## Limites conhecidos

- Previsão da SPTrans não é chegada observada: o ônibus pode adiantar, atrasar ou não passar. A tela e os avisos dizem isso.
- A conferência pela câmera só funciona depois que o modelo de visão for publicado.
- No navegador, a voz e a consulta param se o sistema suspender a aba em segundo plano; a tela acesa reduz esse risco.

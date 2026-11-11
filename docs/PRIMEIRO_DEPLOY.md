# Primeiro deploy público

O código completo está em `integracao/mvp`; os originais não commitados da `main` e o worktree GenAI foram preservados. O Blueprint aponta explicitamente para essa branch, usa apenas planos **Free**, inicia SPTrans em demonstração e deixa GenAI opcional/desligado no primeiro deploy.

## O que falta autorizar/conectar

1. O GitHub conectado é **pedrobicas**, mas este checkout ainda não tem `origin`. Escolher nome e visibilidade do repositório e autorizar sua criação/primeiro push. Nenhum repositório foi criado nem enviado nesta sessão.
2. Entrar em **https://dashboard.render.com/** com sua conta e permitir acesso do Render ao repositório escolhido. Não há credencial Render configurada nesta sessão.
3. Docker não está instalado nesta máquina. Os estágios npm/Maven, o JAR, os schemas e os workflows foram validados localmente; o job de imagem precisa executar no GitHub antes do deploy.

## Depois de autorizar o repositório

No diretório da branch de integração, apontar `origin` para a URL escolhida e enviar **esta branch**. Exemplo para repositório já criado, substituindo `REPOSITORIO`:

```powershell
git remote add origin https://github.com/pedrobicas/REPOSITORIO.git
git push -u origin integracao/mvp
```

Não enviar `.env`, `.validation`, caches ou arquivos de túnel. A CI deve passar: Python, Spring/PostgreSQL, Angular/acessibilidade, Gitleaks, Semgrep, build Docker, Trivy e teste HTTP da imagem. Não ignorar checks que falhem; examinar e corrigir antes de publicar.

No Render: **New → Blueprint → conectar GitHub → escolher repositório → branch `integracao/mvp` → revisar `render.yaml` → Apply**. Conferir serviço e banco com plano **Free**. O Render gera `PF_SALT`, `RPA_API_KEY` e as chaves das integrações; `DATABASE_URL` vem do banco. Não há token SPTrans ou endpoint GenAI obrigatório para publicar o MVP demonstrativo.

## Aceite na URL publicada

```powershell
python scripts/integracao/testar_mvp.py --url https://SERVICO.onrender.com
```

Verificar no navegador busca `paulista`, abertura do ponto, selo de dados simulados, previsões, ajustes de contraste/letra, botão de voz, chat indisponível de forma amigável e navegação direta em `/sobre`. Publicar um boletim com o RPA e confirmar após reiniciar o serviço. Nunca publicar um sucesso de GenAI se o serviço não estiver ligado.

Para agendar o RPA: **GitHub → Settings → Secrets and variables → Actions**, cadastrar `MVP_URL=https://SERVICO.onrender.com/api` e `RPA_API_KEY` com o valor seguro exibido no Environment do Render. Executar manualmente `rpa-diario` antes de depender do cron. O workflow agendado só roda a partir da branch padrão do GitHub: definir `integracao/mvp` como padrão no primeiro deploy, ou integrar em `main` e atualizar `branch` no Blueprint quando a equipe voltar.

## GenAI e limites do plano gratuito

Depois do MVP publicado, configurar no Render `GENAI_URL` com o túnel HTTPS e `GENAI_API_KEY` com a mesma chave do serviço local. Usar os scripts existentes de `scripts/genai/`; não alterar DNS nesta etapa. O serviço GenAI permanece em loopback e protegido por chave.

O serviço Free dorme após inatividade e o PostgreSQL Free expira 30 dias após a criação. Criar o banco perto da apresentação e exportar os dados necessários antes de expirar. [Limites oficiais do Render](https://render.com/docs/free). Nenhum plano pago foi contratado.

// Capturas reais do vídeo de GenAI (produção + arquivos do repositório).
//   node scripts/video/cap_genai.js <pasta das cenas> <pasta de trabalho> [cena...]
// A conversa usa o site publicado, a SPTrans real e a GenAI no PC do dono (Ollama). A avaliação só LÊ os placares já
// registrados: nenhum conjunto de teste é executado de novo.
const { gravar, abrirNavegador, espera } = require('./captura.js');
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

const RAIZ = path.resolve(__dirname, '..', '..');
const PY = path.join(RAIZ, '.venv', 'Scripts', 'python.exe');
const SITE = 'https://ponto-falante.onrender.com';
const [CENAS, TRAB] = process.argv.slice(2, 4);
const SO = process.argv.slice(4);
const quer = (n) => !SO.length || SO.includes(n);
const RESP = '.fala--assistente:not(.fala--processando)';

async function perguntar(c, page, texto, id, folga = 140) {
  const campo = page.getByPlaceholder('Escreva sua pergunta');
  await c.rolarAte(campo, 470, 900);
  await c.clicar(campo, 600);
  await c.digitar(texto);
  await espera(450);
  const antes = await page.locator(RESP).count();
  c.marcar('enviada_' + id);
  await page.keyboard.press('Enter');
  await espera(700);
  await c.rolarAte(page.locator('.fala--voce').last(), 160, 800);
  for (let k = 0; k < 600 && (await page.locator(RESP).count()) <= antes; k++) await espera(200);
  c.marcar('resposta_' + id);
  await espera(400);
  await c.rolarAte(page.locator('.fala--voce').last(), folga, 1100);
  await espera(900);
}

(async () => {
  fs.mkdirSync(CENAS, { recursive: true });
  fs.mkdirSync(TRAB, { recursive: true });
  const nav = await abrirNavegador();
  try {
    if (quer('genai_chat')) {
      await gravar(nav, CENAS, 'genai_chat', async (c, page) => {
        await page.goto(SITE + '/', { waitUntil: 'networkidle', timeout: 90000 });
        await espera(1500);
        c.marcar('inicio_site');
        await c.clicar(page.getByRole('link', { name: 'Assistente' }).first(), 900);
        await page.waitForURL(/assistente/);
        await page.getByText('Disponível').first().waitFor({ timeout: 60000 });
        await espera(1800);
        c.marcar('assistente');
        await perguntar(c, page, 'Qual ônibus vai para o Centro saindo da Paulista, 1374?', 'rota');
        await espera(5500);
        await perguntar(c, page, 'Quanto falta para a 875A-10?', 'falta');
        await espera(4500);
        await perguntar(c, page, 'E no sentido contrário?', 'contrario');
        await espera(5500);
        await perguntar(c, page, 'Tenho 66 anos, posso andar gratuitamente?', 'idoso');
        await espera(3500);
        const fontes = page.getByText('Ver fontes da resposta').last();
        c.marcar('fontes');
        await c.clicar(fontes, 800);
        await espera(600);
        await c.rolar(160, 900);
        await espera(4500);
        c.marcar('ouvir');
        await c.clicar(page.getByRole('button', { name: /Ouvir resposta/ }).last(), 800);
        await espera(3500);
        const parar = page.getByRole('button', { name: /Parar/ }).last();
        if (await parar.count()) await c.clicar(parar, 500);
        await espera(800);
        await perguntar(c, page, 'Posso levar meu cachorro no ônibus em Curitiba?', 'recusa');
        await espera(6000);
        c.marcar('ajustes');
        await c.clicar(page.getByRole('link', { name: 'Ajustes' }).first(), 900);
        await page.waitForURL(/acessibilidade|ajustes/);
        await espera(1500);
        await c.clicar(page.locator('label.escolha', { hasText: 'Grande' }).first(), 800);
        await espera(1600);
        const cores = page.locator('summary', { hasText: 'Cores e contraste' });
        await c.clicar(cores, 800);
        await espera(900);
        await c.clicar(page.locator('label.escolha', { hasText: 'Alto contraste escuro' }).first(), 900);
        await espera(2200);
        c.marcar('volta');
        await c.clicar(page.getByRole('link', { name: 'Assistente' }).first(), 900);
        await page.waitForURL(/assistente/);
        await espera(1200);
        await c.rolarAte(page.locator('.fala--voce').last(), 140, 1500);
        await espera(5000);
        c.marcar('fim_chat');
      });
    }

    if (quer('genai_arq')) {
      const blocos = (arq) => [...fs.readFileSync(path.join(RAIZ, arq), 'utf-8').replace(/\r\n/g, '\n')
        .matchAll(/```mermaid\n([\s\S]*?)```/g)].map((m) => m[1]);
      const sistema = blocos('README.md').find((b) => b.includes('FastAPI GenAI'));
      const pipeline = blocos('genai/RELATORIO.md').find((b) => b.includes('POST /api/chat'));
      if (!sistema || !pipeline) throw new Error('diagramas não encontrados no README.md ou em genai/RELATORIO.md');
      const esc = (t) => t.replace(/&/g, '&amp;').replace(/</g, '&lt;');
      // Mesmos diagramas do repositório; só a direção do desenho do pipeline muda (TD -> LR) para caber em 16:9.
      const html = `<!doctype html><html><head><meta charset="utf-8"><style>
        body{margin:0;background:#fff;font-family:'Segoe UI',sans-serif}
        section{height:720px;display:flex;flex-direction:column;align-items:center;justify-content:center;box-sizing:border-box;padding:24px 30px}
        h2{font:600 22px 'Segoe UI';color:#333;margin:0 0 14px} .mermaid{width:1220px;text-align:center}
        .mermaid svg{max-width:1220px!important;max-height:620px;height:auto}
        .largo{align-items:flex-start;overflow:hidden} .largo h2{align-self:center} .trilho{will-change:transform}
        .largo .mermaid{width:auto} .largo .mermaid svg{width:2900px;max-width:none!important;max-height:none}</style>
        <script src="https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.min.js"></script></head><body>
        <section><h2>README.md · arquitetura do MVP</h2><pre class="mermaid">${esc(sistema)}</pre></section>
        <section class="largo"><h2>genai/RELATORIO.md · pipeline de resposta (agente)</h2><div class="trilho"><pre class="mermaid">${esc(pipeline.replace('flowchart TD', 'flowchart LR'))}</pre></div></section>
        <script>mermaid.initialize({startOnLoad:true,theme:'neutral',flowchart:{curve:'basis'},themeVariables:{fontSize:'17px',fontFamily:'Segoe UI'}});</script>
        </body></html>`;
      const arq = path.join(TRAB, 'arquitetura.html');
      fs.writeFileSync(arq, html);
      await gravar(nav, CENAS, 'genai_arq', async (c, page) => {
        await page.goto('file:///' + arq.replace(/\\/g, '/'), { waitUntil: 'networkidle' });
        await page.locator('.mermaid svg').first().waitFor({ timeout: 30000 });
        await espera(1000);
        await page.waitForFunction(() => document.querySelectorAll('.mermaid svg').length === 2, null, { timeout: 30000 }).catch(() => {});
        c.marcar('sistema');
        await espera(6500);
        c.marcar('rolagem');
        await c.rolar(720, 1600);
        c.marcar('pipeline');
        await espera(2500);
        c.marcar('panoramica');
        await page.evaluate(async () => {
          const t = document.querySelector('.trilho'); const fim = t.scrollWidth - 1220; const t0 = performance.now(); const ms = 7000;
          const f = (k) => (k < 0.5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2);
          await new Promise((ok) => { const passo = (agora) => { const k = Math.min(1, (agora - t0) / ms);
            t.style.transform = 'translateX(' + (-fim * f(k)) + 'px)'; if (k < 1) requestAnimationFrame(passo); else ok(); }; requestAnimationFrame(passo); });
        });
        await espera(2500);
        c.marcar('fim_arq');
      });
    }

    if (quer('genai_term')) {
      const v3 = path.join(RAIZ, 'genai', 'avaliacao', 'v3');
      const roteiro = { titulo: 'Avaliação da GenAI · arquivos registrados', prompt: 'genai>', comandos: [
        { mostrar: 'mostrar.py placar v3/teste_final_20261113/placar_teste_v3.csv   # teste inédito, rodado uma vez',
          argv: [PY, path.join(__dirname, 'mostrar.py'), 'placar', path.join(v3, 'teste_final_20261113', 'placar_teste_v3.csv')],
          ritmo_ms: 260, pausa_depois: 9 },
        { mostrar: 'mostrar.py placar v3/dev_agente_20261114/*/placar_dev_v3.csv   # reparo de recusa, só no DEV', limpar: true,
          argv: [PY, path.join(__dirname, 'mostrar.py'), 'placar', path.join(v3, 'dev_agente_20261114', 'sem_reparo', 'placar_dev_v3.csv'),
            path.join(v3, 'dev_agente_20261114', 'com_reparo', 'placar_dev_v3.csv')], ritmo_ms: 300, pausa_depois: 8 },
      ] };
      const arq = path.join(TRAB, 'genai_term.json');
      fs.writeFileSync(arq, JSON.stringify(roteiro, null, 1));
      const srv = spawn(PY, [path.join(__dirname, 'terminal_real.py'), arq, '--porta', '8772'], { stdio: 'ignore', windowsHide: true });
      try {
        await espera(1500);
        await gravar(nav, CENAS, 'genai_term', async (c, page) => {
          await page.goto('http://127.0.0.1:8772/');
          for (let i = 0; i < roteiro.comandos.length; i++) {
            await page.waitForFunction((i) => document.title === 'executando ' + i, i, { timeout: 60000 });
            c.marcar('cmd' + i);
            await page.waitForFunction((i) => document.title === 'pronto ' + i || document.title === 'FIM', i, { timeout: 60000 });
            c.marcar('ok' + i);
          }
          await page.waitForFunction(() => document.title === 'FIM', null, { timeout: 60000 });
          await espera(1200);
        });
      } finally {
        srv.kill();
      }
    }
  } finally {
    await nav.close();
  }
})().catch((e) => { console.error(e); process.exit(1); });

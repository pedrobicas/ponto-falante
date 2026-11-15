// Capturas reais do vídeo de RPA.
//   node scripts/video/cap_rpa.js <pasta das cenas> <pasta de trabalho> [cena...]
// A pasta de trabalho recebe uma cópia de rpa/ (o teste local não toca nos logs versionados) e o MVP de teste
// (rpa/tools/mock_mvp.py, dados SIMULADOS) roda só em 127.0.0.1. A produção é consultada apenas para leitura.
const { gravar, abrirNavegador, espera } = require('./captura.js');
const { spawn, execFileSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const RAIZ = path.resolve(__dirname, '..', '..');
const PY = path.join(RAIZ, '.venv', 'Scripts', 'python.exe');
const SITE = 'https://ponto-falante.onrender.com';
const [CENAS, TRAB] = process.argv.slice(2, 4);
const SO = process.argv.slice(4);
const quer = (n) => !SO.length || SO.includes(n);

function prepararCopia() {
  const demo = path.join(TRAB, 'rpa_demo');
  fs.rmSync(demo, { recursive: true, force: true });
  for (const n of ['src', 'config', 'data', 'tools']) fs.cpSync(path.join(RAIZ, 'rpa', n), path.join(demo, n), { recursive: true });
  return demo;
}

async function terminal(nav, nome, roteiro, porta) {
  if (!/^[a-z0-9_]+$/.test(nome)) throw new Error('nome de roteiro inválido: ' + nome);
  const arq = path.join(TRAB, nome + '.json');  // nosemgrep -- nome fixo do roteiro, validado na linha anterior
  fs.writeFileSync(arq, JSON.stringify(roteiro, null, 1));
  const srv = spawn(PY, [path.join(__dirname, 'terminal_real.py'), arq, '--porta', String(porta)], { stdio: 'ignore', windowsHide: true });
  try {
    await espera(1500);
    await gravar(nav, CENAS, nome, async (c, page) => {
      await page.goto(`http://127.0.0.1:${porta}/`);
      for (let i = 0; i < roteiro.comandos.length; i++) {
        await page.waitForFunction((i) => document.title === 'executando ' + i, i, { timeout: 120000 });
        c.marcar('cmd' + i);
        await page.waitForFunction((i) => document.title === 'pronto ' + i || document.title === 'FIM', i, { timeout: 180000 });
        c.marcar('ok' + i);
      }
      await page.waitForFunction(() => document.title === 'FIM', null, { timeout: 60000 });
      await espera(1500);
    });
  } finally {
    srv.kill();
  }
}

(async () => {
  fs.mkdirSync(CENAS, { recursive: true });
  fs.mkdirSync(TRAB, { recursive: true });
  const nav = await abrirNavegador();
  let mock = null;
  try {
    if (quer('rpa_site')) {
      await gravar(nav, CENAS, 'rpa_site', async (c, page) => {
        await page.goto(SITE + '/busca', { waitUntil: 'networkidle', timeout: 90000 });
        await espera(1200);
        c.marcar('busca');
        const campo = page.getByLabel('Nome do ponto, rua ou código');
        await c.clicar(campo);
        await c.digitar('Paulista 1374');
        await espera(400);
        await page.keyboard.press('Enter');
        await page.locator('a[href*="/ponto/"]').first().waitFor({ timeout: 30000 });
        await espera(900);
        c.marcar('resultado');
        await espera(1600);
        await c.clicar(page.locator('a[href*="/ponto/"]').first());
        await page.waitForURL(/\/ponto\//);
        await page.getByText(/min/).first().waitFor({ timeout: 40000 });
        await espera(800);
        c.marcar('previsoes');
        await espera(2500);
        await c.rolar(330, 1600);
        await espera(3500);
        c.marcar('fim_previsoes');
      });
    }

    // A cópia limpa só é recriada quando o terminal roda; rpa_html sozinho reaproveita a saída da execução anterior.
    const demo = quer('rpa_term') ? prepararCopia() : path.join(TRAB, 'rpa_demo');
    const env = { PYTHONPATH: 'src' };
    if (quer('rpa_term')) {
      mock = spawn(PY, ['-m', 'uvicorn', 'tools.mock_mvp:app', '--host', '127.0.0.1', '--port', '8232', '--log-level', 'warning'],
        { cwd: demo, env: Object.fromEntries(Object.entries(process.env).filter(([k]) => !['MVP_URL', 'RPA_API_KEY', 'MOCK_API_KEY', 'MOCK_FALHA'].includes(k))),
          stdio: 'ignore', windowsHide: true });
      await espera(3000);
      const local = { ...env, MVP_URL: 'http://127.0.0.1:8232' };
      await terminal(nav, 'rpa_term', {
        titulo: 'Robô RPA · Python 3.12', prompt: 'rpa>', comandos: [
          { mostrar: 'python scripts/video/mostrar.py regras config/monitoramento.yaml   # regras de decisão (YAML)',
            argv: [PY, path.join(__dirname, 'mostrar.py'), 'regras', path.join(demo, 'config', 'monitoramento.yaml')],
            ritmo_ms: 70, pausa_depois: 7 },
          { mostrar: 'python -m pf_rpa.coletor --somente-leitura   # consulta real à SPTrans via MVP publicado', limpar: true,
            argv: [PY, '-m', 'pf_rpa.coletor', '--somente-leitura'], cwd: demo, compacto: true, ritmo_ms: 120,
            env: { ...env, MVP_URL: SITE + '/api' }, pausa_depois: 5 },
          { mostrar: 'gh run list --limit 40 --json ...   # execuções reais dos robôs no GitHub Actions (horário UTC)', limpar: true,
            argv: ['gh', 'run', 'list', '--limit', '40', '--json', 'workflowName,createdAt,event,conclusion', '-q',
              String.raw`.[] | select(.workflowName | startswith("rpa")) | "\(.createdAt[0:16] | sub("T"; " "))   \(.workflowName)   \(.event)   \(.conclusion)"`],
            cwd: RAIZ, max_linhas: 8, ritmo_ms: 110, pausa_depois: 4.5 },
          { mostrar: 'set MVP_URL=http://127.0.0.1:8232 & python -m pf_rpa.robo --data 2026-11-13   # MVP local de teste', limpar: true,
            argv: [PY, '-m', 'pf_rpa.robo', '--data', '2026-11-13'], cwd: demo, compacto: true, ritmo_ms: 380,
            env: local, mostrar_codigo: true, pausa_depois: 6 },
          { mostrar: 'curl -X POST "http://127.0.0.1:8232/admin/falha?ativo=true"   # derruba a leitura do MVP local', limpar: true,
            argv: ['curl', '-s', '-X', 'POST', 'http://127.0.0.1:8232/admin/falha?ativo=true'], pausa_depois: 1.5 },
          { mostrar: 'python -m pf_rpa.robo --data 2026-11-13',
            argv: [PY, '-m', 'pf_rpa.robo', '--data', '2026-11-13'], cwd: demo, compacto: true, ritmo_ms: 120,
            env: local, mostrar_codigo: true, pausa_depois: 5 },
          { mostrar: 'python scripts/video/mostrar.py auditoria logs/auditoria.jsonl   # trilha de auditoria', limpar: true,
            argv: [PY, path.join(__dirname, 'mostrar.py'), 'auditoria', path.join(demo, 'logs', 'auditoria.jsonl')],
            ritmo_ms: 60, pausa_depois: 6 },
        ] }, 8771);
    }

    if (quer('rpa_html')) {
      const html = path.join(demo, 'saida', 'boletim_2026-11-13.html');
      if (!fs.existsSync(html)) throw new Error('rode antes a cena rpa_term (gera o boletim local)');
      await gravar(nav, CENAS, 'rpa_html', async (c, page) => {
        await page.goto('file:///' + html.replace(/\\/g, '/'));
        await espera(1200);
        c.marcar('topo');
        await c.mover(700, 360, 900);
        await espera(2500);
        await c.rolar(420, 1800);
        await espera(3500);
        c.marcar('fim');
      });
    }

    if (quer('rpa_mvp')) {
      await gravar(nav, CENAS, 'rpa_mvp', async (c, page) => {
        await page.goto(SITE + '/boletim', { waitUntil: 'networkidle', timeout: 90000 });
        await page.getByText(/Boletim de/).first().waitFor({ timeout: 45000 });
        await espera(1500);
        c.marcar('boletim');
        await c.mover(560, 300, 800);
        await espera(3500);
        await c.rolar(520, 1800);
        c.marcar('resumo');
        await espera(4000);
        await c.rolar(560, 1800);
        c.marcar('linhas');
        await espera(4500);
        c.marcar('assistente');
        await c.clicar(page.getByRole('link', { name: 'Assistente' }).first());
        await page.waitForURL(/assistente/);
        await espera(1200);
        const campo = page.getByPlaceholder('Escreva sua pergunta');
        await c.rolarAte(campo, 380);
        await c.clicar(campo);
        await c.digitar('Teve algum problema no transporte hoje?');
        await espera(400);
        const RESP = '.fala--assistente:not(.fala--processando)';
        const antes = await page.locator(RESP).count();
        c.marcar('pergunta');
        await page.keyboard.press('Enter');
        for (let k = 0; k < 400 && (await page.locator(RESP).count()) <= antes; k++) await espera(250);
        await espera(500);
        c.marcar('resposta');
        const ultima = page.locator(RESP).last();
        await c.rolarAte(ultima, 150, 1300);
        await espera(6500);
        c.marcar('fim_resposta');
      });
    }
  } finally {
    if (mock) mock.kill();
    await nav.close();
  }
})().catch((e) => { console.error(e); process.exit(1); });

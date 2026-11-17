// Capturas reais do vídeo de Visão Computacional.
//   node scripts/video/cap_visao.js <pasta das cenas> <pasta de trabalho> [cena...]
// Cenas do site publicado: fluxo COM sessão de embarque num ponto real (GTFS SPTrans) atendido pela 647P-10, e a
// foto do letreiro enviada pelo botão "Enviar uma foto do letreiro". O resultado vem do serviço de visão da equipe
// (via túnel); nada é encenado. O resultado de cada conferência (resposta da API, texto da tela, tempo) vai para
// <pasta das cenas>/<cena>/resultado.json.
// Cena de terminal: a API falsa roda em segundo plano (log em <pasta de trabalho>/api_fake.log) e o terminal mostra o
// demo.py de verdade na CPU, seguido das linhas "Detecção recebida" do log da API falsa.
const { gravar, abrirNavegador, espera } = require('./captura.js');
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

const RAIZ = path.resolve(__dirname, '..', '..');
const VISAO = path.join(RAIZ, 'visao');
const SITE = 'https://ponto-falante.onrender.com';
const PONTO = { busca: 'Avenida Brigadeiro Faria Lima 3015', codigo: '3407210' };
const DEMO = path.join(VISAO, 'amostras', 'imagens', 'demo');
const [CENAS, TRAB] = process.argv.slice(2, 4).map((p) => path.resolve(p));  // nosemgrep -- pastas de saída escolhidas pelo próprio operador na linha de comando
const NOME_SEGURO = /^[a-z0-9_]+$/;
const FOTO_SEGURA = /^[A-Za-z0-9_-]+\.jpg$/;
const SO = process.argv.slice(4);
const quer = (n) => !SO.length || SO.includes(n);

function pythonVisao() {
  for (const p of [path.join(RAIZ, '.venv-visao', 'Scripts', 'python.exe'),
    path.resolve(RAIZ, '..', '..', '.venv-visao', 'Scripts', 'python.exe')]) if (fs.existsSync(p)) return p;
  throw new Error('.venv-visao não encontrado');
}

async function conferencia(nav, nome, linha, foto) {
  if (!NOME_SEGURO.test(nome) || !FOTO_SEGURA.test(foto)) throw new Error('cena ou foto inválida: ' + nome + ' ' + foto);
  const info = { cena: nome, ponto: PONTO.codigo, linha_esperada: linha, foto };
  await gravar(nav, CENAS, nome, async (c, page) => {
    await page.goto(SITE + '/embarque', { waitUntil: 'networkidle', timeout: 120000 });
    await espera(1500);
    c.marcar('embarque');
    const campo = page.getByLabel('Ou digite o nome do ponto');
    await c.clicar(campo);
    await c.digitar(PONTO.busca);
    await espera(400);
    await c.clicar(page.getByRole('search', { name: 'Buscar ponto' }).getByRole('button', { name: 'Buscar' }));
    const opcao = page.locator('.opcao-ponto', { hasText: 'código ' + PONTO.codigo }).first();
    await opcao.waitFor({ timeout: 60000 });
    await espera(1400);
    c.marcar('pontos');
    await c.rolarAte(opcao, 260);
    await espera(500);
    await c.clicar(opcao);
    const sim = page.getByRole('button', { name: 'Sim, é este ponto' });
    await sim.waitFor({ timeout: 30000 });
    await espera(1300);
    await c.clicar(sim);
    const marcar = page.locator('label.opcao-linha', { hasText: linha }).first();
    await marcar.waitFor({ timeout: 60000 });
    await espera(1300);
    c.marcar('linhas');
    await c.rolarAte(marcar, 300);
    await espera(600);
    await c.clicar(marcar);
    await espera(900);
    const comecar = page.getByRole('button', { name: 'Começar a acompanhar' });
    await c.rolarAte(comecar, 380);
    await espera(500);
    await c.clicar(comecar);
    const conferir = page.getByRole('button', { name: 'Conferir o letreiro pela câmera' });
    await conferir.waitFor({ timeout: 60000 });
    await espera(1800);
    c.marcar('acompanhando');
    await c.rolarAte(conferir, 320);
    await espera(600);
    await c.clicar(conferir);
    const enviar = page.getByRole('button', { name: 'Enviar uma foto do letreiro' });
    await enviar.waitFor({ timeout: 60000 });
    await espera(1500);
    c.marcar('camera');
    await c.rolarAte(enviar, 330);
    await espera(600);
    const escolha = page.waitForEvent('filechooser', { timeout: 15000 });
    await c.clicar(enviar);
    const seletor = await escolha;
    const pedido = page.waitForRequest((r) => r.url().includes('/api/embarque/visao/conferir'), { timeout: 30000 });
    const resposta = page.waitForResponse((r) => r.url().includes('/api/embarque/visao/conferir'), { timeout: 120000 });
    await espera(700);
    await seletor.setFiles(path.join(DEMO, foto));  // nosemgrep -- foto fixa do roteiro, validada por FOTO_SEGURA
    const req = await pedido;
    const t0 = Date.now();
    c.marcar('enviada');
    const resp = await resposta;
    const t1 = Date.now();
    info.http = resp.status();
    info.resposta_api = await resp.json().catch(() => null);
    info.tempo_conferencia_ms = t1 - t0;
    info.tempo_pedido_navegador = req.timing();
    const res = page.locator('.camera__resultado');
    await res.waitFor({ timeout: 30000 });
    c.marcar('resultado');
    info.data_resultado = await res.getAttribute('data-resultado');
    info.texto_tela = (await res.innerText()).trim();
    await espera(900);
    // Deixa a foto e o resultado visíveis juntos.
    const previa = page.locator('.camera__previa');
    const bp = await previa.boundingBox();
    const br = await res.boundingBox();
    if (bp && br) await c.rolar(bp.y - Math.max(20, (720 - (br.y + br.height - bp.y)) / 2), 1300);
    await c.mover(1215, 640, 700);  // tira o cursor de cima do resultado
    await espera(4200);
    c.marcar('parado');
    await page.screenshot({ path: path.join(CENAS, '..', nome + '.png') });  // nosemgrep -- nome fixo da cena, validado por NOME_SEGURO
  });
  fs.writeFileSync(path.join(CENAS, nome, 'resultado.json'), JSON.stringify(info, null, 2));  // nosemgrep -- nome fixo da cena, validado por NOME_SEGURO
  console.log(nome, info.data_resultado, JSON.stringify(info.resposta_api), info.tempo_conferencia_ms + ' ms');
}

async function terminal(nav, nome, roteiro, porta) {
  if (!/^[a-z0-9_]+$/.test(nome)) throw new Error('nome de roteiro inválido: ' + nome);
  const arq = path.join(TRAB, nome + '.json');  // nosemgrep -- nome fixo do roteiro, validado na linha anterior
  fs.writeFileSync(arq, JSON.stringify(roteiro, null, 1));
  const srv = spawn(pythonVisao(), [path.join(__dirname, 'terminal_real.py'), arq, '--porta', String(porta)], { stdio: 'ignore', windowsHide: true });
  try {
    await espera(1500);
    await gravar(nav, CENAS, nome, async (c, page) => {
      await page.goto(`http://127.0.0.1:${porta}/`);
      for (let i = 0; i < roteiro.comandos.length; i++) {
        await page.waitForFunction((i) => document.title === 'executando ' + i, i, { timeout: 120000, polling: 200 });
        c.marcar('cmd' + i);
        await page.waitForFunction((i) => document.title === 'pronto ' + i || document.title === 'FIM', i, { timeout: 900000, polling: 200 });
        c.marcar('ok' + i);
      }
      await page.waitForFunction(() => document.title === 'FIM', null, { timeout: 60000 });
      await espera(1500);
    });
  } finally {
    srv.kill();
  }
}

async function cenaTerminal(nav) {
  const py = pythonVisao();
  const log = path.join(TRAB, 'api_fake.log');
  const saida = fs.openSync(log, 'w');
  const linhas = '647P-10,5109-10,2100-10,288,695H-10,8000-10';
  const api = spawn(py, ['src/api_fake.py', '--linhas', linhas], { cwd: VISAO, stdio: ['ignore', saida, saida], windowsHide: true,
    env: { ...process.env, PYTHONIOENCODING: 'utf-8', PYTHONUNBUFFERED: '1' } });
  try {
    await espera(2500);
    const video = path.join(CENAS, '..', 'demo_cpu.mp4');
    await terminal(nav, 'visao_terminal', {
      titulo: 'Visão computacional · YOLO11n + EasyOCR na CPU', prompt: 'visao>', comandos: [
        { mostrar: `python src/demo.py --fonte amostras/imagens/demo --ponto 260015039 --repetir-imagem 8 --saida ${video}`
            + `   # API falsa (--linhas ${linhas}) no terminal 1`,
          argv: [py, 'src/demo.py', '--fonte', 'amostras/imagens/demo', '--ponto', '260015039', '--repetir-imagem', '8', '--saida', video],
          cwd: VISAO, ritmo_ms: 120, mostrar_codigo: true, pausa_depois: 4 },
        { mostrar: 'findstr "Detec" api_fake.log   # o que a API falsa (terminal 1) recebeu',
          argv: ['findstr', 'Detec', 'api_fake.log'], cwd: TRAB, ritmo_ms: 260, pausa_depois: 5 },
      ] }, 8767);
  } finally {
    api.kill();
    fs.closeSync(saida);
  }
}

(async () => {
  fs.mkdirSync(CENAS, { recursive: true });
  fs.mkdirSync(TRAB, { recursive: true });
  const nav = await abrirNavegador();
  try {
    if (quer('visao_confere')) await conferencia(nav, 'visao_confere', '647P-10', '01_647P-10.jpg');
    if (quer('visao_outra_linha')) await conferencia(nav, 'visao_outra_linha', '477P-10', '01_647P-10.jpg');
    if (quer('visao_inconclusivo')) await conferencia(nav, 'visao_inconclusivo', '647P-10', '03_destino_sacoma.jpg');
    if (quer('visao_terminal')) await cenaTerminal(nav);
  } finally {
    await nav.close();
  }
})().catch((e) => { console.error(e); process.exit(1); });

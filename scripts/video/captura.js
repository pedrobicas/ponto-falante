// Captura de tela em alta qualidade para os vídeos de demonstração (sem áudio).
//
// Usa o screencast do DevTools (quadros JPEG nítidos, 1920x1080) em vez do gravador WebM do Playwright, que
// comprime demais o texto. Cada cena vira uma pasta com os quadros, o índice de tempos e as marcações de roteiro;
// a montagem final (zoom, cortes, transições e selos) é feita por scripts/video/compor.py.
//
// O cursor desenhado na página só acompanha os eventos reais de mouse do Playwright: nada é encenado.
const { chromium } = require('playwright-core');
const fs = require('fs');
const path = require('path');

const VIEWPORT = { width: 1280, height: 720 };
const ESCALA = 1.5; // 1280x720 CSS -> quadros 1920x1080
const espera = (ms) => new Promise((r) => setTimeout(r, ms));

const CURSOR = `(() => {
  if (window.__pfCursor) return; window.__pfCursor = true;
  const montar = () => {
    const c = document.createElement('div');
    c.innerHTML = '<svg width="24" height="30" viewBox="0 0 24 30"><path d="M3 2 L3 23 L8.6 17.8 L12.3 26.6 L16 25 L12.3 16.6 L20 16.6 Z" fill="#111" stroke="#fff" stroke-width="1.8" stroke-linejoin="round"/></svg>';
    Object.assign(c.style, { position: 'fixed', left: '0', top: '0', zIndex: '2147483647', pointerEvents: 'none',
      transform: 'translate(-200px,-200px)', filter: 'drop-shadow(0 1px 2px rgba(0,0,0,.4))' });
    document.documentElement.appendChild(c);
    let ultimo = null;
    try { ultimo = JSON.parse(sessionStorage.getItem('__pfCursor') || 'null'); } catch (e) {}
    const pos = (x, y) => { c.style.transform = 'translate(' + (x - 3) + 'px,' + (y - 2) + 'px)'; };
    if (ultimo) pos(ultimo[0], ultimo[1]);
    addEventListener('mousemove', (e) => { pos(e.clientX, e.clientY);
      try { sessionStorage.setItem('__pfCursor', JSON.stringify([e.clientX, e.clientY])); } catch (err) {} }, true);
    addEventListener('mousedown', (e) => {
      const r = document.createElement('div');
      Object.assign(r.style, { position: 'fixed', left: (e.clientX - 18) + 'px', top: (e.clientY - 18) + 'px', width: '36px',
        height: '36px', borderRadius: '50%', border: '3px solid rgba(255,183,0,.95)', zIndex: '2147483646', pointerEvents: 'none',
        transition: 'transform .5s ease-out, opacity .5s ease-out' });
      document.documentElement.appendChild(r);
      requestAnimationFrame(() => requestAnimationFrame(() => { r.style.transform = 'scale(1.9)'; r.style.opacity = '0'; }));
      setTimeout(() => r.remove(), 600);
    }, true);
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', montar); else montar();
})();`;

const suave = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);

class Cena {
  constructor(page, pasta) {
    this.page = page;
    this.pasta = pasta;
    this.marcas = [];
    this.quadros = [];
    this.mouse = { x: 640, y: 420 };
  }

  marcar(nome) {
    this.marcas.push({ nome, t: Date.now() / 1000 });
    console.log('  marca', nome);
  }

  async mover(x, y, ms = 650) {
    const { x: x0, y: y0 } = this.mouse;
    const passos = Math.max(8, Math.round(ms / 16));
    for (let i = 1; i <= passos; i++) {
      const k = suave(i / passos);
      await this.page.mouse.move(x0 + (x - x0) * k, y0 + (y - y0) * k);
      await espera(ms / passos);
    }
    this.mouse = { x, y };
  }

  async centro(alvo) {
    await alvo.scrollIntoViewIfNeeded();
    const b = await alvo.boundingBox();
    if (!b) throw new Error('elemento sem posição na tela');
    return { x: b.x + b.width / 2, y: b.y + b.height / 2 };
  }

  async clicar(alvo, ms = 700) {
    const { x, y } = await this.centro(alvo);
    await this.mover(x, y, ms);
    await espera(180);
    await this.page.mouse.down();
    await espera(70);
    await this.page.mouse.up();
    await espera(250);
  }

  async digitar(texto, base = 52) {
    for (const ch of texto) {
      await this.page.keyboard.type(ch);
      await espera(base + (ch === ' ' ? 35 : 0) + Math.round(Math.random() * 28));
    }
  }

  // Rolagem com aceleração e desaceleração, no documento ou num contêiner rolável.
  async rolar(delta, ms = 1200, seletor = null) {
    await this.page.evaluate(async ({ delta, ms, seletor }) => {
      const el = seletor ? document.querySelector(seletor) : document.scrollingElement;
      const inicio = el.scrollTop, t0 = performance.now();
      const f = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
      await new Promise((ok) => { const passo = (agora) => { const k = Math.min(1, (agora - t0) / ms);
        el.scrollTop = inicio + delta * f(k); if (k < 1) requestAnimationFrame(passo); else ok(); }; requestAnimationFrame(passo); });
    }, { delta, ms, seletor });
  }

  async rolarAte(alvo, folga = 120, ms = 1100) {
    const b = await alvo.boundingBox();
    if (!b) return;
    const delta = b.y - folga;
    if (Math.abs(delta) > 4) await this.rolar(delta, ms);
  }
}

async function gravar(navegador, raiz, nome, roteiro, opcoes = {}) {
  const pasta = path.join(raiz, nome);
  fs.rmSync(pasta, { recursive: true, force: true });
  fs.mkdirSync(path.join(pasta, 'q'), { recursive: true });
  const ctx = await navegador.newContext({ viewport: opcoes.viewport || VIEWPORT, deviceScaleFactor: ESCALA, locale: 'pt-BR',
    timezoneId: 'America/Sao_Paulo', colorScheme: opcoes.esquema || 'light', reducedMotion: 'no-preference' });
  await ctx.addInitScript(CURSOR);
  const page = await ctx.newPage();
  const cena = new Cena(page, pasta);
  const cdp = await ctx.newCDPSession(page);
  let n = 0;
  const gravacoes = [];
  cdp.on('Page.screencastFrame', (f) => {
    const arquivo = String(n++).padStart(6, '0') + '.jpg';
    cena.quadros.push({ t: f.metadata.timestamp, a: arquivo });
    gravacoes.push(fs.promises.writeFile(path.join(pasta, 'q', arquivo), Buffer.from(f.data, 'base64')));
    cdp.send('Page.screencastFrameAck', { sessionId: f.sessionId }).catch(() => {});
  });
  if (opcoes.antes) await opcoes.antes(page);
  await cdp.send('Page.startScreencast', { format: 'jpeg', quality: 93, maxWidth: 1920, maxHeight: 1080, everyNthFrame: 1 });
  cena.marcar('inicio');
  let erro = null;
  try {
    await roteiro(cena, page);
  } catch (e) {
    erro = e;
  }
  cena.marcar('fim');
  await espera(300);
  await cdp.send('Page.stopScreencast').catch(() => {});
  await Promise.all(gravacoes);
  await ctx.close();
  fs.writeFileSync(path.join(pasta, 'indice.json'), JSON.stringify({ quadros: cena.quadros, marcas: cena.marcas }, null, 0));
  console.log(`cena ${nome}: ${cena.quadros.length} quadros, ${(cena.marcas.at(-1).t - cena.marcas[0].t).toFixed(1)} s`);
  if (erro) throw erro;
}

async function abrirNavegador() {
  return chromium.launch({ channel: 'msedge', headless: true, args: ['--hide-scrollbars', '--force-color-profile=srgb', '--force-device-scale-factor=1.5'] });
}

module.exports = { gravar, abrirNavegador, espera };

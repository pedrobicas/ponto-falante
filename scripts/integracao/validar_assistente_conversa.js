// Playwright CLI: run-code --filename scripts/integracao/validar_assistente_conversa.js
// Iniciar no servidor local. Prepara a própria conversa e não depende de histórico anterior.
async (page) => {
  const resultados = { telas: [], conversa: [], voz: null };
  const erros = [];
  const erro = e => erros.push(e.message);
  page.on('pageerror', erro);
  async function perguntar(pergunta, verificar) {
    await page.waitForFunction(() => document.querySelector('[role="log"]')?.getAttribute('aria-busy') === 'false');
    await page.getByRole('textbox', { name: 'Sua pergunta' }).fill(pergunta);
    // A primeira chamada ao modelo local pode demorar mais que o padrão de 30 s do navegador.
    const resposta = page.waitForResponse(r => r.url().endsWith('/api/chat') && r.request().method() === 'POST', { timeout: 150_000 });
    await page.getByRole('button', { name: 'Enviar pergunta', exact: true }).click();
    const http = await resposta;
    const r = await http.json();
    if (!http.ok() || !verificar(r)) throw new Error(`Conversa falhou: ${pergunta}: ${JSON.stringify(r)}`);
    // Receber o HTTP não significa que Angular já aplicou texto e contexto.
    await page.waitForFunction(texto => {
      const log = document.querySelector('[role="log"]');
      return log?.getAttribute('aria-busy') === 'false' && log.lastElementChild?.textContent.includes(texto);
    }, r.resposta);
    resultados.conversa.push({ pergunta, origem: r.origem, disponivel: r.disponivel, contexto: r.contexto, ms: r.latencia_ms, enviado: http.request().postDataJSON().contexto });
    return r;
  }
  try {
    await page.goto(new URL('/assistente', page.url()).href);
    await perguntar('Quais linhas passam no ponto 70016916?', r => r.contexto.ponto === 70016916);
    await perguntar('sentido 1 da linha 875A-10', r => r.contexto.sentido === 1 && r.resposta.includes('70 paradas'));
    await page.getByRole('link', { name: 'Ver paradas e previsões', exact: true }).click();
    await page.getByRole('searchbox', { name: 'Encontre sua parada' }).fill('Paulista 1374');
    await page.getByRole('button', { name: /1374/ }).click();
    await page.waitForFunction(() => !!document.querySelector('.linha__selecionada') && !document.querySelector('.linha__selecionada [role="status"]'));
    await page.route('**/__test-axe.js', route => route.fulfill({ path: 'frontend/node_modules/axe-core/axe.min.js', contentType: 'application/javascript' }));
    async function auditar(nome) {
      if (!(await page.evaluate(() => !!window.axe))) await page.addScriptTag({ url: '/__test-axe.js' });
      const r = await page.evaluate(async () => ({
        overflow: document.documentElement.scrollWidth > innerWidth + 1,
        falhas: (await axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa'] } })).violations.map(v => ({ id: v.id, impacto: v.impact, elementos: v.nodes.length })),
      }));
      resultados.telas.push({ nome, ...r });
      await page.screenshot({ path: `output/playwright/conversa-14-${nome}.png`, fullPage: true });
      if (r.overflow || r.falhas.length) throw new Error(`${nome}: ${JSON.stringify(r)}`);
    }
    await page.setViewportSize({ width: 1365, height: 900 });
    await auditar('linha-desktop');
    await page.setViewportSize({ width: 375, height: 812 });
    await auditar('linha-mobile');
    await page.evaluate(() => document.documentElement.style.setProperty('--escala-fonte', '1.75'));
    await auditar('linha-mobile-175');
    await page.evaluate(() => document.documentElement.style.removeProperty('--escala-fonte'));
    await page.getByRole('link', { name: 'Assistente', exact: true }).click();
    if (!(await page.getByRole('log').textContent()).includes('70 paradas')) throw new Error('Histórico perdido ao navegar.');
    await page.setViewportSize({ width: 1365, height: 900 });
    await auditar('chat-desktop');
    const itinerario = await (await page.request.get(new URL('/api/linhas/875A-10/paradas', page.url()).href)).json();
    const paradasVolta = new Set(itinerario.sentidos.find(s => s.sentido === 2).paradas.map(p => p.codigo));
    const volta = await perguntar('e no sentido contrário?', r => r.contexto.sentido === 2
      && r.contexto.ponto !== 70016916 && paradasVolta.has(r.contexto.ponto));
    await perguntar('e o próximo?', r => r.origem === 'TEMPO_REAL' && r.contexto.sentido === 2
      && r.contexto.linha === '875A-10' && r.contexto.ponto === volta.contexto.ponto);
    await perguntar('Quais linhas passam no ponto 70016916?', r => r.resposta.includes('875A-10'));
    await perguntar('e o próximo?', r => r.origem === 'TEMPO_REAL' && r.contexto.linha === null && r.contexto.ponto === 70016916);
    await perguntar('Tenho 69 anos. Posso usar o ônibus municipal com RG?', r => r.disponivel && !r.nao_consta && r.fontes.length > 0);
    await page.evaluate(() => {
      if (!window.speechSynthesis) return;
      window.__falarConversaOriginal = speechSynthesis.speak.bind(speechSynthesis);
      speechSynthesis.speak = u => { window.__falaValidada = { idioma: u.lang, caracteres: u.text.length }; window.__falarConversaOriginal(u); };
    });
    await page.getByRole('button', { name: 'Ouvir resposta', exact: true }).last().click();
    resultados.voz = await page.evaluate(() => window.__falaValidada || null);
    await page.evaluate(() => speechSynthesis?.cancel());
    await page.setViewportSize({ width: 375, height: 812 });
    await auditar('chat-mobile');
    await page.evaluate(() => document.documentElement.style.setProperty('--escala-fonte', '1.75'));
    await auditar('chat-mobile-175');
    await page.evaluate(() => document.documentElement.style.removeProperty('--escala-fonte'));
    // Falha HTTP injetada apenas nesta página: não derruba os serviços reais.
    await page.route('**/api/chat', route => route.fulfill({ status: 503, contentType: 'application/json', body: '{}' }));
    await page.getByRole('textbox', { name: 'Sua pergunta' }).fill('Como funciona o bilhete?');
    await page.getByRole('button', { name: 'Enviar pergunta', exact: true }).click();
    await page.getByRole('button', { name: 'Tentar de novo', exact: true }).waitFor();
    await auditar('chat-indisponivel');
    resultados.errosJavascript = erros;
    if (erros.length) throw new Error('Erros de JavaScript: ' + erros.join(';'));
    return resultados;
  } finally {
    page.off('pageerror', erro);
    await page.unroute('**/api/chat');
    await page.unroute('**/__test-axe.js');
    await page.evaluate(() => {
      if (window.__falarConversaOriginal) speechSynthesis.speak = window.__falarConversaOriginal;
      document.documentElement.style.removeProperty('--escala-fonte');
    });
  }
}

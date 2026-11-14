// Playwright CLI: run-code --filename scripts/integracao/validar_boletim_chat.js
// Pré-condição: abrir o MVP local com um boletim publicado pelo robô.
async (page) => {
  const resultado = { telas: [], voz: null, chat: null, erros: [] };
  const erro = e => resultado.erros.push(e.message);
  page.on('pageerror', erro);
  await page.route('**/__test-axe.js', route => route.fulfill({ path: 'frontend/node_modules/axe-core/axe.min.js', contentType: 'application/javascript' }));
  async function auditar(nome) {
    if (!(await page.evaluate(() => !!window.axe))) await page.addScriptTag({ url: '/__test-axe.js' });
    const estado = await page.evaluate(async () => ({
      overflow: document.documentElement.scrollWidth > innerWidth + 1,
      falhas: (await axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa'] } })).violations.map(v => v.id),
    }));
    resultado.telas.push({ nome, ...estado });
    await page.screenshot({ path: `output/playwright/boletim-14-${nome}.png`, fullPage: true });
    if (estado.overflow || estado.falhas.length) throw new Error(JSON.stringify({ nome, ...estado }));
  }
  try {
    await page.goto(new URL('/boletim', page.url()).href);
    await page.getByRole('button', { name: 'Ouvir resumo', exact: true }).waitFor();
    await page.setViewportSize({ width: 1365, height: 900 });
    await auditar('desktop');
    await page.setViewportSize({ width: 375, height: 812 });
    await page.evaluate(() => document.documentElement.style.setProperty('--escala-fonte', '1.75'));
    await auditar('mobile-175');
    await page.evaluate(() => {
      window.__falarOriginal = speechSynthesis.speak.bind(speechSynthesis);
      speechSynthesis.speak = u => { window.__vozRpa = { idioma: u.lang, texto: u.text }; window.__falarOriginal(u); };
    });
    await page.getByRole('button', { name: 'Ouvir resumo', exact: true }).click();
    resultado.voz = await page.evaluate(() => window.__vozRpa);
    if (resultado.voz?.idioma !== 'pt-BR') throw new Error('Voz não recebeu texto em pt-BR.');
    await page.evaluate(() => { speechSynthesis.cancel(); speechSynthesis.speak = window.__falarOriginal; document.documentElement.style.removeProperty('--escala-fonte'); });
    await page.getByRole('link', { name: 'Assistente', exact: true }).click();
    await page.getByRole('textbox', { name: 'Sua pergunta' }).fill('O que diz o boletim de hoje?');
    const resposta = page.waitForResponse(r => r.url().endsWith('/api/chat') && r.request().method() === 'POST');
    await page.getByRole('button', { name: 'Enviar pergunta', exact: true }).click();
    const r = await (await resposta).json();
    if (r.origem !== 'BOLETIM') throw new Error('Pergunta de boletim não usou o RPA.');
    resultado.chat = { origem: r.origem, natureza: r.natureza_dados };
    await page.waitForFunction(() => document.querySelector('[role="log"]')?.getAttribute('aria-busy') === 'false');
    const selo = await page.locator('.troca').last().locator('pf-origem').textContent();
    const esperado = { ESTIMADO: 'Estimado', SIMULADO: 'SIMULADO', INDISPONIVEL: 'Indisponível' }[r.natureza_dados];
    if (!esperado || !selo.includes(esperado)) throw new Error('Selo diverge da classificação recebida.');
    await auditar('chat-mobile');
    await page.getByRole('link', { name: 'Abrir o boletim', exact: true }).click();
    await page.getByRole('button', { name: 'Ouvir resumo', exact: true }).waitFor();
    await page.getByRole('link', { name: 'Assistente', exact: true }).click();
    if (!(await page.getByRole('log').textContent()).includes(r.resposta)) throw new Error('Histórico perdido ao navegar.');
    await page.route('**/api/boletim', route => route.fulfill({ status: 503, contentType: 'application/json', body: '{}' }));
    await page.getByRole('link', { name: 'Boletim', exact: true }).click();
    await page.getByText('Não foi possível abrir o boletim', { exact: true }).waitFor();
    await auditar('falha-backend');
    return resultado;
  } finally {
    page.off('pageerror', erro);
    await page.unroute('**/api/boletim');
    await page.unroute('**/__test-axe.js');
  }
}

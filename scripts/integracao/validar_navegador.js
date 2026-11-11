// Playwright CLI: run-code --filename scripts/integracao/validar_navegador.js
async (page) => {
  const base = 'http://127.0.0.1:8080';
  const resultados = { paginas: [], voz: null, mobile: null, chat: null };
  await page.addInitScript({ path: 'frontend/node_modules/axe-core/axe.min.js' });
  await page.addInitScript(() => {
    if (!window.speechSynthesis) return;
    const original = window.speechSynthesis.speak.bind(window.speechSynthesis);
    window.speechSynthesis.speak = fala => {
      window.__vozTeste = { idioma: fala.lang, textoNaoVazio: !!fala.text.trim() };
      original(fala); // Encaminha ao sintetizador real, sem substituir a reproducao.
    };
  });
  async function auditar(nome) {
    const falhas = await page.evaluate(async () => (await axe.run(document, {
      runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa'] },
    })).violations.map(v => ({ id: v.id, impacto: v.impact, elementos: v.nodes.length })));
    resultados.paginas.push({ nome, falhas });
    if (falhas.length) throw new Error('Acessibilidade em ' + nome + ': ' + JSON.stringify(falhas));
  }
  await page.goto(base);
  await page.getByRole('heading', { name: 'Qual ônibus você espera?' }).waitFor();
  await auditar('inicio');
  await page.getByRole('searchbox').fill('paulista');
  await page.getByRole('button', { name: 'Buscar ponto' }).click();
  await page.getByRole('link', { name: /Paulista - Museu/ }).click();
  await page.getByRole('button', { name: 'Ouvir próximos ônibus' }).waitFor();
  if (!(await page.locator('main').textContent()).includes('horários simulados')) {
    throw new Error('Origem demonstrativa ausente no ponto.');
  }
  await auditar('previsoes');
  await page.screenshot({ path: 'output/playwright/previsoes-desktop.png', fullPage: true });
  await page.getByRole('link', { name: 'Ajustes', exact: true }).click();
  await page.getByRole('radio', { name: 'Grande', exact: true }).check();
  await page.getByRole('radio', { name: /Alto contraste escuro/ }).check();
  await page.reload();
  await page.getByRole('radio', { name: 'Grande', exact: true }).waitFor();
  if (!(await page.getByRole('radio', { name: 'Grande', exact: true }).isChecked())) {
    throw new Error('Preferencia de fonte nao persistiu.');
  }
  if (!(await page.getByRole('radio', { name: /Alto contraste escuro/ }).isChecked())) {
    throw new Error('Preferencia de contraste nao persistiu.');
  }
  const voz = page.getByRole('button', { name: 'Testar a voz' });
  if (await voz.isEnabled()) {
    await voz.click();
    resultados.voz = await page.evaluate(() => window.__vozTeste);
    if (resultados.voz?.idioma !== 'pt-BR' || !resultados.voz?.textoNaoVazio) {
      throw new Error('Texto nao foi encaminhado para sintese em pt-BR.');
    }
  } else resultados.voz = { suportada: false };
  await auditar('acessibilidade-alto-contraste');
  await page.getByRole('link', { name: 'Boletim', exact: true }).click();
  await page.getByRole('button', { name: 'Ouvir resumo' }).waitFor();
  await auditar('boletim');
  await page.getByRole('link', { name: 'Assistente', exact: true }).click();
  await page.getByRole('textbox').waitFor();
  await page.getByRole('textbox').fill('Quais documentos preciso para solicitar o Bilhete Unico da Pessoa com Deficiencia?');
  const aguardarResposta = page.waitForResponse(r => r.url().endsWith('/api/chat') && r.request().method() === 'POST', { timeout: 60000 });
  await page.getByRole('button', { name: 'Enviar pergunta' }).click();
  const respostaHttp = await aguardarResposta;
  const respostaChat = await respostaHttp.json();
  if (respostaHttp.status() !== 200 || typeof respostaChat.disponivel !== 'boolean') {
    throw new Error('Contrato publico do chat invalido.');
  }
  await page.getByText('Você perguntou:', { exact: true }).waitFor();
  resultados.chat = { http: respostaHttp.status(), disponivel: respostaChat.disponivel,
    nao_consta: respostaChat.nao_consta, fontes: respostaChat.fontes.length };
  await auditar('assistente');
  await page.getByRole('link', { name: 'Sobre', exact: true }).click();
  await page.getByRole('heading', { name: 'Sobre o Ponto Falante' }).waitFor();
  await auditar('sobre');
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(base);
  await page.getByRole('heading', { name: 'Qual ônibus você espera?' }).waitFor();
  resultados.mobile = await page.evaluate(() => ({
    largura: document.documentElement.clientWidth,
    conteudo: document.documentElement.scrollWidth,
  }));
  if (resultados.mobile.conteudo > resultados.mobile.largura) throw new Error('Rolagem horizontal no mobile.');
  await auditar('inicio-mobile');
  await page.screenshot({ path: 'output/playwright/inicio-mobile.png', fullPage: true });
  await page.getByRole('link', { name: 'Pular para o conteúdo' }).focus();
  await page.keyboard.press('Enter');
  if (!(await page.evaluate(() => document.activeElement?.tagName === 'H1'))) {
    throw new Error('Atalho de teclado nao levou foco ao titulo.');
  }
  return resultados;
}

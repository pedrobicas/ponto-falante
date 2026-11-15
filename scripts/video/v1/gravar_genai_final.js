// Captura real de produção. Sem respostas injetadas, sem áudio e sem avaliação final.
// NODE_PATH deve apontar para node_modules que contém playwright-core.
const { chromium } = require('playwright-core');
const fs = require('fs');
const path = require('path');
const root = path.resolve(__dirname, '../..');
const out = path.resolve(root, process.argv[2] || 'output/playwright/genai-final');
const site = 'https://ponto-falante.onrender.com';
fs.mkdirSync(out, { recursive: true });
const evidence = { site, gravado_em: new Date().toISOString(), cenas: [] };
const pause = ms => new Promise(r => setTimeout(r, ms));

(async () => {
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  const api = await browser.newContext();
  for (const [label, route] of [['status','/api/status'],['saude','/actuator/health']]) {
    evidence[label] = await (await api.request.get(site + route)).json();
  }
  await api.close();
  async function scene(name, fn) {
    const ctx = await browser.newContext({ viewport:{width:1280,height:720}, recordVideo:{dir:out,size:{width:1280,height:720}}, locale:'pt-BR', colorScheme:'light' });
    const page = await ctx.newPage();
    const t0 = Date.now();
    const s = {name, eventos:[], respostas:[]}; evidence.cenas.push(s);
    const mark = label => { const x={label,segundo:(Date.now()-t0)/1000};s.eventos.push(x);console.log(name,JSON.stringify(x)); };
    async function snap(label) { await page.screenshot({path:path.join(out,name+'-'+label+'.png')});mark(label); }
    async function ask(q) {
      mark('digitar: '+q);
      const input=page.getByRole('textbox',{name:'Sua pergunta'});
      await input.scrollIntoViewIfNeeded();
      await input.pressSequentially(q,{delay:30});
      await pause(700);
      const response=page.waitForResponse(r=>r.url().endsWith('/api/chat')&&r.request().method()==='POST',{timeout:150000});
      await input.press('Enter');mark('enviada');
      const r=await response; const json=await r.json();
      s.respostas.push({pergunta:q,http:r.status(),...json});mark('resposta');
      await page.waitForFunction(()=>document.querySelector('[role="log"]')?.getAttribute('aria-busy')==='false');
      await page.locator('.troca').last().evaluate(e=>e.scrollIntoView({behavior:'smooth',block:'start'}));
      await pause(750);await snap('resposta-'+s.respostas.length);await pause(7000);
      return json;
    }
    try { await fn(page,ask,mark,snap,s); }
    finally {
      mark('fim');
      const video=page.video();await ctx.close();
      const target=path.join(out,name+'.webm');
      if(fs.existsSync(target)) throw new Error('Preservar arquivo existente: '+target);
      await video.saveAs(target);await video.delete();
      fs.writeFileSync(path.join(out,'captura.json'),JSON.stringify(evidence,null,2));
    }
  }
  try {
    await scene('genai-direitos',async(page,ask,mark,snap,s)=>{
      await page.goto(site+'/assistente',{waitUntil:'networkidle'});mark('pagina pronta');await pause(3000);
      const r=await ask('Tenho 66 anos, posso andar gratuitamente?');
      if(!r.disponivel) throw new Error('GenAI indisponível: preservar esta tentativa e diagnosticar antes de repetir.');
      if(r.fontes?.length) {
        await page.locator('.citacoes summary').last().click();
        await page.locator('.citacoes').last().evaluate(e=>e.scrollIntoView({behavior:'smooth',block:'center'}));
        await pause(800);await snap('fontes');await pause(8000);
      }
      // Observa a chamada real da Web Speech API e conserva sua execução original.
      await page.evaluate(()=>{const original=speechSynthesis.speak.bind(speechSynthesis);speechSynthesis.speak=u=>{window.__vozDemo={idioma:u.lang,texto:u.text};original(u);};});
      await page.getByRole('button',{name:'Ouvir resposta',exact:true}).last().click();mark('ouvir');await pause(3000);
      s.voz=await page.evaluate(()=>window.__vozDemo);await snap('voz');
      await page.evaluate(()=>speechSynthesis.cancel());
      await ask('E meu acompanhante?');
      await page.getByRole('link',{name:'Ajustes',exact:true}).click();await pause(1800);
      await page.getByRole('radio',{name:'Grande',exact:true}).check();await pause(2000);await snap('letras');
      await page.getByText('Cores e contraste',{exact:true}).first().click();
      await page.getByRole('radio',{name:/Alto contraste escuro/}).check();await pause(2500);await snap('contraste');
      await page.getByRole('link',{name:'Assistente',exact:true}).click();await pause(1800);
      await page.locator('.troca').first().evaluate(e=>e.scrollIntoView({behavior:'smooth',block:'start'}));await pause(2000);await snap('historico');await pause(4500);
      s.historico_preservado=(await page.locator('.troca').count())===2;
      s.overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1);
    });
    await scene('genai-limite',async(page,ask)=>{
      await page.goto(site+'/assistente',{waitUntil:'networkidle'});await pause(1200);
      await ask('Posso levar meu cachorro no ônibus em Curitiba?');
    });
    await scene('genai-boletim',async(page,ask)=>{
      await page.goto(site+'/assistente',{waitUntil:'networkidle'});await pause(1200);
      await ask('Existe algum problema ou ocorrência no transporte hoje?');
    });
  } finally { await browser.close(); }
  console.log('Captura finalizada:',path.join(out,'captura.json'));
})().catch(e=>{console.error(e);process.exit(1);});

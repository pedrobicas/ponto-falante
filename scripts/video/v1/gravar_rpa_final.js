// Capturas reais RPA, sem áudio. NODE_PATH deve apontar para playwright-core instalado.
const { chromium } = require('playwright-core');
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');
const ROOT = path.resolve(__dirname, '../..');
const WORK = path.join(ROOT, '.validation/video-rpa-final');
const OUT = path.join(ROOT, 'output/playwright/rpa-video-final');
const PY = path.join(ROOT, '.venv/Scripts/python.exe');
const wait = ms => new Promise(r => setTimeout(r, ms));
const marks = {};

async function scene(browser, name, fn) {
  const ctx = await browser.newContext({ viewport: { width:1280, height:720 }, recordVideo:{dir:OUT,size:{width:1280,height:720}}, locale:'pt-BR' });
  const page = await ctx.newPage();
  const began = Date.now();
  marks[name] = {};
  const mark = key => { marks[name][key] = (Date.now()-began)/1000; };
  try { await fn(page, mark); }
  finally {
    const v = page.video();
    await ctx.close();
    const target = path.join(OUT, name+'.webm');
    if (fs.existsSync(target)) throw new Error('Preservar bruto existente: '+target);
    await v.saveAs(target); await v.delete();
    fs.writeFileSync(path.join(OUT,'marcacoes.json'), JSON.stringify(marks,null,2));
    fs.writeFileSync(path.join(OUT,name+'-marcacoes.json'), JSON.stringify(marks[name],null,2));
    console.log('gravado',name,JSON.stringify(marks[name]));
  }
}

async function terminal(browser, mode, hold, port) {
  const json = {prompt:'rpa>',comandos:[{mostrar:`python scripts/video/rpa_inspecionar.py ${mode}`,argv:[PY,path.join(__dirname,'rpa_inspecionar.py'),mode],cwd:ROOT,pausa_depois:0.2}]};
  const roteiro = path.join(WORK,mode+'.json');
  fs.writeFileSync(roteiro,JSON.stringify(json,null,2));
  const proc = spawn(PY,[path.join(__dirname,'terminal_real.py'),roteiro,'--porta',String(port)],{stdio:'ignore',windowsHide:true});
  try {
    await wait(1000);
    await scene(browser,mode,async(page,mark)=>{
      await page.goto(`http://127.0.0.1:${port}`);
      await page.addStyleTag({content:"#t{font-size:21px;line-height:1.35;padding:22px 28px;color:#e9eef3;background:#101922}.p{color:#81d6b7}.c{color:#fff}"});
      mark('pronto');
      await page.waitForFunction(()=>document.title==='FIM',null,{timeout:90000});
      mark('resultado');
      await page.screenshot({path:path.join(OUT,mode+'.png')});
      await wait(hold*1000);
    });
  } finally { proc.kill(); }
}

async function main() {
  fs.mkdirSync(WORK,{recursive:true}); fs.mkdirSync(OUT,{recursive:true});
  const browser = await chromium.launch({channel:'msedge',headless:true});
  let mock;
  try {
    const only = process.argv[2] || 'all';
    if (only==='all'||only==='site') {
      await scene(browser,'producao-live',async(page,mark)=>{
        await page.goto('https://ponto-falante.onrender.com/boletim',{waitUntil:'domcontentloaded',timeout:60000});
        await page.getByRole('heading',{name:/Resumo do transporte|Boletim/i}).first().waitFor({timeout:45000});
        await page.waitForTimeout(3000);
        await page.screenshot({path:path.join(OUT,'producao-topo.png')});
        fs.writeFileSync(path.join(OUT,'producao-texto.txt'),await page.locator('body').innerText());
        mark('carregado'); await wait(11000);
        for (let i=0;i<12;i++){await page.mouse.wheel(0,55);await wait(130);}
        mark('resumo'); await wait(9000);
        await page.screenshot({path:path.join(OUT,'producao-resumo.png')});
        for(let i=0;i<10;i++){await page.mouse.wheel(0,55);await wait(130);}
        mark('linhas'); await wait(9000);
        await page.screenshot({path:path.join(OUT,'producao-linhas.png')});
        await page.evaluate(()=>window.scrollTo({top:0,behavior:'smooth'})); await wait(2000);
        mark('final'); await wait(8000);
      });
    }
    if (only==='all'||only==='terminal') {
      for (const [mode,hold] of [['regras',12],['codigo',8],['coleta',12],['sucesso',12]]) await terminal(browser,mode,hold,8781);
      const env={...process.env,PYTHONPATH:path.join(ROOT,'rpa')};
      for(const key of ['MVP_URL','RPA_API_KEY','MOCK_API_KEY']) delete env[key];
      mock=spawn(PY,['-m','uvicorn','tools.mock_mvp:app','--host','127.0.0.1','--port','8232','--log-level','warning'],{cwd:path.join(ROOT,'rpa'),env,stdio:'ignore',windowsHide:true});
      await wait(2200);
      await terminal(browser,'falha',9,8781);
      await terminal(browser,'auditoria',12,8781);
    }
  } finally {if(mock)mock.kill();await browser.close();}
}
main().catch(e=>{console.error(e);process.exit(1);});

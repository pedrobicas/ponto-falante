"""Terminal de gravação: executa comandos REAIS de uma lista fixa e mostra a saída verdadeira numa página legível.

    python scripts/video/terminal_real.py roteiro.json --porta 8765

Serve só em 127.0.0.1 e só executa os comandos do roteiro (argv fixos, sem shell); a página não envia comando algum.
O texto exibido é a saída do processo no momento da gravação. Para caber na tela em fonte grande, as linhas de log
podem ser compactadas (carimbo de data e nome do módulo viram só a hora) e reveladas com um pequeno ritmo por linha.

roteiro.json: {"titulo": "...", "prompt": "rpa>", "comandos": [{"mostrar": "texto digitado", "argv": [...], "cwd": "...",
               "env": {...}, "filtro": "regex", "compacto": true, "ritmo_ms": 220, "max_linhas": 0,
               "limpar": true, "mostrar_codigo": false, "pausa_depois": 2.0}]}
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PAGINA = r"""<!doctype html><html lang="pt-BR"><meta charset="utf-8"><title>terminal</title>
<style>
html,body{margin:0;height:100%;background:#e9ecef}
.janela{position:absolute;inset:26px 30px;background:#101318;border-radius:14px;box-shadow:0 18px 50px rgba(0,0,0,.28);
 display:flex;flex-direction:column;overflow:hidden}
.barra{height:44px;flex:none;display:flex;align-items:center;gap:9px;padding:0 18px;background:#1b1f26;color:#aeb6c2;
 font:600 15px 'Segoe UI',sans-serif}
.barra i{width:13px;height:13px;border-radius:50%;display:inline-block}
.barra span{margin-left:12px}
#t{flex:1;overflow:hidden;padding:20px 26px;color:#e8ebef;font:19px/1.55 'Cascadia Mono','Cascadia Code',Consolas,monospace;
 white-space:pre-wrap;word-break:break-word}
.p{color:#5fd38d;font-weight:700}.c{color:#fff;font-weight:700}.k{color:#8b949e}
.h{color:#8b949e}.w{color:#ffcf5c}.e{color:#ff7b72}.ok{color:#5fd38d;font-weight:700}
.crit{color:#ff7b72;font-weight:700}.aten{color:#ffcf5c;font-weight:700}.dest{color:#79c0ff}
.linha{display:block;animation:surge .25s ease-out}
@keyframes surge{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:none}}
.cursor{display:inline-block;width:10px;height:21px;background:#e8ebef;vertical-align:-3px;animation:pisca 1s steps(1) infinite}
@keyframes pisca{50%{opacity:0}}
</style>
<div class="janela"><div class="barra"><i style="background:#ff5f57"></i><i style="background:#febc2e"></i>
<i style="background:#28c840"></i><span id="titulo"></span></div><div id="t"></div></div>
<script>
const t=document.getElementById('t');const espera=ms=>new Promise(r=>setTimeout(r,ms));
const esc=s=>s.replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
function fim(){t.scrollTop=t.scrollHeight}
function realce(txt){let h=esc(txt);
 h=h.replace(/^(\d\d:\d\d:\d\d)/,'<span class="h">$1</span>');
 h=h.replace(/\b(CRITICA|CRÍTICA)\b/g,'<span class="crit">$1</span>').replace(/\b(ATENCAO|ATENÇÃO)\b/g,'<span class="aten">$1</span>');
 h=h.replace(/(-&gt; )OK\b/g,'$1<span class="ok">OK</span>').replace(/\b(status=sucesso\w*|código=0|success)\b/g,'<span class="ok">$1</span>');
 h=h.replace(/(#.*)$/,'<span class="k">$1</span>');
 return h}
function linha(txt){const s=document.createElement('span');s.className='linha';
 if(/ERRO|ERROR|Traceback|código=2|código de saída: [1-9]/.test(txt))s.classList.add('e');
 else if(/AVISO|WARNING|tentativa/.test(txt))s.classList.add('w');
 s.innerHTML=realce(txt)||'&nbsp;';t.appendChild(s);fim()}
(async()=>{const r=await (await fetch('/roteiro')).json();document.getElementById('titulo').textContent=r.titulo||'';
 await espera(900);
 for(let i=0;i<r.comandos.length;i++){const c=r.comandos[i];
  if(c.limpar&&i>0){t.innerHTML=''}
  const lin=document.createElement('span');lin.className='linha';
  lin.innerHTML='<span class="p">'+esc(r.prompt)+'</span> <span class="c"></span><span class="cursor"></span>';t.appendChild(lin);
  const cmd=lin.querySelector('.c');const ic=c.mostrar.indexOf('  #');const texto=ic<0?c.mostrar:c.mostrar.slice(0,ic);const coment=ic<0?'':c.mostrar.slice(ic);
  for(const ch of texto){cmd.textContent+=ch;fim();await espera(30+Math.random()*22)}
  if(coment){const k=document.createElement('span');k.className='k';lin.insertBefore(k,lin.querySelector('.cursor'));
   for(const ch of coment){k.textContent+=ch;await espera(12)}}
  await espera(450);lin.querySelector('.cursor').remove();
  document.title='executando '+i;
  const resp=await fetch('/run?i='+i);const leitor=resp.body.getReader();const dec=new TextDecoder();let resto='';
  for(;;){const {done,value}=await leitor.read();if(done)break;resto+=dec.decode(value,{stream:true});
   const partes=resto.split('\n');resto=partes.pop();
   for(const l of partes){linha(l);if(c.ritmo_ms)await espera(c.ritmo_ms)}}
  if(resto)linha(resto);
  document.title='pronto '+i;
  await espera((c.pausa_depois??2)*1000)}
 const fimp=document.createElement('span');fimp.className='linha';
 fimp.innerHTML='<span class="p">'+esc(r.prompt)+'</span> <span class="cursor"></span>';t.appendChild(fimp);fim();
 document.title='FIM'})();
</script></html>"""

LOG = re.compile(r"^\d{4}-\d{2}-\d{2} (\d\d:\d\d:\d\d) \| (\w+)\s*\| [\w.]+ \| (.*)$")


def compactar(linha: str) -> str:
    m = LOG.match(linha)
    if not m:
        return linha
    hora, nivel, msg = m.groups()
    marca = {"WARNING": "AVISO  ", "ERROR": "ERRO   "}.get(nivel, "")
    return f"{hora}  {marca}{msg}"


def main() -> None:
    roteiro = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    porta = int(sys.argv[sys.argv.index("--porta") + 1]) if "--porta" in sys.argv else 8765

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):  # silencioso
            pass

        def _enviar(self, corpo: bytes, tipo: str) -> None:
            self.send_response(200)
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(len(corpo)))
            self.end_headers()
            self.wfile.write(corpo)

        def do_GET(self):  # noqa: N802
            if self.path == "/":
                self._enviar(PAGINA.encode("utf-8"), "text/html; charset=utf-8")
            elif self.path == "/roteiro":
                publico = {"titulo": roteiro.get("titulo", ""), "prompt": roteiro["prompt"], "comandos": [
                    {k: c.get(k) for k in ("mostrar", "pausa_depois", "ritmo_ms", "limpar")} for c in roteiro["comandos"]]}
                self._enviar(json.dumps(publico).encode("utf-8"), "application/json")
            elif self.path.startswith("/run?i="):
                try:
                    c = roteiro["comandos"][int(self.path.split("=")[1])]
                except (ValueError, IndexError):
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()
                env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1", **c.get("env", {})}
                for k in c.get("sem_env", []):
                    env.pop(k, None)
                filtro = re.compile(c["filtro"]) if c.get("filtro") else None
                proc = subprocess.Popen(c["argv"], cwd=c.get("cwd"), env=env, stdout=subprocess.PIPE,  # nosemgrep -- argv fixo do roteiro local
                                        stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
                n = 0
                for l in proc.stdout:
                    l = l.rstrip("\n")
                    if filtro and not filtro.search(l):
                        continue
                    if c.get("compacto"):
                        l = compactar(l)
                    n += 1
                    if c.get("max_linhas") and n > c["max_linhas"]:
                        continue
                    self.wfile.write((l + "\n").encode("utf-8"))
                    self.wfile.flush()
                codigo = proc.wait()
                if c.get("mostrar_codigo"):
                    self.wfile.write(f"(código de saída: {codigo})\n".encode("utf-8"))
            else:
                self.send_error(404)

    ThreadingHTTPServer(("127.0.0.1", porta), H).serve_forever()


if __name__ == "__main__":
    main()

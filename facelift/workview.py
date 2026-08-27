"""Work view — show facelift exactly how I work on any task.

TodoWrite checklist + one in_progress at a time + read→edit→bash→verify loop.
Polls data/facelift.db events and maps them to the pipeline todos and tool stream.
Read-only, conservative, immersive like qwen.chat Work tab.
"""

from __future__ import annotations
import json, time, urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

WORK_HTML = r"""<!doctype html>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>facelift — work</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root{--bg:#090a0f;--panel:#11131a;--card:#171a24;--line:#232836;--mut:#8c93a8;--txt:#e8ecf3;--acc:#7c5cff;--ok:#22c55e;--run:#f59e0b;--pend:#475569}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--txt);font:13px/1.5 Inter,system-ui,sans-serif;height:100vh;display:flex;overflow:hidden}
a{color:#9ab6ff}
.top{height:42px;display:flex;align-items:center;justify-content:space-between;padding:0 12px;border-bottom:1px solid var(--line);background:rgba(17,19,26,.85);backdrop-filter:blur(10px)}
.pill{font:11px JetBrains Mono,monospace;padding:2px 7px;border-radius:999px;border:1px solid var(--line);color:var(--mut)}
.main{display:flex;flex:1;min-height:0}
.todo{width:300px;background:rgba(17,19,26,.9);border-right:1px solid var(--line);display:flex;flex-direction:column}
.todo-h{padding:12px;border-bottom:1px solid var(--line);font:11px JetBrains Mono,monospace;letter-spacing:.08em;color:var(--mut);text-transform:uppercase}
.tlist{padding:10px;overflow:auto;flex:1}
.ti{display:flex;gap:8px;align-items:flex-start;padding:8px 8px;border-radius:10px;margin-bottom:4px;border:1px solid transparent}
.ti.active{background:var(--card);border-color:var(--line)}
.ti.done{opacity:.7}
.box{width:16px;height:16px;border-radius:4px;border:1.5px solid var(--line);display:grid;place-items:center;flex-shrink:0;margin-top:1px;font-size:10px}
.box.run{border-color:var(--run);background:rgba(245,158,11,.15);color:var(--run);animation:pulse 1s infinite}
.box.done{border-color:var(--ok);background:rgba(34,197,94,.15);color:var(--ok)}
.box.pend{border-color:var(--pend);color:var(--pend)}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.5}}
.ttitle{font:12px Inter,sans-serif;font-weight:600}
.tdesc{font:11px JetBrains Mono,monospace;color:var(--mut)}
.stream{flex:1;display:flex;flex-direction:column;min-width:0;background:radial-gradient(900px 400px at 50% 0%,#1a1f3a 0%,transparent 60%)}
.shead{padding:10px 14px;border-bottom:1px solid var(--line);display:flex;gap:8px;align-items:center;font:11px JetBrains Mono,monospace;color:var(--mut)}
.sbody{flex:1;overflow:auto;padding:14px}
.call{margin:8px 0;border:1px solid var(--line);border-radius:12px;overflow:hidden;background:#131722}
.call-h{padding:7px 10px;display:flex;gap:8px;align-items:center;font:11px JetBrains Mono,monospace;color:var(--mut);background:#0f1320;border-bottom:1px solid var(--line)}
.call-b{padding:8px 10px;font:11px JetBrains Mono,monospace;color:#cbd5e1;white-space:pre-wrap;word-break:break-all;max-height:160px;overflow:auto}
.art{width:380px;background:rgba(17,19,26,.96);border-left:1px solid var(--line);display:flex;flex-direction:column}
.art-h{padding:10px 12px;border-bottom:1px solid var(--line);font:11px JetBrains Mono,monospace;letter-spacing:.08em;color:var(--mut);text-transform:uppercase;display:flex;justify-content:space-between}
.frame{flex:1;margin:10px;border:1px solid var(--line);border-radius:12px;overflow:hidden;display:flex;flex-direction:column;background:#0b0e16}
.frame iframe{flex:1;border:0;background:white}
.muted{color:var(--mut)} .mono{font-family:JetBrains Mono,monospace}
.kv{display:flex;justify-content:space-between;padding:3px 0;border-bottom:1px solid #1b2130;font:11px JetBrains Mono,monospace}
@media(max-width:1100px){.art{display:none}.todo{width:220px}}
</style>
<div class="top">
  <div style="display:flex;gap:8px;align-items:center"><b>facelift</b><span class="pill">work</span><span class="pill" id="runpill" style="background:var(--card)">how I work on any task</span></div>
  <div style="display:flex;gap:8px;align-items:center"><span class="pill" id="ts"></span><a href="/api/status" target="_blank" class="pill">/api/status</a><a href="/chat" class="pill">chat</a><a href="/" class="pill">viz</a></div>
</div>
<div class="main">
  <div class="todo">
    <div class="todo-h">TodoWrite — one in_progress at a time</div>
    <div class="tlist" id="tlist"></div>
    <div style="padding:10px;border-top:1px solid var(--line)" class="mono muted" id="tmeta"></div>
  </div>
  <div class="stream">
    <div class="shead"><span class="pill">read → edit → bash → verify</span><span class="muted">each tool emitted separately, file_path:line</span><span class="pill" id="toolcount" style="margin-left:auto">0 tool calls</span></div>
    <div class="sbody" id="sbody"></div>
  </div>
  <div class="art">
    <div class="art-h"><span>artifact — live preview + diff</span><span class="pill" id="artpill">no build yet</span></div>
    <div style="padding:10px" class="mono" id="stages"></div>
    <div class="frame"><iframe id="preview" src="about:blank"></iframe><div style="padding:6px 8px;border-top:1px solid var(--line)" class="mono muted">dist/index.html · builds/worker-…/dist · deploy → facelift.dpdns.org</div></div>
    <div style="padding:10px"><div class="muted mono" style="font-size:11px">Verification</div><div id="verify" class="mono" style="font-size:11px;white-space:pre-wrap"></div></div>
  </div>
</div>
<script>
const TODOS = [
  {k:'discovered', title:'Discover leads', desc:'sources.py:overpass_search bbox → dedupe', file:'facelift/sources.py:42', need:'discovered'},
  {k:'scored', title:'Score staleness', desc:'measure.py:score_many + UGLY_PASS gate', file:'facelift/measure.py:88', need:'scored'},
  {k:'audited', title:'Audit (PSI)', desc:'audit.py:audit_domain mobile+desktop', file:'facelift/cli.py:183', need:'audited'},
  {k:'triage', title:'Triage · speculative', desc:'speculative.py:73 veto 0 tok → batched 5/chunk 1 LLM', file:'facelift/speculative.py:74', need:'scored'},
  {k:'research', title:'Research waterfall', desc:'research.py:178 4× parallel Bing→DDG→Reddit → 1 synthesis', file:'facelift/research.py:178', need:'research'},
  {k:'build', title:'Compose / Agent build', desc:'build.py:compose or builder_agent opencode → quality gate', file:'facelift/cli.py:319', need:'rebuilt'},
  {k:'critic', title:'Visual critic + revision', desc:'beforeafter.py screenshot → design_critique → revision', file:'facelift/beforeafter.py', need:'rebuilt'},
  {k:'contacts', title:'Contacts + draft', desc:'contacts.py:waterfall → outreach draft hash gate', file:'facelift/outreach.py', need:'contacts_found'},
];

function statusToDone(stages, events){
  // mark todo done if stage reached or event exists
  const evKinds = new Set((events||[]).map(e=>e.kind));
  const hasStage = (k)=> (stages[k]||0)>0;
  return (todo)=>{
    if(todo.k==='triage') return hasStage('scored')||hasStage('rebuilt');
    if(todo.k==='research') return evKinds.has('rebuilt')||hasStage('rebuilt');
    if(todo.k==='contacts') return hasStage('contacts_found')||hasStage('drafted');
    if(todo.k==='critic') return hasStage('rebuilt');
    return hasStage(todo.need) || evKinds.has(todo.need);
  };
}

async function poll(){
  try{
    const r=await fetch('/api/status',{cache:'no-store'}); const j=await r.json();
    document.getElementById('ts').textContent=new Date(j.ts).toLocaleTimeString();
    // todo list — one in_progress
    const stages=j.stages||{}; const evs=j.events||[];
    const isDone = statusToDone(stages, evs);
    let firstPending = TODOS.findIndex(t=>!isDone(t));
    if(firstPending===-1) firstPending=TODOS.length;
    let html='';
    TODOS.forEach((t,i)=>{
      const done=isDone(t); const active=i===firstPending && !done;
      const cls=done?'done':active?'active':'';
      const boxCls=done?'done':active?'run':'pend';
      const boxChar=done?'✓':active?'●':'○';
      html+=`<div class="ti ${cls}"><div class="box ${boxCls}">${boxChar}</div><div><div class="ttitle">${t.title} <span class="pill" style="padding:0 4px;font-size:10px">${t.k}</span></div><div class="tdesc">${t.desc}</div><div class="mono muted" style="font-size:10px">${t.file}</div></div></div>`;
    });
    document.getElementById('tlist').innerHTML=html;
    document.getElementById('tmeta').textContent = `${Object.entries(stages).map(([k,v])=>k+':'+v).join(' · ')||'no leads yet — run discover-nosite'} · cache hits ${j.cache?.hit||0} misses ${j.cache?.miss||0}`;
    document.getElementById('stages').innerHTML = Object.entries(stages).map(([k,v])=>`<div class="kv"><span>${k}</span><b>${v}</b></div>`).join('') || '<span class="muted">no leads</span>';
    // tool stream — map events to tool calls like I emit them
    const sbody=document.getElementById('sbody');
    let calls='';
    evs.slice(0,12).reverse().forEach(e=>{
      const det=e.detail||{};
      let tool='bash', args='', out='';
      if(e.kind==='discover_nosite'){ tool='bash'; args=`overpass_no_site_search(bbox, limit) → ${det.name||e.lead_id}`; out=JSON.stringify(det).slice(0,120)}
      else if(e.kind==='scored'){ tool='bash'; args=`measure.py:score_many [${e.lead_id}]`; out=`score ${det.score||'?'} signals ${JSON.stringify(det).slice(0,80)}`}
      else if(e.kind==='extracted'){ tool='read'; args=`facelift/cli.py:145 _extract_facts(${e.lead_id})`; out=`model ${det.model||''} keys ${Object.keys(det.data||{}).slice(0,4).join(',')}`}
      else if(e.kind==='audited'){ tool='bash'; args=`audit.py:audit_domain(${e.lead_id})`; out=`mobile ${JSON.stringify(det.mobile||{}).slice(0,60)}`}
      else if(e.kind==='rebuilt'){ tool='edit'; args=`builds/${det.worker||''}/dist/index.html`; out=`→ ${det.url||''}`; if(det.url) document.getElementById('preview').src=det.url; document.getElementById('artpill').textContent='live';}
      else { tool='log'; args=e.kind; out=JSON.stringify(det).slice(0,100)}
      const dot = e.kind.includes('error')?'run':e.kind==='rebuilt'?'done':'done';
      calls+=`<div class="call"><div class="call-h"><span style="width:7px;height:7px;border-radius:50%;background:${dot==='done'?'var(--ok)':dot==='run'?'var(--run)':'var(--pend)'}"></span>${tool} <span class="muted">${e.ts||''}</span><span class="pill" style="margin-left:auto">${e.kind}</span></div><div class="call-b"><b>${args}</b>\n<span class="muted">${e.lead_id||''}</span>\n${out}</div></div>`;
    });
    if(!calls) calls='<div class="muted" style="padding:20px;text-align:center">No tool calls yet — run <span class="pill">discover-nosite --commit</span> then <span class="pill">rebuild &lt;id&gt; --commit</span><br>Each turn appears here as a separate tool emission, exactly how I work.</div>';
    sbody.innerHTML=calls;
    document.getElementById('toolcount').textContent = `${evs.length} tool calls`;
    document.getElementById('verify').textContent = evs.some(e=>e.kind==='rebuilt') ? 'verify: dist/index.html exists → quality_check() → deploy_dir() → watch liveness' : 'verify pending — build not yet run';
  }catch(e){ document.getElementById('sbody').textContent='poll failed: '+e }
}
poll(); setInterval(poll,1500);
</script>
"""

from .viz import _snapshot

class H3(BaseHTTPRequestHandler):
    def do_GET(self):
        p = urllib.parse.urlparse(self.path).path
        if p in ("/","/work","/index.html"):
            self.send_response(200); self.send_header("content-type","text/html; charset=utf-8"); self.end_headers()
            self.wfile.write(WORK_HTML.encode())
        elif p == "/api/status":
            body = json.dumps(_snapshot()).encode()
            self.send_response(200); self.send_header("content-type","application/json"); self.send_header("cache-control","no-store"); self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404); self.end_headers()
    def log_message(self, *a, **kw): pass

def serve_work(port=8767):
    httpd = HTTPServer(("127.0.0.1", port), H3)
    print(f"work view at http://127.0.0.1:{port}/work  (TodoWrite + tool stream + diff, like how I work)")
    try: httpd.serve_forever()
    except KeyboardInterrupt: pass

def cmd_work(args) -> int:
    import webbrowser, threading
    if args.open:
        threading.Timer(0.7, lambda: webbrowser.open(f"http://127.0.0.1:{args.port}/work")).start()
    serve_work(args.port)
    return 0

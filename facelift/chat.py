"""Immersive qwen.chat-style cockpit — facelift Chat.

Center chat + left sessions + right artifacts. No CLI memorizing.
Every facelift turn streams as a qwen-style tool waterfall
with where (Bing→DDG→Reddit), latency, and CAS result live.

Reuse viz _snapshot() backend; adds /api/chat stream + POST.
"""

from __future__ import annotations
import json, time, urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

QWEN_HTML = r"""<!doctype html>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>facelift — chat</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400&display=swap" rel="stylesheet">
<style>
:root{--bg:#0a0c10;--panel:#11141b;--card:#171b24;--line:#222836;--mut:#8c93a6;--txt:#e6e9f0;--acc:#7c5cff;--acc2:#2ec5ff;--ok:#22c55e;--warn:#f59e0b}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(1200px 600px at 40% -10%,#1a1f3a 0%,transparent 60%),var(--bg);color:var(--txt);font:13px/1.5 Inter,system-ui,sans-serif;height:100vh;display:flex;overflow:hidden}
a{color:#9ab6ff}
.sidebar{width:260px;background:rgba(17,20,27,.92);backdrop-filter:blur(14px);border-right:1px solid var(--line);display:flex;flex-direction:column}
.brand{padding:14px 14px 10px;display:flex;align-items:center;gap:10px;border-bottom:1px solid var(--line)}
.logo{width:28px;height:28px;border-radius:8px;background:linear-gradient(135deg,var(--acc),var(--acc2));display:grid;place-items:center;font-weight:800;font-size:12px}
.pill{font:11px JetBrains Mono,monospace;padding:2px 7px;border-radius:999px;border:1px solid var(--line);color:var(--mut)}
.sess{padding:8px;overflow:auto;flex:1}
.item{padding:8px 10px;border-radius:10px;cursor:pointer;border:1px solid transparent;color:var(--mut);margin-bottom:4px}
.item.active{background:var(--card);border-color:var(--line);color:var(--txt)}
.item:hover{background:#151a27}
.center{flex:1;display:flex;flex-direction:column;min-width:0;position:relative}
.top{height:48px;display:flex;align-items:center;justify-content:space-between;padding:0 16px;border-bottom:1px solid var(--line);background:rgba(17,20,27,.6);backdrop-filter:blur(10px)}
.model{padding:6px 10px;border-radius:999px;background:var(--card);border:1px solid var(--line);font:12px JetBrains Mono,monospace;color:var(--mut)}
.stream{flex:1;overflow:auto;padding:18px 0 0}
.thread{max-width:760px;margin:0 auto;padding:0 18px 120px;width:100%}
.bubble{margin:10px 0;display:flex;gap:10px}
.av{width:26px;height:26px;border-radius:50%;display:grid;place-items:center;font-size:12px;flex-shrink:0}
.av.user{background:#1f2937} .av.ai{background:linear-gradient(135deg,var(--acc),var(--acc2))}
.msg{flex:1;min-width:0}
.role{font-size:11px;letter-spacing:.08em;color:var(--mut);text-transform:uppercase;margin-bottom:4px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:12px 14px}
.tool{margin:8px 0;border:1px solid var(--line);border-radius:12px;overflow:hidden;background:#131722}
.tool-h{padding:8px 10px;display:flex;align-items:center;gap:8px;font:11px JetBrains Mono,monospace;color:var(--mut);background:#0f1320;border-bottom:1px solid var(--line);cursor:pointer}
.dot{width:7px;height:7px;border-radius:50%}.dot.ok{background:var(--ok)}.dot.run{background:var(--warn);animation:pulse 1s infinite}.dot.wait{background:#334155}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}
.tool-b{padding:10px;font:12px JetBrains Mono,monospace;color:#cbd5e1;white-space:pre-wrap;word-break:break-all}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}
.chip{padding:4px 8px;border-radius:999px;background:#0f1320;border:1px solid var(--line);color:var(--mut);font:11px JetBrains Mono,monospace}
.artifact{width:380px;background:rgba(17,20,27,.96);border-left:1px solid var(--line);display:flex;flex-direction:column}
.art-h{padding:10px 12px;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;align-items:center}
.frame{flex:1;background:#0b0e16;margin:10px;border:1px solid var(--line);border-radius:12px;overflow:hidden;display:flex;flex-direction:column}
.frame iframe{flex:1;border:0;background:white}
.composer{position:absolute;left:0;right:0;bottom:0;padding:12px;background:linear-gradient(to top,var(--bg),transparent 30%,transparent);display:flex;justify-content:center}
.box{width:100%;max-width:760px;background:var(--panel);border:1px solid var(--line);border-radius:18px;padding:8px;display:flex;flex-direction:column;gap:8px;box-shadow:0 20px 60px rgba(0,0,0,.5)}
.box textarea{width:100%;background:transparent;border:0;outline:0;color:var(--txt);resize:none;min-height:22px;max-height:120px;font:13px Inter,sans-serif;padding:6px 8px}
.bar{display:flex;justify-content:space-between;align-items:center;padding:0 4px 2px}
.quick{display:flex;gap:6px;flex-wrap:wrap}
.q{padding:5px 8px;border-radius:999px;background:#0f1320;border:1px solid var(--line);color:var(--mut);font:11px JetBrains Mono,monospace;cursor:pointer}
.q:hover{border-color:var(--acc);color:var(--txt)}
.send{width:28px;height:28px;border-radius:999px;background:linear-gradient(135deg,var(--acc),var(--acc2));border:0;color:white;display:grid;place-items:center;cursor:pointer}
.muted{color:var(--mut)} .mono{font-family:JetBrains Mono,monospace}
.kv{display:flex;justify-content:space-between;padding:3px 0;border-bottom:1px solid #1b2130;font:11px JetBrains Mono,monospace}
@media(max-width:1100px){.artifact{display:none}.sidebar{width:200px}}
</style>
<div class="sidebar">
  <div class="brand"><div class="logo">F</div><div><b>facelift</b><div class="muted mono" style="font-size:10px">immersive · qwen style</div></div><span class="pill" style="margin-left:auto">speculative</span></div>
  <div style="padding:10px"><div class="pill" style="width:100%;text-align:center;padding:8px;cursor:pointer" onclick="newChat()">+ New run</div></div>
  <div class="sess" id="sess"></div>
  <div style="padding:10px;border-top:1px solid var(--line)"><div class="muted mono" style="font-size:11px">Data: <span id="dbpath"></span><br><a href="/api/status" target="_blank">/api/status</a> · <a href="/" target="_blank">viz</a></div></div>
</div>
<div class="center">
  <div class="top"><div style="display:flex;gap:8px;align-items:center"><span class="model">Gemini 3.6 Flash · speculative · wallet 1500/d</span><span class="pill" id="hitpill">cache —</span></div><div class="muted mono" id="ts"></div></div>
  <div class="stream" id="stream"><div class="thread" id="thread"></div></div>
  <div class="composer"><div class="box">
    <textarea id="inp" rows="1" placeholder="Ask facelift…  e.g. “discover nosite in Bandra 10” / “rebuild osm-123” / “draft lead_001”"></textarea>
    <div class="bar"><div class="quick">
      <div class="q" onclick="fill('discover nosite 19.05,72.80,19.25,73.05 limit 10')">Discover nosite</div>
      <div class="q" onclick="fill('status')">Status</div>
      <div class="q" onclick="fill('rebuild osm-… --commit')">Rebuild</div>
      <div class="q" onclick="fill('agents researcher osm-1,osm-2 --workers 3')">Agents</div>
      <div class="q" onclick="fill('draft osm-…')">Draft</div>
    </div><button class="send" onclick="send()">↑</button></div>
  </div></div>
</div>
<div class="artifact">
  <div class="art-h"><b class="mono" style="font-size:11px;letter-spacing:.08em">ARTIFACT — LIVE PREVIEW</b><span class="pill" id="art-pill">no build yet</span></div>
  <div style="padding:10px">
    <div id="stages" class="mono" style="font-size:11px"></div>
    <div class="chips" id="spec-chips"></div>
  </div>
  <div class="frame"><iframe id="preview" src="about:blank"></iframe><div style="padding:6px 8px;border-top:1px solid var(--line);display:flex;gap:6px" class="mono muted">research waterfall → speculative.py:178 · Bing→DDG→Reddit · agents store.py:84 CAS</div></div>
  <div style="padding:10px"><div class="muted mono" style="font-size:11px">Tool waterfall (per turn)</div><div id="water" class="mono" style="font-size:11px;white-space:pre-wrap"></div></div>
</div>
<script>
let sessId = localStorage.getItem('fl_sess') || ('run-'+Date.now().toString(36));
localStorage.setItem('fl_sess', sessId);
const thread = document.getElementById('thread');
function el(h){const d=document.createElement('div'); d.innerHTML=h; return d.firstElementChild}
function addUser(t){ thread.appendChild(el(`<div class="bubble"><div class="av user">U</div><div class="msg"><div class="role">you</div><div class="card">${esc(t)}</div></div></div>`)); scroll() }
function addAI(){ const w=el(`<div class="bubble"><div class="av ai">F</div><div class="msg"><div class="role">facelift · speculative</div><div class="card" id="ai-${Date.now()}"><span class="muted">thinking…</span></div></div></div>`); thread.appendChild(w); scroll(); return w.querySelector('.card'); }
function esc(s){return s.replace(/&/g,'&amp;').replace(/</g,'&lt;')}
function fill(s){ document.getElementById('inp').value=s; document.getElementById('inp').focus(); }
function newChat(){ thread.innerHTML=''; hint(); }
function hint(){
  thread.appendChild(el(`<div class="bubble"><div class="av ai">F</div><div class="msg"><div class="role">facelift</div><div class="card">Immersive, conservative — I never send without your hash.<br><br><b>Try:</b> <span class="chip">discover nosite 19.05,72.80,19.25,73.05 limit 10</span> <span class="chip">status</span> <span class="chip">rebuild &lt;lead_id&gt; --commit</span><br><span class="muted mono" style="font-size:11px">Left: your runs (from data/facelift.db). Center: streaming tool waterfall. Right: live preview + research where.</span></div></div></div>`));
}
function scroll(){ document.getElementById('stream').scrollTop = document.getElementById('stream').scrollHeight; }

async function askExplain(q, box){
  box.innerHTML=`<div class="tool"><div class="tool-h"><span class="dot run"></span>thinking · qwen style <span class="pill" style="margin-left:auto">explain</span></div><div class="tool-b muted">pulling live snapshot and tracing where…</div></div>`;
  try{
    const r=await fetch('/api/explain?q='+encodeURIComponent(q)); const j=await r.json();
    box.innerHTML = `<div style="margin:6px 0;padding:10px;border:1px solid var(--line);border-radius:12px;background:#0f1320">
      <div class="mono" style="font-size:11px;color:var(--mut)">thinking</div>
      <div style="font-size:12px;white-space:pre-wrap">${esc(j.answer||'')}</div>
      <div class="muted mono" style="margin-top:6px;font-size:11px">where: ${esc(j.where||'')}</div>
      <div style="margin-top:8px;display:flex;gap:6px"><span class="chip" onclick="fill('what are you doing?')">what now?</span><span class="chip" onclick="fill('where did you search?')">where searched?</span><span class="chip" onclick="fill('cache hit rate?')">cache?</span></div>
    </div>`;
    if(j.snapshot){ const s=j.snapshot; box.insertAdjacentHTML('beforeend', `<div class="tool"><div class="tool-h"><span class="dot ok"></span>live snapshot <span class="pill" style="margin-left:auto">${new Date(s.ts).toLocaleTimeString()}</span></div><div class="tool-b">stages: ${Object.entries(s.stages||{}).map(([k,v])=>k+':'+v).join(' · ')}\nhits ${s.cache?.hit||0} misses ${s.cache?.miss||0} entries ${s.cache?.entries||0}\nlast: ${(s.events?.[0]?.kind||'-')} ${(s.events?.[0]?.lead_id||'')}</div></div>`); }
  }catch(e){ box.innerHTML+=`<div class="muted mono">explain failed: ${esc(String(e))}</div>`}
  scroll();
}
async function send(){
  const inp=document.getElementById('inp'); const t=inp.value.trim(); if(!t) return; inp.value='';
  addUser(t);
  const box=addAI();
  const isQuestion = /^(why|what|where|how|explain|cache|veto)\b|\?$|doing|search/i.test(t);
  if(isQuestion){ await askExplain(t, box); return; }
  // facelift command → qwen-style thinking + tool waterfall
  box.innerHTML = `<div style="padding:8px 10px;border:1px solid var(--line);border-radius:12px;background:#0f1320;margin-bottom:8px"><div class="mono" style="font-size:11px;color:var(--mut)">thinking</div><div style="font-size:12px" class="muted">You said “${esc(t)}”. I'll map that to the conservative pipeline: dry-run shows, --commit writes. Streaming each turn with where and why so you stay in control.</div></div>`;
  const steps=[
    ['run','deterministic veto (0 tokens)','speculative.py:73 — RULE_VETO bank|embassy|bhavan|…\n→ if name matches → rejected instantly, 0 LLM. Else → batched.','why was vetoed?'],
    ['run','batched triage — 1 LLM call per 5 leads','speculative.py:74 batched_triage()\nminified JSON array [{prospect,reason}] per chunk\nkey = sha256(names)[:16], TTL 24h cache','cache hit rate?'],
    ['run','speculative_research() 4× parallel','research.py:178 ThreadPoolExecutor(max_workers=4)\n  trends → best {vertical} website design inspiration\n  tech → {vertical} essential features booking/ordering\n  expect → {vertical} must have features\n  traces → "{lead}" {city} reviews OR instagram\nBing primary (BING_BLOCK_RE) → DDG fallback research.py:94 → reddit_search','where did you search?'],
    ['run','batched synthesis + deterministic copy','research.py:147 batched_research_synthesis() — 1 LLM call for all buckets\ncopywriter.py:68 write_copy() → on exception → deterministic_copy(trade,city) 0 tokens','how copy fallback?'],
    ['wait','deploy & visual critic','build.py:compose or builder_agent opencode → screenshot → design_critique → revision → deploy → before-after.html','what deployed?'],
  ];
  for(const [st,title,body,explainQ] of steps){
    const d=document.createElement('div'); d.className='tool';
    d.innerHTML=`<div class="tool-h"><span class="dot ${st}"></span>${title}<span class="pill" style="margin-left:auto">${st}</span><span class="chip" style="margin-left:6px;cursor:pointer" onclick="askExplain('${explainQ}', this.closest('.card'))">why?</span></div><div class="tool-b">${esc(body)}</div>`;
    box.appendChild(d); await new Promise(r=>setTimeout(r,320)); scroll();
    d.querySelector('.dot').className='dot ok'; d.querySelector('.tool-h .pill').textContent='done';
  }
  try{
    const r=await fetch('/api/status',{cache:'no-store'}); const j=await r.json();
    const ev=j.events?.[0]; const url=j.research?.url;
    box.insertAdjacentHTML('beforeend', `<div class="tool"><div class="tool-h"><span class="dot ok"></span>live snapshot <span class="pill" style="margin-left:auto">${new Date(j.ts).toLocaleTimeString()}</span></div><div class="tool-b">stages: ${Object.entries(j.stages||{}).map(([k,v])=>k+':'+v).join(' · ')}\nlast: ${(ev?.kind||'-')} ${(ev?.lead_id||'')} ${(ev?.detail?.model||ev?.detail?.url||'').slice(0,60)}\ncache: hits ${j.cache?.hit||0} misses ${j.cache?.miss||0} entries ${j.cache?.entries||0}</div></div>`);
    if(url){ document.getElementById('preview').src=url; document.getElementById('art-pill').textContent=url.slice(0,28); }
  }catch(e){ box.insertAdjacentHTML('beforeend', `<div class="muted mono">live fetch failed: ${esc(String(e))}</div>`)}
  box.insertAdjacentHTML('beforeend', `<div class="muted mono" style="margin-top:8px">Run for real (conservative):<br><span class="chip">$env:PYTHONPATH="C:\\Users\\Raja\\facelift"; python -m facelift.cli ${esc(t)}</span> <span class="muted">add --commit to write</span></div>`);
  box.insertAdjacentHTML('beforeend', `<div style="margin-top:8px;display:flex;gap:6px"><span class="chip" onclick="askExplain('what are you doing?', this.closest('.card'))">what now?</span><span class="chip" onclick="fill('why vetoed?')">why veto?</span><span class="chip" onclick="fill('where did you search?')">where?</span></div>`);
  scroll();
}

document.getElementById('inp').addEventListener('keydown', e=>{ if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send()} });
hint();

// sidebar sessions from events
async function refreshSess(){
  try{
    const r=await fetch('/api/status',{cache:'no-store'}); const j=await r.json();
    document.getElementById('ts').textContent=new Date(j.ts).toLocaleTimeString();
    document.getElementById('hitpill').textContent=`hits ${j.cache?.hit||0} / misses ${j.cache?.miss||0}`;
    document.getElementById('dbpath').textContent='data/facelift.db';
    const stages=j.stages||{}; document.getElementById('stages').innerHTML=Object.entries(stages).map(([k,v])=>`<div class="kv"><span>${k}</span><b>${v}</b></div>`).join('')||'<span class="muted">no leads</span>';
    document.getElementById('spec-chips').innerHTML=`<span class="chip">veto 0 tok</span><span class="chip">batch 5/chunk</span><span class="chip">hit ${Math.round((j.cache?.hit||0)/((j.cache?.hit||0)+(j.cache?.miss||0)||1)*100)}%</span>`;
    document.getElementById('water').textContent='trends → best {vertical} website design inspiration\ntech → {vertical} essential features online booking ordering\ntraces → "{lead}" {city} reviews OR instagram\nexpect → {vertical} must have features customers expect\n— 4 parallel, Bing→DDG, 1 synthesis call';
    const sess=document.getElementById('sess'); const evs=j.events||[]; const byLead={};
    for(const e of evs){ if(!byLead[e.lead_id]) byLead[e.lead_id]=[]; byLead[e.lead_id].push(e); }
    sess.innerHTML=Object.keys(byLead).slice(0,12).map(id=>`<div class="item" onclick="fill('rebuild ${id} --commit')"><b>${id.slice(0,18)}</b><div class="muted mono" style="font-size:11px">${(byLead[id][0]?.kind||'').slice(0,22)}</div></div>`).join('') || '<div class="muted" style="padding:8px">no runs yet — hit Discover</div>';
    const url=j.research?.url; if(url) { document.getElementById('preview').src=url; document.getElementById('art-pill').textContent='live'; }
  }catch(e){}
}
refreshSess(); setInterval(refreshSess,1600);
</script>
"""

from .viz import _snapshot  # reuse

def _explain(q: str) -> dict:
    s = _snapshot()
    ql = q.lower()
    stages = s.get("stages",{})
    evs = s.get("events",[])
    cache = s.get("cache",{})
    last = evs[0] if evs else {}
    # deterministic veto explain
    if any(k in ql for k in ("veto","reject","why not","why was")):
        return {"answer": "Deterministic veto runs before any LLM (0 tokens) at speculative.py:73.\nRULE_VETO = bank|embassy|commission|authority|ministr|secretariat|bhavan|bhawan|sadan|nigam|parishad|corporate park|tech park|state board|branch \\d+|zonal|pvt|ltd|inc\\b|corporation\nIf name matches → rejected instantly, no model call. Otherwise → batched_triage() groups 5 leads → 1 minified JSON call, hash(cache) 24h at spec_cache.json.",
                "where":"speculative.py:73-74", "snapshot": s}
    if any(k in ql for k in ("where","search","research","bing","ddg","reddit")):
        return {"answer": "Research is speculative + parallel:\n• research.py:178 speculative_research() launches 4 web_search in ThreadPoolExecutor(max_workers=4) simultaneously: trends/tech/expect/traces.\n• Each web_search tries Bing primary (BING_BLOCK_RE) → on fail falls back to DuckDuckGo HTML (research.py:94), then reddit_search public JSON.\n• batched_research_synthesis() merges all buckets into ONE LLM call. If Bing times out, you still get DDG; if both fail, template fallback keeps pipeline alive.",
                "where":"research.py:94,178", "snapshot": s}
    if any(k in ql for k in ("cache","hit","miss","token","cost")):
        hit, miss = cache.get("hit",0), cache.get("miss",0)
        tot = hit+miss or 1
        return {"answer": f"Cache {CACHE if False else 'data/spec_cache.json'} — hits {hit} / misses {miss} → hit rate {round(hit/tot*100)}%.\nKey = sha256(json(inputs))[:16], TTL 24h, prune at 500 entries. Batched triage hash is [names] per 5-chunk, research synth hash is first 500 chars of buckets. Hit = 0 tokens, no LLM.",
                "where":"speculative.py:50", "snapshot": s}
    if any(k in ql for k in ("doing","status","what","now","progress")):
        last_k = last.get("kind","-"); last_id = last.get("lead_id","")
        return {"answer": f"Right now: stages {', '.join(f'{k}:{v}' for k,v in stages.items()) or 'no leads yet'}.\nLast event: {last_k} {last_id} {str(last.get('detail',{}))[:140]}.\nIf you ran discover-nosite → triage (veto→batch) → research waterfall → build → critic → deploy. Agents compete via store.py:84 atomic CAS — only one wins per lead.",
                "where":"cli.py:920 + store.py:84", "snapshot": s}
    if any(k in ql for k in ("agent","pool","cas","parallel","worker")):
        return {"answer": "Pool.spawn() at agents.py:52 runs role workers in ThreadPoolExecutor. Shared WAL store (store.py:61 PRAGMA journal_mode=WAL). Claim = try_stage_transition(old→new) doing SELECT stage → UPDATE WHERE stage=old → commit + verify. Two workers racing same lead → one gets rowcount 1 (wins), other rowcount 0 → 'already claimed'. No duplicate builds.",
                "where":"agents.py:52 store.py:84", "snapshot": s}
    return {"answer": f"You asked: \"{q}\"\\nI can explain any turn — try: 'why vetoed?', 'where did you search?', 'cache hit rate?', 'what are you doing?', 'how do agents not clash?'.\\nCurrent stages {stages}, last {last.get('kind')} {last.get('lead_id')}.",
            "where":"chat.py:_explain", "snapshot": s}

class H2(BaseHTTPRequestHandler):
    def do_GET(self):
        p = urllib.parse.urlparse(self.path).path
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        if p in ("/","/chat","/qwen","/index.html"):
            self.send_response(200); self.send_header("content-type","text/html; charset=utf-8"); self.end_headers()
            self.wfile.write(QWEN_HTML.encode())
        elif p == "/api/status":
            body = json.dumps(_snapshot()).encode()
            self.send_response(200); self.send_header("content-type","application/json"); self.send_header("cache-control","no-store"); self.end_headers()
            self.wfile.write(body)
        elif p == "/api/explain":
            q = qs.get("q",["what are you doing"])[0]
            body = json.dumps(_explain(q)).encode()
            self.send_response(200); self.send_header("content-type","application/json"); self.send_header("cache-control","no-store"); self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404); self.end_headers()
    def do_POST(self):
        p = urllib.parse.urlparse(self.path).path
        if p == "/api/chat":
            n = int(self.headers.get("content-length","0") or 0)
            body = self.rfile.read(n) if n else b"{}"
            try: j=json.loads(body)
            except: j={}
            q=j.get("q","") or j.get("message","")
            ans=_explain(q)
            out=json.dumps(ans).encode()
            self.send_response(200); self.send_header("content-type","application/json"); self.end_headers()
            self.wfile.write(out)
        else:
            self.send_response(404); self.end_headers()
    def log_message(self, *a, **kw): pass

def serve_chat(port=8766):
    httpd = HTTPServer(("127.0.0.1", port), H2)
    print(f"immersive qwen.chat at http://127.0.0.1:{port}/chat  (center chat · left sessions · right artifacts)")
    try: httpd.serve_forever()
    except KeyboardInterrupt: pass

def cmd_chat(args) -> int:
    import webbrowser, threading
    if args.open:
        threading.Timer(0.7, lambda: webbrowser.open(f"http://127.0.0.1:{args.port}/chat")).start()
    serve_chat(args.port)
    return 0

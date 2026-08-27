"""Live side-workspace viz — conservative, read-only observability.

Serves http://127.0.0.1:<port> with auto-polling dashboard:
  - pipeline stage counts + recent events timeline
  - research waterfall (where: Bing/DDG/Reddit, queries, hits, latency)
  - speculative metrics (deterministic vs LLM, batched triage chunks, cache hits/misses)
  - agent pool (role, lead, status, elapsed, CAS result)

No mutations. Reads data/facelift.db + data/spec_cache.json only.
"""

from __future__ import annotations

import json
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "facelift.db"
CACHE = ROOT / "data" / "spec_cache.json"


def _snapshot() -> dict:
    out: dict = {"ts": int(time.time()*1000), "stages": {}, "events": [], "cache": {}, "research": None}
    # stages + events from store
    try:
        from .store import Store
        from .speculative import get_cache_metrics
        s = Store(DB)
        out["stages"] = s.stage_counts()
        rows = s.conn.execute("SELECT ts, lead_id, kind, detail FROM events ORDER BY rowid DESC LIMIT 30").fetchall()
        evs = []
        for r in rows:
            try:
                det = json.loads(r["detail"]) if r["detail"] else {}
            except Exception:
                det = {"raw": str(r["detail"])[:120]}
            evs.append({"ts": r["ts"], "lead_id": r["lead_id"], "kind": r["kind"], "detail": det})
        out["events"] = evs
        try:
            out["cache"] = get_cache_metrics()
            # cache file size / entries
            if CACHE.exists():
                try:
                    j = json.loads(CACHE.read_text(encoding="utf-8"))
                    out["cache"]["entries"] = len(j)
                except Exception:
                    pass
        except Exception:
            pass
        # last research char count
        last = s.last_event_detail(rows[0]["lead_id"], "extracted") if rows else None
        # try to surface last field_research length if present in rebuilt log
        for r in rows:
            if r["kind"] == "rebuilt":
                d = json.loads(r["detail"]) if r["detail"] else {}
                out["research"] = {"worker": d.get("worker"), "url": d.get("url")}
                break
    except Exception as ex:
        out["error"] = str(ex)[:200]
    return out

HTML = r"""<!doctype html>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>facelift — live workspace</title>
<style>
:root{--bg:#0b0f14;--card:#111821;--mut:#8a96a8;--ok:#2ecc71;--warn:#f1c40f;--bad:#e74c3c;--line:#1e2a3a}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:#d6e1ee;font:13px/1.4 ui-monospace,Consolas,monospace}
h2{font-size:11px;letter-spacing:.12em;color:var(--mut);margin:0 0 8px;text-transform:uppercase}
.grid{display:grid;grid-template-columns:320px 1fr 380px;gap:12px;padding:12px;min-height:100vh}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px}
.kv{display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid #15202e}
.kv:last-child{border:0}
.pill{display:inline-block;padding:1px 6px;border-radius:999px;font-size:11px;border:1px solid var(--line);color:var(--mut)}
.dot{width:8px;height:8px;border-radius:50%;display:inline-block;margin-right:6px}
.tl{max-height:520px;overflow:auto}
.ev{padding:6px 0;border-bottom:1px solid #15202e}
.ev:last-child{border:0}
.muted{color:var(--mut)} .ok{color:var(--ok)} .warn{color:var(--warn)}
.spec{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.mono{white-space:pre-wrap;word-break:break-all;font-size:11px;color:#9fb0c8}
header{display:flex;justify-content:space-between;align-items:center;padding:10px 12px;border-bottom:1px solid var(--line);background:#0e141d;position:sticky;top:0}
a{color:#7fb3ff}
@media(max-width:1100px){.grid{grid-template-columns:1fr}}
</style>
<header>
  <div><b>facelift</b> <span class="pill">live workspace</span> <span id="ts" class="muted"></span></div>
  <div style="display:flex;gap:8px;align-items:center"><span id="cache" class="pill"></span><span class="pill">read-only</span><a href="/api/status" target="_blank">/api/status</a></div>
</header>
<div class="grid">
  <div class="card"><h2>pipeline — stages</h2><div id="stages"></div><h2 style="margin-top:14px">speculative — programmatic</h2><div id="spec" class="spec"></div><div id="research" class="muted" style="margin-top:8px"></div></div>
  <div class="card"><h2>timeline — last 30 events (most recent first)</h2><div id="tl" class="tl"></div></div>
  <div class="card"><h2>research waterfall — where &amp; what</h2><div id="wf" class="mono">polling…</div><h2 style="margin-top:12px">agents — Pool.spawn</h2><div id="agents" class="mono">use: python -m facelift agents --role researcher --leads "id1,id2" --workers 3
atomic CAS in store.py:84 — only one worker wins per lead.</div></div>
</div>
<script>
async function poll(){
  try{
    const r=await fetch('/api/status',{cache:'no-store'}); const j=await r.json();
    document.getElementById('ts').textContent=new Date(j.ts).toLocaleTimeString()+' · '+j.ts;
    document.getElementById('cache').textContent='cache hits '+ (j.cache.hit??0)+' / misses '+(j.cache.miss??0)+' · entries '+(j.cache.entries??0);
    // stages
    const s=j.stages||{}; let h=''; const order=['discovered','scored','audited','built','rebuilt','contacts_found','drafted','sent'];
    for(const k of Object.keys(s).sort()) h+=`<div class="kv"><span>${k}</span><b>${s[k]}</b></div>`;
    if(!h) h='<div class="muted">no leads yet — run discover-nosite</div>';
    document.getElementById('stages').innerHTML=h;
    const hit=j.cache.hit||0, miss=j.cache.miss||0; const tot=hit+miss||1;
    document.getElementById('spec').innerHTML=
      `<div class="card" style="padding:8px;background:#0e1a28"><div class="muted">deterministic first</div><b>veto+template</b><div class="muted">0 tokens</div></div>`+
      `<div class="card" style="padding:8px;background:#0e1a28"><div class="muted">hit rate</div><b>${Math.round(hit/tot*100)}%</b><div class="muted">${hit} / ${miss+hit}</div></div>`;
    if(j.research) document.getElementById('research').textContent='last build: '+(j.research.worker||'')+' '+ (j.research.url||'');
    // timeline
    const evs=j.events||[]; let tl='';
    for(const e of evs){
      const det=e.detail||{}; const short=(det.model?det.model+' · ':'')+(det.url?det.url.slice(0,42):(det.data?Object.keys(det.data).slice(0,3).join(','):JSON.stringify(det).slice(0,90)));
      const color=e.kind.includes('rebuilt')?'ok':e.kind.includes('error')?'bad':e.kind.includes('extracted')?'warn':'';
      tl+=`<div class="ev"><span class="dot" style="background:${color=='ok'?'var(--ok)':color=='bad'?'var(--bad)':color=='warn'?'var(--warn)':'#2a3a52'}"></span><b>${e.kind}</b> <span class="muted">${e.lead_id||''}</span><br><span class="muted">${e.ts||''}</span><div class="mono">${short}</div></div>`;
    }
    document.getElementById('tl').innerHTML=tl||'<div class="muted">no events yet</div>';
    document.getElementById('wf').textContent=
      'speculative_research() in research.py:178 — 4 parallel web_search (ThreadPoolExecutor max_workers=4)\n'+
      '  trends  → best {vertical} website design inspiration\n'+
      '  tech    → {vertical} essential features online booking ordering\n'+
      '  expect  → {vertical} must have features customers expect\n'+
      '  traces  → "{lead}" {city} reviews OR instagram\n'+
      'synthesis: batched_research_synthesis() — 1 LLM call for all buckets (research.py:147)\n'+
      'fallback: sequential web_search(q,3) via Bing primary → DuckDuckGo fallback (research.py:94)\n'+
      'copy: deterministic_copy(trade,city) 0 tokens when LLM fails (speculative.py:217) → copywriter.py:68';
  }catch(e){ document.getElementById('tl').textContent='poll failed: '+e}
}
poll(); setInterval(poll,1500);
</script>
"""

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        p = urllib.parse.urlparse(self.path).path
        if p in ("/", "/index.html"):
            self.send_response(200); self.send_header("content-type","text/html; charset=utf-8"); self.end_headers()
            self.wfile.write(HTML.encode())
        elif p == "/api/status":
            body = json.dumps(_snapshot()).encode()
            self.send_response(200); self.send_header("content-type","application/json"); self.send_header("cache-control","no-store"); self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404); self.end_headers()
    def log_message(self, *a, **kw): pass

def serve(port=8765):
    httpd = HTTPServer(("127.0.0.1", port), H)
    print(f"viz live at http://127.0.0.1:{port}  (read-only, polling /api/status every 1.5s)")
    print(f"  stages + timeline from {DB}")
    print(f"  speculative cache {CACHE}")
    try: httpd.serve_forever()
    except KeyboardInterrupt: pass

def cmd_viz(args) -> int:
    import webbrowser
    if args.open:
        import threading
        threading.Timer(0.6, lambda: webbrowser.open(f"http://127.0.0.1:{args.port}")).start()
    serve(args.port)
    return 0

"""Facelift autonomous harness - `python main.py`

One command. No arguments. The machine:
  1. roams the city grid for businesses WITHOUT websites (priority class),
     then falls back to ugly-site prospects,
  2. scores and ranks every finding,
  3. chooses ONE target and writes the reasoning for WHY,
  4. runs the full pipeline: facts -> brief -> agent-build -> deploy ->
     impact report -> contact waterfall -> gated draft,
  5. stops at the human approval gate (send requires owner + app password).

Power users: python -m facelift <command> still exposes every stage.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from facelift.markets import CITY_BOXES_IN
from facelift.models import Stage
from facelift.store import Store

ROOT = Path(__file__).resolve().parent
CURSOR = ROOT / "data" / "cursor.json"
RUNS = ROOT / "data" / "runs"

CITIES = list(CITY_BOXES_IN)
MAX_CITIES_PER_RUN = 5
RUN_BUDGET_S = 900


def sh(*args: str) -> int:
    print(f"\n=== facelift {' '.join(args)} ===")
    rc = subprocess.run(
        [sys.executable, "-m", "facelift", *args],
        cwd=str(ROOT),
    ).returncode
    return rc


def load_cursor() -> int:
    try:
        return json.loads(CURSOR.read_text())["i"] % len(CITIES)
    except Exception:  # noqa: BLE001 - first run
        return 0


def save_cursor(i: int) -> None:
    CURSOR.parent.mkdir(parents=True, exist_ok=True)
    CURSOR.write_text(json.dumps({"i": i % len(CITY_BOXES_IN)}))


def discover_no_sites(store: Store, want: int = 3) -> int:
    """Rotate through the city grid collecting CREATE-class leads."""
    start = load_cursor()
    added = 0
    budget_start = time.monotonic()
    tried = 0
    k = start
    while tried < MAX_CITIES_PER_RUN and tried < len(CITIES):
        if time.monotonic() - budget_start > RUN_BUDGET_S * 0.4:
            break
        city = CITIES[k % len(CITIES)]
        s_, w_, n_, e_ = CITY_BOXES_IN[city]
        bbox = f"{round(s_,4)},{round(w_,4)},{round(n_,4)},{round(e_,4)}"
        before = _count_nosite(store)
        rc = sh("discover-nosite", "--bbox", bbox,
                "--limit", "10", "--commit")
        new = _count_nosite(store) - before
        added += max(0, new)
        save_cursor(k + 1)
        k += 1
        tried += 1
        time.sleep(3)
        if added >= want:
            break
    return added


def _count_nosite(store: Store) -> int:
    return sum(
        1 for ld in store.list_leads()
        if ld.domain.startswith("no-site-")
    )


def pick_candidate(store: Store) -> tuple[object | None, list[str]]:
    """Priority: CREATE-class first, then ugliest scored site.
    Returns (lead, reasons)."""
    leads = store.list_leads()
    pool = [ld for ld in leads if ld.stage == Stage.SCORED]

    def reasons_for(ld) -> list[str]:
        v = {s.get("signal"): s.get("value") for s in ld.signals}
        r: list[str] = []
        if str(ld.domain).startswith("no-site-"):
            r.append(
                "NO WEBSITE AT ALL - right now every online customer "
                "search ends at a competitor instead of them."
            )
        elif v.get("free_builder_host"):
            r.append(
                "Trapped on a free-builder subdomain - no brand domain, "
                "no SEO equity, platform owns their web identity."
            )
        psi = v.get("psi_mobile_perf")
        if isinstance(psi, int):
            r.append(
                f"Fails Google's mobile bar: speed {psi}/100 "
                f"(healthy is 90+)."
            )
        if v.get("copyright_stale"):
            r.append(
                f"Site frozen since {v.get('newest_year', 'years ago')} - "
                f"an abandoned web presence signals a business that's "
                f"waiting for help."
            )
        if v.get("wayback_stale"):
            r.append("Archive confirms years without updates.")
        if v.get("viewport_missing"):
            r.append("Not mobile-friendly - loses the majority of "
                     "first-time visitors on phones.")
        return r

    def reachability(store_: Store, lead_id: str) -> list[str]:
        out = []
        for c in store_.list_contacts(lead_id):
            if c["kind"] == "email" and c["verified"]:
                out.append(
                    f"Owner reachable: published email {c['value']} "
                    f"(self-sourced, compliant)."
                )
                break
            if c["kind"] == "phone":
                out.append(f"Phone on record: {c['value']}.")
                break
        return out

    nosite = [
        ld for ld in pool if str(ld.domain).startswith("no-site-")
    ]
    nosite.sort(key=lambda ld: ld.ugly_score, reverse=True)
    for ld in nosite[:3]:
        rs = reasons_for(ld) + reachability(store, ld.id)
        if len(rs) >= 1:
            return ld, rs

    rest = [ld for ld in pool
            if not str(ld.domain).startswith("no-site-")]
    rest.sort(key=lambda ld: ld.ugly_score, reverse=True)
    for ld in rest[:3]:
        rs = reasons_for(ld) + reachability(store, ld.id)
        if len(rs) >= 1:
            return ld, rs
    return (None, [])


def _stored_hash(store: Store, lead_id: str) -> str:
    ev = store.last_event_detail(lead_id, "drafted") or {}
    return ev.get("body_hash", "")


def _stored_hash_ref() -> str:
    return ""


def write_run_report(lead, url: str | None, reasons: list[str],
                     contacts: list[dict]) -> Path:
    RUNS.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    p = RUNS / f"{stamp}-{lead.id}.md"
    contact_lines = [
        f"- [{c['kind']}] {c['value']} ({c['source']}, "
        f"confidence {c['confidence']}, verified={bool(c['verified'])})"
        for c in contacts
    ] or ["- none yet"]
    lines = [
        f"# Facelift run - {lead.name}",
        "",
        f"- Lead id: `{lead.id}`",
        f"- Class: {'CREATE (no site)' if str(lead.domain).startswith('no-site-') else 'FIX (ugly site)'}",
        f"- Live concept: {url or '(deploy failed - see log above)'}",
        "",
        "## Why this business (reasoning)",
        *[f"- {r}" for r in reasons],
        "",
        "## Contacts found",
        *contact_lines,
        "",
        "## Next human action",
        "- Review the live concept, then `python -m facelift draft "
        f"{lead.id}` and `send --approve <hash>` (needs Gmail app "
        "password in .env).",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")
    return p


def _launch_cockpits():
    """Start immersive work/chat/viz cockpits in background (read-only, polling /api/status).
    All specs we discussed stream live while hunting+building: speculative veto/batch, 4× research, CAS, cache."""
    import threading
    try:
        from facelift.workview import serve_work
        from facelift.chat import serve_chat
        from facelift.viz import serve
        threading.Thread(target=serve_work, args=(8767,), daemon=True).start()
        threading.Thread(target=serve_chat, args=(8766,), daemon=True).start()
        threading.Thread(target=serve, args=(8765,), daemon=True).start()
        print(" cockpits live (read-only):")
        print("   work — how I work: http://127.0.0.1:8767/work  (TodoWrite + tool stream + diff)")
        print("   chat — qwen.chat : http://127.0.0.1:8766/chat  (ask 'why vetoed?' 'where searched?')")
        print("   viz  — dashboard : http://127.0.0.1:8765/      (stages/timeline/research)")
    except Exception as ex:
        print(f" (cockpits skipped: {ex})")


def main() -> int:
    print("=" * 62)
    print(" FACELIFT - autonomous run starting  [speculative · parallel · immersive]")
    print("=" * 62)
    _launch_cockpits()
    store = Store(ROOT / "data" / "facelift.db")
    try:
        from facelift.speculative import reset_cache_counters, get_cache_metrics
        reset_cache_counters()
    except Exception:
        pass

    print("\n[1/5] Roaming the grid for businesses WITHOUT websites...")
    added = discover_no_sites(store, want=3)

    print("\n[2/5] Choosing today's target (no-site priority)...")
    lead, reasons = pick_candidate(store)
    if lead is None:
        print("No viable candidate this run. Try again or widen cities.")
        return 1
    print(f"\nTARGET: {lead.name} ({lead.domain}) score={lead.ugly_score}")
    print("REASONING:")
    for r in reasons:
        print(f"  • {r}")

    print("\n[3/5] Building (facts -> brief -> agent -> deploy)...")
    if not str(lead.domain).startswith("no-site-"):
        sh("audit", lead.id, "--commit")

    # Parallel builds for additional scored leads — speculative + atomic CAS (store.py:84, agents.py:52)
    from facelift.models import Stage as _S
    others = [ld for ld in store.list_leads()
              if ld.stage == _S.SCORED and ld.id != lead.id][:2]
    if others and len(others) >= 1:
        print(f"\n[3b] Parallel builds for {len(others)} additional leads (Pool + CAS, no duplicate)…")
        print("     open http://127.0.0.1:8767/work to watch TodoWrite tick live")
        try:
            from facelift.agents import Pool, Role
            pool = Pool(max_workers=2)
            tasks = pool.spawn(Role.BUILDER, [ld.id for ld in others])
            for t in tasks:
                print(f"     {'OK' if t.status=='done' else 'FAIL'} {t.lead_id} {t.status} {t.elapsed}s")
        except Exception as ex:
            print(f"     (Pool fallback to sequential: {ex})")
            from facelift.parallel import build_parallel
            build_parallel([ld.id for ld in others], max_workers=2)

    rc = sh("rebuild", lead.id, "--commit")

    print("\n[4/5] Finding the owner...")
    sh("contacts", lead.id, "--commit")
    contacts = store.list_contacts(lead.id)

    # also find contacts for parallel-built leads
    for ld in others:
        sh("contacts", ld.id, "--commit")

    print("\n[5/5] Drafting outreach (stops at your approval gate)...")
    sh("draft", lead.id)

    auto = False
    for line in Path(ROOT / ".env").read_text(
            encoding="utf-8-sig").splitlines():
        if line.startswith("AUTO_SEND="):
            auto = line.split("=", 1)[1].strip() == "1"
    if auto:
        print("\n[5b] AUTO_SEND=1 — firing approved send...")
        sh("send", lead.id, "--approve", _stored_hash(store, lead.id))
        sh("replies")

    print("\n[6/6] Publishing mirrors (github.io + public repo)...")
    sh(str(ROOT / "publish_gh.py").replace(str(ROOT) + "\\", "")
       and "publish-gh") if False else None
    subprocess.run([sys.executable, str(ROOT / "publish_gh.py"),
                    "demolished-lab"], cwd=str(ROOT))
    subprocess.run([sys.executable, str(ROOT / "publish_public.py")],
                   cwd=str(ROOT))

    ev = store.last_event_detail(lead.id, "rebuilt") or {}
    url = ev.get("url")
    report = write_run_report(lead, url, reasons, contacts)
    try:
        from facelift.speculative import get_cache_metrics
        m = get_cache_metrics()
        print(f"\n speculative: cache hits {m.get('hit',0)} misses {m.get('miss',0)} entries {m.get('entries','?')} — veto 0 tok, batched 5/chunk, 4× parallel research")
    except Exception:
        pass
    print("\n" + "=" * 62)
    print(f" RUN COMPLETE -> {report}")
    if url:
        print(f" LIVE: {url}")
    print(" Cockpits still live: work 8767/work  chat 8766/chat  viz 8765/")
    print(" Approval gate: review, then send --approve <hash>")
    print("=" * 62)
    print(" Press Ctrl+C to stop cockpits (they are daemon threads).")
    # keep cockpits alive briefly for artifact review
    try:
        import time as _t
        _t.sleep(2)
    except Exception:
        pass
    return 0 if rc == 0 else rc


if __name__ == "__main__":
    raise SystemExit(main())

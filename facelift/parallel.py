"""Parallel build engine — multiple leads built simultaneously.

Each rebuild is fully independent (different dist, different worker name,
different KV namespace). The shared SQLite store uses WAL mode for
concurrent access. The only serialized resource is the Cloudflare API
(rate-limited by CF, not by us).

Usage:
    python -m facelift batch-parallel --n 3

Or from main.py:
    from facelift.parallel import build_parallel
    build_parallel(store, lead_ids, max_workers=3)
"""

from __future__ import annotations

import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build_one(lead_id: str) -> dict:
    """Run a single rebuild in a subprocess. Returns result dict."""
    t0 = time.monotonic()
    proc = subprocess.run(
        [sys.executable, "-m", "facelift", "rebuild", lead_id, "--commit"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=900,
    )
    mins = round((time.monotonic() - t0) / 60, 1)
    output = (proc.stdout or "") + (proc.stderr or "")
    success = "deployed:" in output or "NATIVE DEPLOY" in output.upper()
    url = ""
    for line in output.splitlines():
        if "deployed:" in line:
            url = line.split("deployed:")[1].strip()
            break
    return {
        "lead_id": lead_id,
        "success": success and proc.returncode == 0,
        "url": url,
        "mins": mins,
        "rc": proc.returncode,
        "tail": output[-200:] if not success else "",
    }


def build_parallel(lead_ids: list[str], max_workers: int = 3) -> list[dict]:
    """Build multiple sites in parallel. Returns results sorted by time."""
    results = []
    t0 = time.monotonic()
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(build_one, lid): lid for lid in lead_ids}
        for fut in as_completed(futures):
            lid = futures[fut]
            try:
                r = fut.result()
                results.append(r)
                status = "✅" if r["success"] else "❌"
                print(f"  {status} {lid}: {r['url'] or r['tail'][:60]} "
                      f"({r['mins']}min)")
            except Exception as ex:  # noqa: BLE001
                results.append({"lead_id": lid, "success": False,
                                "url": "", "mins": 0,
                                "tail": str(ex)[:80], "rc": -1})
                print(f"  ❌ {lid}: {str(ex)[:60]}")
    total = round((time.monotonic() - t0) / 60, 1)
    print(f"\nparallel build: {len(results)} sites in {total}min "
          f"({max_workers} workers)")
    return results

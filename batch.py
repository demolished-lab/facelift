"""R1 — Quality validation batch: rebuild top candidates, judge cold.

Picks the highest-scoring unrebuilt leads, runs the full personalized
harness on each, and writes a showcase verdict table the owner can review:
data/runs/batch-report.md
"""

import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from facelift.store import Store  # noqa: E402
from facelift.models import Stage  # noqa: E402
from facelift import builder_agent  # noqa: E402


def sh(*args):
    return subprocess.run(
        [sys.executable, "-m", "facelift", *args], cwd=str(ROOT)
    ).returncode


def main(n_builds: int = 2):
    store = Store(ROOT / "data" / "facelift.db")
    cands = [ld for ld in store.list_leads()
             if ld.stage == Stage.SCORED][:n_builds]
    if not cands:
        print("no scored candidates - run discover-nosite first")
        return 1

    rows = []
    for ld in cands:
        print(f"\n{'#' * 60}\n# BATCH BUILD: {ld.name}\n{'#' * 60}")
        t0 = time.time()
        rc = sh("rebuild", ld.id, "--commit")
        mins = round((time.time() - t0) / 60, 1)

        ev = store.last_event_detail(ld.id, "rebuilt") or {}
        url = ev.get("url", "")
        dist = None
        for d in Path(ROOT / "builds").glob(f"{ev.get('worker', '*')}"):
            dist = d / "dist"
        fails = builder_agent.quality_check(dist) if dist and dist.exists() \
            else ["dist not found"]
        rows.append({
            "name": ld.name, "url": url, "mins": mins,
            "rc": rc, "gate": "PASS" if not fails else f"{len(fails)} issues",
            "fails": fails,
        })

    lines = ["# R1 Batch Report\n"]
    for r in rows:
        lines.append(
            f"- **{r['name']}** — {r['rc'] and 'ERR' or 'built'} in "
            f"{r['mins']}min · gate: {r['gate']} · {r['url']}"
        )
        for f in r.get("fails", [])[:3]:
            lines.append(f"    - {f}")
    report = ROOT / "data" / "runs" / "batch-report.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("\n".join(lines), encoding="utf-8")
    print("\n" + "\n".join(lines))
    print(f"\nbatch complete -> {report}")
    return 0


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    raise SystemExit(main(n))

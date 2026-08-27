"""Site audit engine (PRD FR-2.1).

Primary: local Lighthouse CLI (unlimited, free, no network quota) via
installed npm package + local Chrome. Optional: PSI API when
FACELIFT_PSI_API_KEY is set in .env (adds Google field/CrUX data).
Both return the same summary shape.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

from .llm import _load_env

PSI_URL = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
MIN_GAP_S = 5.0
USER_AGENT = "facelift/0.1"
LH_CATEGORIES = "performance,seo,accessibility,best-practices"

_last_call = 0.0


def _pace() -> None:
    global _last_call
    wait = MIN_GAP_S - (time.monotonic() - _last_call)
    if wait > 0:
        time.sleep(wait)
    _last_call = time.monotonic()


def psi(url: str, strategy: str = "mobile") -> dict:
    _load_env()
    q: dict[str, str | list[str]] = {
        "url": url,
        "strategy": strategy,
        "category": ["performance", "seo", "accessibility", "best-practices"],
    }
    key = os.environ.get("FACELIFT_PSI_API_KEY")
    if key:
        q["key"] = key
    full = PSI_URL + "?" + urllib.parse.urlencode(q, doseq=True)
    req = urllib.request.Request(full, headers={"User-Agent": USER_AGENT})
    last_err: Exception | None = None
    for attempt in range(3):
        _pace()
        try:
            with urllib.request.urlopen(req, timeout=150) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as ex:
            last_err = ex
            if ex.code in (429, 500, 503):
                time.sleep(6 * (attempt + 1))
                continue
            break
        except Exception as ex:  # noqa: BLE001 - surfaced to caller
            last_err = ex
    raise RuntimeError(f"psi failed ({strategy}): {last_err}")


def summarize(data: dict) -> dict:
    lr = data.get("lighthouseResult") or data
    out: dict = {}
    for name, cat in lr.get("categories", {}).items():
        if isinstance(cat.get("score"), (int, float)):
            out[name] = round(cat["score"] * 100)
    le = data.get("loadingExperience", {})
    if le.get("overall_category"):
        out["field_category"] = le["overall_category"]
    audits = lr.get("audits", {})
    lcp = audits.get("largest-contentful-paint", {}).get("numericValue")
    if isinstance(lcp, (int, float)):
        out["lcp_s"] = round(lcp / 1000, 1)
    return out


def _lh_binary() -> list[str]:
    lh = shutil.which("lighthouse")
    if lh:
        return [lh]
    return ["npx", "--yes", "lighthouse"]


def _lighthouse(url: str, form_factor: str, _retry: bool = True) -> dict:
    run_tmp = tempfile.mkdtemp(prefix="facelift-lh-")
    with tempfile.NamedTemporaryFile(
        suffix=".json", delete=False, dir=os.environ.get("TEMP")
    ) as tf:
        out_path = tf.name
    cmd = _lh_binary() + [
        url,
        "--quiet",
        "--output=json",
        f"--output-path={out_path}",
        f"--only-categories={LH_CATEGORIES}",
        f"--form-factor={form_factor}",
        '--chrome-flags=--headless=new --disable-gpu --no-first-run',
        "--max-wait-for-load=60000",
    ]
    if form_factor == "mobile":
        cmd.append("--screenEmulation.mobile")
    env = dict(os.environ)
    env["TMP"] = run_tmp
    env["TEMP"] = run_tmp
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=240, env=env
        )
        if not os.path.exists(out_path) or os.path.getsize(out_path) < 2:
            raise RuntimeError(
                f"lighthouse failed ({form_factor}): "
                f"rc={proc.returncode} {proc.stderr[-250:]}"
            )
        with open(out_path, encoding="utf-8") as fh:
            return json.load(fh)
    except (RuntimeError, subprocess.TimeoutExpired):
        shutil.rmtree(run_tmp, ignore_errors=True)
        if _retry:
            time.sleep(3)
            return _lighthouse(url, form_factor, _retry=False)
        raise
    finally:
        shutil.rmtree(run_tmp, ignore_errors=True)
        try:
            os.unlink(out_path)
        except OSError:
            pass


def audit_domain(domain: str) -> tuple[dict, dict | None]:
    target = domain if domain.startswith("http") else f"https://{domain}/"
    _load_env()
    if os.environ.get("FACELIFT_PSI_API_KEY"):
        mobile = summarize(psi(target, "mobile"))
        desktop = summarize(psi(target, "desktop"))
        return mobile, desktop
    mobile = summarize(_lighthouse(target, "mobile"))
    try:
        desktop = summarize(_lighthouse(target, "desktop"))
    except Exception as ex:  # noqa: BLE001 - mobile is the decision metric
        desktop = {"error": f"desktop unavailable: {str(ex)[:100]}"}
    return mobile, desktop

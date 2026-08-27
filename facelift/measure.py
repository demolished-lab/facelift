"""Staleness scoring and prospect filtering (PRD FR-1.2, D5 revised).

Deterministic pure functions of fetched homepage HTML so results are
testable offline. Excluded: institutions/chains/directories that will never
buy a facelift. Free-builder hosts auto-qualify (always prospects).
"""

from __future__ import annotations

import datetime as dt
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

import urllib.error
import urllib.request

from .models import Lead

USER_AGENT = "facelift/0.1 (owner-operated agency research; contact: operator@example.com)"
FETCH_TIMEOUT_S = 12
MAX_BYTES = 2_000_000
UGLY_PASS = 55

FREE_BUILDER_SUFFIXES = (
    "wixsite.com", "weebly.com", "blogspot.com", "wordpress.com",
    "business.site", "godaddysites.com", "jimdosite.com", "webnode.com",
    "great-site.net", "rf.gd", "epizy.com", "000webhostapp.com",
    "sites.google.com", "glitch.me", "netlify.app" ,
)

EXCLUDE_DOMAIN_PARTS = (
    "bank", ".gov", ".gov.in", "nic.in", "ac.in", "iit", "university",
    "justdial", "indiamart", "tripadvisor", "yelp.com", "zomato", "swiggy",
    "practo", "olympusmylife", "facebook.com", "instagram.com",
)
EXCLUDE_NAME_PARTS = (
    "bank", "government", "municipal", "university", "college",
    "ministry", "embassy", "petrol pump", "atm",
)


def is_excludable(lead: Lead) -> str | None:
    d = lead.domain.lower()
    n = lead.name.lower()
    for part in EXCLUDE_DOMAIN_PARTS:
        if part in d:
            return f"domain~{part}"
    for part in EXCLUDE_NAME_PARTS:
        if part in n:
            return f"name~{part}"
    return None


def _url_candidates(domain: str) -> list[str]:
    if domain.startswith(("http://", "https://")):
        return [domain]
    return [f"https://{domain}/", f"http://{domain}/"]


def fetch_homepage(domain: str) -> str:
    last_err: Exception | None = None
    for url in _url_candidates(domain):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT_S) as resp:
                raw = resp.read(MAX_BYTES)
            return raw.decode("utf-8", errors="ignore")
        except Exception as ex:  # noqa: BLE001 - triaged by caller/caveat
            last_err = ex
    raise RuntimeError(f"fetch failed: {last_err}")


def extract_signals(html: str, domain: str) -> list[dict]:
    low = html.lower()
    today = dt.date.today()

    years = [int(y) for y in re.findall(r"(?:©|\(c\)|&copy;|copyright)[^0-9]{0,20}(20\d{2})", low)]
    newest = max(years) if years else None

    jquery_old = bool(re.search(r"jquery[./-]*1\.\d+", low))
    legacy = sum(bool(re.search(t, low)) for t in (r"<marquee", r"<font ", r"<center", r"<frameset"))
    weight_kb = len(html) // 1024

    signals = [
        {"signal": "viewport_missing",
         "value": '<meta name="viewport"' not in low},
        {"signal": "free_builder_host",
         "value": any(domain.endswith(s) or s in domain for s in FREE_BUILDER_SUFFIXES)},
        {"signal": "copyright_stale",
         "value": bool(newest and newest <= today.year - 2), "newest_year": newest},
        {"signal": "jquery_1x", "value": jquery_old},
        {"signal": "legacy_tags", "value": legacy},
        {"signal": "table_layout",
         "value": "<table" in low and ("bgcolor" in low or "cellpadding" in low)},
        {"signal": "insecure_asset_refs", "value": 'src="http://' in low},
        {"signal": "meta_description_missing",
         "value": 'name="description"' not in low},
        {"signal": "weight_kb", "value": weight_kb},
    ]
    return signals


def score(signals: list[dict]) -> int:
    v = {s["signal"]: s.get("value") for s in signals}
    total = 15
    if v.get("viewport_missing"):
        total += 25
    if v.get("copyright_stale"):
        total += 12
    if v.get("jquery_1x"):
        total += 10
    if v.get("legacy_tags"):
        total += 9
    if v.get("table_layout"):
        total += 8
    if v.get("insecure_asset_refs"):
        total += 10
    if v.get("meta_description_missing"):
        total += 4
    if isinstance(v.get("weight_kb"), int) and v["weight_kb"] > 300:
        total += 6
    if v.get("free_builder_host"):
        return max(total + 20, 70)
    psi = v.get("psi_mobile_perf")
    if isinstance(psi, int):
        total += 20 if psi < 50 else (8 if psi < 75 else -5)
    if v.get("wayback_stale"):
        total += 10
    if v.get("no_wayback_history"):
        total += 5
    if v.get("no_website"):
        return 75
    return min(max(total, 0), 100)


def score_lead(lead: Lead) -> tuple[int, list[dict], str | None]:
    why = is_excludable(lead)
    if why:
        return 0, [{"signal": "excluded", "value": True, "reason": why}], why
    html = fetch_homepage(lead.domain)
    signals = extract_signals(html, lead.domain)
    return score(signals), signals, None


def score_many(leads: list[Lead], workers: int = 8):
    """Returns list of (lead, score, signals, error|None). Threaded per D5."""
    results: list[tuple[Lead, int, list[dict], str | None]] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(score_lead, ld): ld for ld in leads}
        for fut in as_completed(futures):
            ld = futures[fut]
            try:
                sc, sig, err = fut.result()
                results.append((ld, sc, sig, err))
            except Exception as ex:  # noqa: BLE001 - surfaced, never crashes batch
                results.append((ld, 0, [], str(ex)))
    results.sort(key=lambda r: r[1], reverse=True)
    return results

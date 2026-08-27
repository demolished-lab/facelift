"""Wayback Machine staleness enrichment (PRD FR-1.2 signal source).

Internet Archive CDX API: how old is this site's snapshot history and when
was it last captured. A site untouched for 2+ years is an abandoned web
presence - prime facelift prospect even if it "loads fine".
"""

from __future__ import annotations

import datetime as dt
import json
import urllib.request

CDX_URL = "https://web.archive.org/cdx/search/cdx"
USER_AGENT = "facelift/0.1 (owner-operated agency research; contact: operator@example.com)"


def snapshot_span(domain: str) -> dict | None:
    url = (
        f"{CDX_URL}?url={domain}&output=json&fl=timestamp"
        "&collapse=timestamp:4&limit=300"
    )
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=45) as resp:
        data = json.load(resp)
    if not data or len(data) < 2:
        return None
    years = [
        int(row[0][:4])
        for row in data[1:]
        if row and len(row[0]) >= 4 and row[0][:4].isdigit()
    ]
    if not years:
        return None
    return {"oldest": min(years), "newest": max(years), "snapshots": len(years)}


def enrich_signal(domain: str) -> dict:
    try:
        span = snapshot_span(domain)
    except Exception as ex:  # noqa: BLE001 - archive outages are routine
        return {"signal": "wayback_error", "value": True, "detail": str(ex)[:80]}
    current = dt.date.today().year
    if span is None:
        return {"signal": "no_wayback_history", "value": True}
    stale = span["newest"] <= current - 2
    return {
        "signal": "wayback_stale",
        "value": stale,
        "newest": span["newest"],
        "oldest": span["oldest"],
    }

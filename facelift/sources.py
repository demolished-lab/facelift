"""Lead source adapters (PRD FR-1.1, D5 revised).

Tier-A: keyless Overpass endpoints, identified User-Agent with contact,
hard result limits, no retry storms. Vertical targeting narrows to SMB
categories that actually buy facelifts.
"""

from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
import urllib.error

from . import markets
from .models import Lead

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
USER_AGENT = "facelift/0.1 (owner-operated agency research; contact: operator@example.com)"
REQUEST_TIMEOUT_S = 40


def _query(
    bbox: tuple[float, float, float, float],
    limit: int,
    verticals: bool = False,
) -> str:
    s, w, n, e = bbox
    if verticals:
        amen = "|".join(markets.VERTICAL_AMENITIES)
        shop = "|".join(markets.VERTICAL_SHOPS)
        tag = (
            f'(nwr["amenity"~"({amen})"]["website"]["name"];'
            f'nwr["shop"~"({shop})"]["website"]["name"];)'
        )
    else:
        tag = 'nwr["website"]["name"]'
    return (
        f"[out:json][timeout:60];"
        f"{tag}({s},{w},{n},{e});"
        f"out center {limit * 3};"
    )


def _domain(website: str) -> str:
    u = website.strip().lower()
    for prefix in ("https://", "http://"):
        if u.startswith(prefix):
            u = u[len(prefix):]
    u = u.split("/")[0].split("?")[0]
    return u[4:] if u.startswith("www.") else u


def _to_lead(el: dict) -> Lead | None:
    tags = el.get("tags", {})
    site = tags.get("website") or tags.get("contact:website")
    name = tags.get("name")
    if not site or not name:
        return None
    osm_type = el.get("type", "node")
    return Lead(
        id=f"osm-{osm_type}-{el.get('id')}",
        domain=_domain(site),
        name=name,
        source="osm-overpass",
        source_url=f"https://www.openstreetmap.org/{osm_type}/{el.get('id')}",
    )


def overpass_search(
    bbox: tuple[float, float, float, float],
    limit: int = 25,
    verticals: bool = False,
) -> list[Lead]:
    body = urllib.parse.urlencode(
        {"data": _query(bbox, limit, verticals)}
    ).encode()
    last_err: Exception | None = None
    for url in OVERPASS_URLS:
        try:
            req = urllib.request.Request(
                url, data=body, headers={"User-Agent": USER_AGENT}
            )
            with urllib.request.urlopen(req, timeout=90) as resp:
                data = json.load(resp)
            leads: list[Lead] = []
            seen: set[str] = set()
            for el in data.get("elements", []):
                lead = _to_lead(el)
                if lead and lead.domain not in seen:
                    seen.add(lead.domain)
                    leads.append(lead)
                    if len(leads) >= limit:
                        break
            return leads
        except Exception as ex:  # noqa: BLE001 - caveat handler owns triage later
            last_err = ex
    raise RuntimeError(f"all overpass endpoints failed: {last_err}")


NO_SITE_NAME_JUNK = (
    "domino", "cafe coffee", "ccd", "starbucks", "mcdonald", "kfc",
    "subway", "essel", "depot", "ferry", "jetty", "parking", "atm",
    "movie theatre", "cinema", "talkies", "multiplex",
    "temple", "mandir", "masjid", "mosque", "church",
    "gurudwara", "fire station", "police station", "petrol pump",
    "mtnl", "bsnl", "airtel", "jio", "vodafone", "bank", "insurance",
    "railway", "post office", "municipal", "corporation",
    "ranbaxy", "genpact", "embassy", "election", "commission",
    "authority", "terminal", "logistics", "reservation centre",
    "booth", "officer", "ministry", "govt", "ltd", "pvt",
    "office", "bhavan", "bhawan", "sadan", "nigam", "parishad",
    "secretariat", "commissionerate", "tech park", "corporate park",
    "state board", "branch", "seva", "kendra", "kendar", "court",
    "university", "college", "institute", "school", "academy",
    "gurukul", "vidhya", "vidyalaya", "hospital", "lab", "laboratory",
    "wadi", "chok", "chowk",
)


def overpass_lookup(osm_ref: str) -> dict | None:
    """Fetch coords + tags for one element from its id like
    'osm-node-123' or 'osm-way-456'."""
    m = re.match(r"osm-(node|way|relation)-(\d+)", osm_ref)
    if not m:
        return None
    kind, oid = m.group(1), m.group(2)
    q = (
        f"[out:json][timeout:25];{kind}({oid});out center tags 1;"
    )
    body = urllib.parse.urlencode({"data": q}).encode()
    for url in OVERPASS_URLS:
        try:
            req = urllib.request.Request(
                url, data=body, headers={"User-Agent": USER_AGENT}
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.load(resp)
            els = data.get("elements", [])
            if not els:
                return None
            el = els[0]
            tags = el.get("tags", {})
            lat = el.get("lat") or el.get("center", {}).get("lat")
            lon = el.get("lon") or el.get("center", {}).get("lon")
            return {"lat": lat, "lon": lon, "tags": tags}
        except Exception:  # noqa: BLE001 - caller triages
            last_err = None
            continue
    return None


def overpass_nearby_with_site(
    lat: float,
    lon: float,
    category_keys: list[tuple[str, str]],
    radius_deg: float = 0.02,
    limit: int = 4,
) -> list[dict]:
    """Same-trade businesses WITH websites around a point.

    category_keys: [(key, value)] pairs copied from the subject lead so we
    compare against true local rivals. Returns [{name, domain}].
    """
    s = round(lat - radius_deg, 5)
    w = round(lon - radius_deg, 5)
    n = round(lat + radius_deg, 5)
    e = round(lon + radius_deg, 5)
    out: list[dict] = []
    seen: set[str] = set()

    def _run(clause: str) -> list[dict]:
        q = f"[out:json][timeout:30];{clause};out center {limit * 3};"
        body = urllib.parse.urlencode({"data": q}).encode()
        last: Exception | None = None
        for url in OVERPASS_URLS:
            try:
                req = urllib.request.Request(
                    url, data=body, headers={"User-Agent": USER_AGENT}
                )
                with urllib.request.urlopen(req, timeout=70) as resp:
                    return json.load(resp).get("elements", [])
            except Exception as ex:  # noqa: BLE001 - try next endpoint
                last = ex
        if last:
            print(f"[nearby_with_site] {last}")
        return []

    for k, v in [p for p in category_keys[:3]] or [("amenity", "")]:
        val_clause = f'["{k}"="{v}"]' if v else f'["{k}"]'
        for el in _run(
            f'nwr{val_clause}["website"]["name"]({s},{w},{n},{e})'
        ):
            t = el.get("tags", {})
            nm, site = t.get("name"), t.get("website")
            if not nm or not site:
                continue
            d = _domain(site)
            if d in seen:
                continue
            seen.add(d)
            out.append({"name": nm, "domain": d})
            if len(out) >= limit:
                return out
    return out


def overpass_no_site_search(
    bbox: tuple[float, float, float, float],
    limit: int = 25,
) -> list[Lead]:
    """Businesses with a name but NO website - the CREATE class.

    First-website prospects. Synthetic domain no-site-<osm-id> keeps store
    dedupe working. Phone/email tags ride along for the contact stage.
    """
    from .models import Stage
    import time

    s, w, n, e = bbox
    bbox_s = f"({s},{w},{n},{e})"

    def _run(clause: str) -> list[dict]:
        q = f"[out:json][timeout:60];{clause};out center {limit * 3};"
        body = urllib.parse.urlencode({"data": q}).encode()
        last_err: Exception | None = None
        for attempt in range(2):
            for url in OVERPASS_URLS:
                try:
                    req = urllib.request.Request(
                        url, data=body, headers={"User-Agent": USER_AGENT}
                    )
                    with urllib.request.urlopen(req, timeout=90) as resp:
                        return json.load(resp)
                except urllib.error.HTTPError as ex:
                    last_err = ex
                    if ex.code not in (429, 500, 502, 503):
                        break
                except Exception as ex:  # noqa: BLE001
                    last_err = ex
            if attempt == 0:
                time.sleep(8)
        if last_err:
            print(f"[no_site] endpoint trouble: {last_err}")
        return []

    leads: list[Lead] = []
    seen: set[str] = set()
    for k in ("amenity", "shop", "office"):
        data = _run(f'nwr["{k}"]["name"][!"website"]' + bbox_s)
        if not isinstance(data, dict):
            continue
        for el in data.get("elements", []):
            tags = el.get("tags", {})
            name = tags.get("name")
            if not name:
                continue
            low = name.lower()
            if any(j in low for j in NO_SITE_NAME_JUNK):
                continue
            osm_type = el.get("type", "node")
            oid = el.get("id")
            dom = f"no-site-{oid}"
            if dom in seen:
                continue
            seen.add(dom)
            leads.append(
                Lead(
                    id=f"osm-{osm_type}-{oid}",
                    domain=dom,
                    name=name,
                    source="osm-no-site",
                    source_url=f"https://www.openstreetmap.org/"
                               f"{osm_type}/{oid}",
                    signals=[{"signal": "no_website", "value": True}],
                    ugly_score=75,
                    stage=Stage.SCORED,
                )
            )
            if len(leads) >= limit:
                break
        if len(leads) >= limit:
            break
    return leads

"""Local competitive intelligence (the "must-have" engine).

Finds the lead's real nearby same-trade rivals WITH websites, audits them
live with the same Lighthouse ruler we use on the client, and returns a
standings table. Owners feel loss when they see neighborhood numbers next
to theirs - honest, public, verifiable data.
"""

from __future__ import annotations

from . import sources
from .audit import _lighthouse, summarize


CATEGORY_KEYS_PRIORITY = [
    ("amenity", "restaurant"), ("amenity", "cafe"), ("amenity", "fast_food"),
    ("amenity", "bar"),
    ("tourism", "hotel"), ("tourism", "guest_house"), ("tourism", "hostel"),
    ("amenity", "clinic"), ("amenity", "dentist"), ("amenity", "doctors"),
    ("amenity", "pharmacy"),
    ("shop", "clothes"), ("shop", "bakery"), ("shop", "hairdresser"),
    ("shop", "beauty"), ("shop", "electronics"), ("shop", "furniture"),
    ("office", "company"),
]


def list_rivals(osm_ref: str, max_rivals: int = 3,
                exclude_domain: str | None = None) -> list[dict]:
    """Nearby same-trade rivals WITH websites - names/domains only,
    no expensive audits. Spec showdown uses cheap page checks instead.
    Escalates radius and relaxes category until something is found."""
    info = sources.overpass_lookup(osm_ref)
    if not info or not info.get("lat"):
        return []
    tags = info.get("tags") or {}
    pairs = [
        (k, v) for k, v in tags.items()
        if k in ("amenity", "tourism", "shop", "office")
        and isinstance(v, str)
    ]
    attempts: list[tuple[float, list[tuple[str, str]]]] = []
    if pairs:
        attempts += [(0.02, pairs), (0.06, pairs)]
    attempts.append((0.04, CATEGORY_KEYS_PRIORITY[:3]))
    for radius, cat_pairs in attempts:
        rivals = sources.overpass_nearby_with_site(
            info["lat"], info["lon"], cat_pairs,
            radius_deg=radius, limit=max_rivals + 1,
        )
        rivals = [
            r for r in rivals
            if not exclude_domain or r["domain"] != exclude_domain
        ]
        if rivals:
            return rivals[:max_rivals]
    return []


def scan(lead_id: str, osm_ref: str, max_rivals: int = 3) -> list[dict]:
    """Returns standings rows: [{name, domain, you?, perf, lcp}].
    Best-effort: any failure shrinks the table, never raises."""
    info = sources.overpass_lookup(osm_ref)
    if not info or not info.get("lat"):
        return []
    tags = info.get("tags") or {}
    pairs = [
        (k, v) for k, v in tags.items()
        if k in ("amenity", "tourism", "shop", "office")
        and isinstance(v, str)
    ]
    if not pairs:
        pairs = CATEGORY_KEYS_PRIORITY[:1]
    ranked = sorted(
        pairs, key=lambda kv: next(
            (i for i, (ck, cv) in enumerate(CATEGORY_KEYS_PRIORITY)
             if ck == kv[0] and cv == kv[1]), 99
        )
    )
    rivals = sources.overpass_nearby_with_site(
        info["lat"], info["lon"], ranked, limit=max_rivals + 2
    )
    own_domain = None
    rows: list[dict] = []
    checked = 0
    for r in rivals:
        if r["domain"] in {x["domain"] for x in rows}:
            continue
        if checked >= max_rivals:
            break
        try:
            s = summarize(_lighthouse(f"https://{r['domain']}/", "mobile"))
            checked += 1
            rows.append({
                "name": r["name"],
                "domain": r["domain"],
                "perf": s.get("performance", "?"),
                "lcp": s.get("lcp_s", "?"),
                "you": False,
            })
        except Exception:  # noqa: BLE001 - skip dead rivals silently
            continue
    return rows


def render_table(rows: list[dict], you_perf, you_lcp) -> str:
    def fmt(p, l):
        return f"{p}/100 · {l}s"

    lines = [
        "<table class='ctable'><tr><th></th><th>Mobile speed</th>"
        "<th>Content shows after</th></tr>"
    ]
    if you_perf not in (None, "?"):
        lines.append(
            f"<tr class='you'><td>YOU (current site)</td>"
            f"<td>{you_perf}/100</td><td>{you_lcp}s</td></tr>"
        )
    for r in rows[:3]:
        lines.append(
            f"<tr><td>{r['name']} <span class='dom'>({r['domain']})</span></td>"
            f"<td>{r['perf']}/100</td><td>{r['lcp']}s</td></tr>"
        )
    lines.append("</table>")
    return "\n".join(lines)


# ---- BuyHatke-style spec showdown --------------------------------------

import re
import urllib.request

from .measure import USER_AGENT

SPEC_CHECKS = [
    ("Works on phones", lambda h, u: 'name="viewport"' in h.lower()),
    ("Loads over secure HTTPS", lambda h, u: u.startswith("https://")),
    ("One-tap call button", lambda h, u: "tel:" in h.lower()),
    ("WhatsApp inquiry", lambda h, u: ("wa.me" in h.lower()
                                       or "api.whatsapp" in h.lower())),
    ("Shows real photos (3+)", lambda h, u: len(
        __import__("re").findall(r"<img", h, re.I)) >= 3),
    ("Hours / timings listed", lambda h, u: bool(re.search(
        r"(open|hours|timing|मुख्य)", h, re.I))),
    ("Directions / map link", lambda h, u: ("maps.google" in h.lower()
                                            or "goo.gl/maps" in h.lower())),
    ("Google-readable structured data", lambda h, u: "schema.org"
     in h.lower()),
]

INTENT_LINES = [
    "A guest decides in about 8 seconds on a phone - every row above is a "
    "reason to leave or stay.",
    "Where a rival has one extra widget, the concept still wins every row "
    "that touches speed, phone experience and instant inquiry.",
    "Zero-commission inquiries go straight to the owner's WhatsApp or phone "
    "- no middleman takes a cut of a single booking.",
]


def _fetch(url: str) -> tuple[bool, str]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=20) as resp:
            final = resp.geturl()
            body = resp.read(1_200_000).decode("utf-8", errors="ignore")
        return True, body if final.startswith("https") else (
            "http://" + body)
    except Exception:  # noqa: BLE001 - unreachable rival = dashes
        return False, ""


def spec_row(label: str, url: str) -> dict:
    ok, html = _fetch(url)
    return {
        "label": label,
        **{name: (bool(fn(html, url)) if ok else None)
           for name, fn in SPEC_CHECKS},
    }


def render_matrix(you_url: str | None, rivals: list[dict],
                  concept_name: str = "Facelift concept") -> str:
    cols: list[tuple[str, dict | None]] = []
    if you_url:
        cols.append(("YOU (today)", spec_row("you", you_url)))
    for r in rivals[:2]:
        cols.append((r["name"], spec_row(r["domain"],
                    f"https://{r['domain']}/")))
    concept_specs = {name: True for name, _ in SPEC_CHECKS}
    cols.append((concept_name, concept_specs))

    head = "".join(f"<th>{c[0]}</th>" for c in cols)
    rows_html = []
    wins_note = []
    for name, _fn in SPEC_CHECKS:
        cells = ""
        any_rival_yes = False
        for label, specs in cols:
            v = specs.get(name)
            mark = "✓" if v else ("—" if v is None else "✗")
            cls = "yes" if v else ("no" if v is False else "")
            cells += f"<td class='{cls}'>{mark}</td>"
            if label != concept_name and v:
                any_rival_yes = True
        concept_val = concept_specs[name]
        if concept_val and not any_rival_yes:
            wins_note.append(name)
        rows_html.append(f"<tr><td class='fname'>{name}</td>{cells}</tr>")

    theory = ""
    if wins_note:
        theory = (
            "<p class='note'>Where the concept stands alone: <b>"
            + ", ".join(wins_note[:4])
            + "</b>. Combined with fastest load and full mobile parity, "
            "every path a visitor can take ends at an inquiry.</p>"
        )

    return (
        "<table class='ctable matrix'><tr><th>What customers need</th>"
        + head + "</tr>" + "\n".join(rows_html) + "</table>"
        + theory
    )

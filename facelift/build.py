"""FR-3 rebuild composer v1 (PRD FR-3.1).

Premium one-pager assembled ONLY from extracted facts and the client's own
imagery - hallucination-proof by construction (FR-3.2). v1 adds visual
parity: hero imagery, photo gallery, hover motion, scroll reveals - so the
concept wins the side-by-side on feel AND on speed.
"""

from __future__ import annotations

import base64
import html as _h
import re
import urllib.parse
from pathlib import Path

from . import markets

_DATA_URI_RE = re.compile(
    r"data:image/(png|jpe?g|webp);base64,([A-Za-z0-9+/=\s]+)"
)


def extract_data_uris(page_html: str, out_dir: Path, cap: int = 8,
                      min_bytes: int = 15000) -> list[str]:
    """Decode inlined base64 photos from a page snapshot into dist/img/.

    Returns web-relative paths (img/photo-N.ext). Largest-first; skips
    icon-sized payloads. These become hero + gallery - the client's own
    photography, served from our edge instead of their slow origin.
    """
    items: list[tuple[int, bytes, str]] = []
    for m in _DATA_URI_RE.finditer(page_html):
        ext = m.group(1).lower().replace("jpeg", "jpg")
        try:
            raw = base64.b64decode(re.sub(r"\s", "", m.group(2)))
        except Exception:  # noqa: BLE001 - malformed payloads skipped
            continue
        if len(raw) < min_bytes:
            continue
        items.append((len(raw), raw, ext))
    items.sort(key=lambda t: t[0], reverse=True)
    rels: list[str] = []
    for i, (_sz, raw, ext) in enumerate(items[:cap], 1):
        p = out_dir / f"img" / f"photo-{i}.{ext}"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(raw)
        rels.append(f"img/photo-{i}.{ext}")
    return rels


_IMG_RE = re.compile(
    r"<img[^>]+(?:data-src|src)=[\"']([^\"']+\.(?:jpe?g|png|webp|avif))[\"']",
    re.I,
)
_SKIP_IMG_PARTS = (
    "logo", "icon", "sprite", "avatar", "badge", "banner-ad", "pixel",
    ".svg", "blank.gif", "1x1",
)


def harvest_images(page_html: str, base_url: str, cap: int = 8) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for raw in _IMG_RE.findall(page_html):
        u = urllib.parse.urljoin(base_url, raw.strip())
        if not u.startswith("http") or u in seen:
            continue
        low = u.lower()
        if any(p in low for p in _SKIP_IMG_PARTS):
            continue
        seen.add(u)
        out.append(u)
        if len(out) >= cap:
            break
    return out


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="{meta_desc}">
<meta property="og:title" content="{name} - official website">
<meta property="og:description" content="{meta_desc}">
<meta property="og:type" content="business.business">
<title>{name} - website concept by Facelift</title>
<script type="application/ld+json">
{{"@context":"https://schema.org","@type":"LocalBusiness","name":"{json_name}","telephone":"{json_phone}","address":{{"@type":"PostalAddress","streetAddress":"{json_addr}"}},"url":"{orig}"}}
</script>
<style>
:root{{--bg:#fafaf8;--card:#ffffff;--ink:#14161a;--muted:#5c6470;--accent:#0e9f6e;--line:#e7e7e2}}
*{{margin:0;box-sizing:border-box}}
html{{scroll-behavior:smooth}}
body{{font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;background:var(--bg);color:var(--ink);line-height:1.55}}
.bar{{position:sticky;top:0;z-index:50;background:rgba(15,17,21,.92);backdrop-filter:blur(8px);color:#dfe4ea;font-size:13px;padding:10px 16px;display:flex;gap:14px;align-items:center;flex-wrap:wrap}}
.bar b{{color:#34d399}}
.bar nav{{display:flex;gap:14px;margin-left:auto;flex-wrap:wrap}}
.bar a{{color:#c7d2de;text-decoration:none}}
.bar a:hover{{color:#34d399}}
.hero{{position:relative;min-height:72vh;display:flex;align-items:center;justify-content:center;text-align:center;color:#fff;overflow:hidden;background:#0f1115 url("{hero_img}") center/cover no-repeat}}
.hero::before{{content:"";position:absolute;inset:0;background:linear-gradient(180deg,rgba(10,12,16,.55),rgba(10,12,16,.78))}}
.hero-in{{position:relative;padding:64px 18px;max-width:820px}}
.eyebrow{{letter-spacing:.16em;text-transform:uppercase;font-size:12px;color:#6ee7b7;font-weight:800}}
h1{{font-size:clamp(34px,7vw,60px);line-height:1.05;margin:12px 0 10px;text-shadow:0 2px 18px rgba(0,0,0,.45)}}
.sub{{font-size:clamp(16px,2.4vw,20px);color:#e2e8f0;max-width:56ch;margin:0 auto}}
.cta{{display:flex;gap:12px;margin-top:26px;justify-content:center;flex-wrap:wrap}}
.btn{{padding:13px 24px;border-radius:11px;font-weight:800;text-decoration:none;transition:transform .18s ease,box-shadow .18s ease}}
.btn:hover{{transform:translateY(-2px);box-shadow:0 10px 24px rgba(14,159,110,.35)}}
.btn.primary{{background:var(--accent);color:#fff}}
.btn.ghost{{border:1px solid rgba(255,255,255,.5);color:#fff}}
main{{max-width:1020px;margin:0 auto;padding:26px 18px 70px}}
.stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin:-30px 0 10px;position:relative;z-index:2}}
.stat{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px 18px;box-shadow:0 8px 22px rgba(20,22,26,.06);transition:transform .18s ease}}
.stat:hover{{transform:translateY(-3px)}}
.stat .k{{font-size:25px;font-weight:800}}
.stat .l{{color:var(--muted);font-size:12.5px;margin-top:2px}}
h2{{font-size:clamp(21px,3vw,27px);margin:46px 0 16px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:12px}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px 18px;font-weight:600;transition:transform .18s ease,box-shadow .18s ease}}
.card:hover{{transform:translateY(-4px);box-shadow:0 14px 30px rgba(20,22,26,.10)}}
.card span{{display:block;color:var(--accent);font-size:11px;font-weight:800;letter-spacing:.09em;margin-bottom:6px}}
.gallery{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:10px}}
.gallery figure{{margin:0;overflow:hidden;border-radius:14px;border:1px solid var(--line);background:#ddd}}
.gallery img{{width:100%;height:210px;object-fit:cover;display:block;transition:transform .35s ease}}
.gallery figure:hover img{{transform:scale(1.06)}}
.contact{{background:#0f1115;color:#e6e9ef;border-radius:16px;padding:26px;margin-top:48px}}
.contact h2{{color:#fff;margin-top:0}}
.contact p{{margin:6px 0;color:#b9c2cc}}
.rv{{opacity:0;transform:translateY(16px);transition:opacity .6s ease,transform .6s ease}}
.rv.in{{opacity:1;transform:none}}
footer{{text-align:center;color:var(--muted);font-size:12px;padding:28px 16px}}
@media(max-width:520px){{main{{padding:20px 14px 52px}}.gallery img{{height:160px}}}}
</style>
</head>
<body>
<div class="bar"><span><b>Facelift</b> concept &middot; {name}</span>
<nav><a href="#services">Services</a><a href="#gallery">Gallery</a><a href="#contact">Contact</a><a href="before-after.html">Impact report</a></nav></div>

<header class="hero">
<div class="hero-in">
<div class="eyebrow">Website concept &middot; not live yet</div>
<h1>{name}</h1>
<p class="sub">{sub}</p>
<div class="cta">
<a class="btn primary" href="#contact">Get this site</a>
<a class="btn ghost" href="{orig}" target="_blank" rel="noopener">Compare with old site</a>
</div>
</div>
</header>

<main>
<section class="stats rv">
<div class="stat"><div class="k">{old_perf}/100 &rarr; 95+</div><div class="l">mobile speed, current vs concept target</div></div>
<div class="stat"><div class="k">{old_lcp}s &rarr; &lt;2s</div><div class="l">time until main content shows on a phone</div></div>
<div class="stat"><div class="k">100%</div><div class="l">mobile-responsive &middot; HTTPS &middot; SEO structured</div></div>
</section>

{services_block}

{gallery_block}

<section class="contact rv" id="contact">
<h2>Want this as your real website?</h2>
<p>This is a working concept built from your current site's photos and content.</p>
<p>Reply to our email or call <b>{contact_line}</b> and it can be yours in days, fully managed.</p>
<p style="margin-top:10px;font-size:13px">Packages from {price}. Hosting + care available.</p>
</section>
</main>
<footer>Concept by Facelift &middot; built {date} &middot; content &amp; images sourced from {orig} &middot; takedown on request</footer>
<script>
const io=new IntersectionObserver(function(es){{es.forEach(function(e){{if(e.isIntersecting){{e.target.classList.add("in");io.unobserve(e.target)}}}})}},{{threshold:.12}});
document.querySelectorAll(".rv").forEach(function(el){{io.observe(el)}});
</script>
</body>
</html>
"""


def compose(
    name: str,
    extraction: dict,
    stats: dict,
    original_url: str,
    market: str = "in",
    images: list[str] | None = None,
) -> str:
    services = [str(s)[:60] for s in (extraction.get("services") or [])][:9]
    svc_html = ""
    if services:
        cards = "".join(
            f'<div class="card"><span>SERVICE</span>{_h.escape(s)}</div>'
            for s in services
        )
        svc_html = (
            f'<h2 id="services" class="rv">What {name} offers</h2>\n'
            f'<div class="grid rv">{cards}</div>'
        )

    images = images or []
    hero_img = images[0] if images else ""
    gallery_html = ""
    if len(images) >= 2:
        figures = "".join(
            f'<figure><img src="{_h.escape(u, quote=True)}" loading="lazy" '
            f'alt="{_h.escape(name)} photo"></figure>'
            for u in images[1:7]
        )
        gallery_html = (
            '<h2 id="gallery" class="rv">Gallery</h2>\n'
            f'<div class="gallery rv">{figures}</div>'
        )

    sub = _h.escape((extraction.get("tagline") or "").strip())
    address = _h.escape(extraction.get("address") or "")
    phone = _h.escape(extraction.get("phone") or "")
    contact_bits = [b for b in (phone, address) if b]
    contact_line = " &middot; ".join(contact_bits) if contact_bits else "the owner"

    profile = markets.MARKETS.get(market) or markets.MARKETS["in"]
    price = profile["packages"]["starter"]
    price_s = f"{profile['currency']} {price:,}"

    meta_desc = (
        extraction.get("tagline")
        or f"{name} - official website, contact and services."
    ).strip()

    return PAGE.format(
        name=_h.escape(name),
        sub=sub or "A faster, modern home for this business online.",
        orig=_h.escape(original_url, quote=True),
        old_perf=stats.get("perf", "?"),
        old_lcp=stats.get("lcp", "?"),
        services_block=svc_html,
        gallery_block=gallery_html,
        contact_line=contact_line,
        price=price_s,
        date=stats.get("date", ""),
        hero_img=_h.escape(hero_img, quote=True),
        meta_desc=_h.escape(meta_desc[:150]),
        json_name=_h.escape(name.replace('"', "")),
        json_phone=_h.escape((extraction.get("phone") or "").replace('"', "")),
        json_addr=_h.escape(address.replace('"', "")[:120]),
    )

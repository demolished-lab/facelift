"""Component warehouse indexer — catalogs every block/section/template
from all vendored sources into a searchable manifest the build agent
reads to SELECT (not generate) page components.

Categories detected from HTML structure: hero, menu, gallery, contact,
faq, pricing, testimonials, features, footer, nav, cta, about, team.
Trade affinity tagged from content keywords.
"""

from __future__ import annotations

import json
from pathlib import Path

WAREHOUSE = Path(__file__).resolve().parents[1] / "warehouse"

CATEGORY_SIGNALS = {
    "hero": ["hero", "banner", "masthead", "jumbotron", "cover"],
    "menu": ["menu", "dish", "cuisine", "food", "price", "order"],
    "gallery": ["gallery", "photo", "image", "portfolio", "lightbox"],
    "contact": ["contact", "form", "inquiry", "reach", "message"],
    "faq": ["faq", "question", "accordion", "answer"],
    "pricing": ["pricing", "plan", "tier", "cost", "package"],
    "testimonials": ["testimonial", "review", "quote", "rating", "customer"],
    "features": ["feature", "service", "benefit", "offering", "amenity"],
    "footer": ["footer", "bottom", "copyright", "social"],
    "nav": ["nav", "header", "menu-bar", "hamburger", "navigation"],
    "cta": ["cta", "call-to-action", "get-started", "sign-up", "book"],
    "about": ["about", "story", "mission", "team", "who-we-are"],
    "stats": ["stat", "metric", "number", "counter", "achievement"],
}

TRADE_KEYWORDS = {
    "restaurant": ["restaurant", "cafe", "food", "menu", "dish", "chef",
                    "dining", "cuisine", "kitchen", "bar", "coffee"],
    "hostel": ["hostel", "hotel", "room", "bed", "stay", "booking",
               "guest", "suite", "accommodat"],
    "clinic": ["clinic", "doctor", "health", "medical", "patient",
               "appointment", "treatment", "dental"],
    "fitness": ["gym", "fitness", "training", "workout", "class",
                "trainer", "muscle"],
    "salon": ["salon", "beauty", "hair", "spa", "style", "treatment"],
    "retail": ["shop", "store", "product", "brand", "collection"],
}


def _detect_categories(html: str) -> list[str]:
    low = html.lower()
    cats = []
    for cat, signals in CATEGORY_SIGNALS.items():
        if any(s in low for s in signals):
            cats.append(cat)
    return cats or ["generic"]


def _detect_trades(html: str) -> list[str]:
    low = html.lower()
    return [t for t, kws in TRADE_KEYWORDS.items()
            if any(k in low for k in kws)]


def _title(html: str) -> str:
    import re
    m = re.search(r"<title>(.*?)</title>", html, re.I)
    if m:
        return m.group(1).strip()[:60]
    m = re.search(r"<h[12][^>]*>(.*?)</h[12]>", html, re.I | re.S)
    if m:
        t = re.sub(r"<[^>]+>", "", m.group(1)).strip()[:60]
        return t
    return ""


def index_warehouse() -> list[dict]:
    """Scans all warehouse sources, returns catalog entries."""
    catalog = []
    for source_dir in sorted(WAREHOUSE.iterdir()):
        if not source_dir.is_dir():
            continue
        source = source_dir.name
        for f in sorted(source_dir.rglob("*.html")):
            try:
                html = f.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            if len(html) < 200:
                continue
            rel = str(f.relative_to(source_dir))
            cats = _detect_categories(html)
            trades = _detect_trades(html)
            catalog.append({
                "source": source,
                "file": str(f.relative_to(WAREHOUSE)),
                "path": str(f),
                "size_kb": round(len(html) / 1024, 1),
                "title": _title(html),
                "categories": cats,
                "trades": trades,
            })
    return catalog


def search(catalog: list[dict], categories: list[str],
           trade: str = "", limit: int = 5) -> list[dict]:
    """Find blocks matching categories + trade affinity."""
    scored = []
    for e in catalog:
        score = 0
        for c in categories:
            if c in e["categories"]:
                score += 10
        if trade and trade in e["trades"]:
            score += 5
        if score > 0:
            scored.append((score, e))
    scored.sort(key=lambda x: (-x[0], x[1]["size_kb"]))
    return [e for _, e in scored[:limit]]


if __name__ == "__main__":
    import sys

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    cat = index_warehouse()
    out = WAREHOUSE / "catalog.json"
    out.write_text(json.dumps(cat, indent=2), encoding="utf-8")
    print(f"indexed {len(cat)} blocks from "
          f"{len(set(e['source'] for e in cat))} sources")
    cats = {}
    for e in cat:
        for c in e["categories"]:
            cats[c] = cats.get(c, 0) + 1
    for c, n in sorted(cats.items(), key=lambda x: -x[1])[:10]:
        print(f"  {c:<15} {n}")

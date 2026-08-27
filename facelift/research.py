"""Field Research Agent (PRD FR-2.5 - designer-style pre-build research).

Like a human designer starting a real project: scan current design trends
for the trade, hunt references, and trace the lead's own public footprint
(socials, reviews, mentions). Keyless DuckDuckGo HTML lane today;
agent-reach channels plug in when configured. Everything found is PUBLIC
and flows into the build brief as designer's field notes.
"""

from __future__ import annotations

import html as _html
import re
import urllib.parse
import urllib.request

from .measure import USER_AGENT

DDG = "https://html.duckduckgo.com/html/"
BING = "https://www.bing.com/search"

RESULT_RE = re.compile(
    r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>.*?'
    r'class="result__snippet"[^>]*>(.*?)</a>',
    re.S | re.I,
)
BING_BLOCK_RE = re.compile(r'<li class="b_algo".*?</li>', re.S | re.I)
BING_URL_RE = re.compile(r'<h2[^>]*><a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.S)
BING_SNIP_RE = re.compile(r"<p[^>]*>(.*?)</p>", re.S)
TAG_RE = re.compile(r"<[^>]+>")


def _clean(s: str) -> str:
    return _html.unescape(TAG_RE.sub("", s)).strip()


def _decode_ddg_url(u: str) -> str:
    u = _html.unescape(u)
    if u.startswith("//"):
        u = "https:" + u
    if "uddg=" in u:
        import urllib.parse as up

        m = re.search(r"uddg=([^&]+)", u)
        if m:
            u = up.unquote(m.group(1))
    return u


def _unwrap_bing(u: str) -> str:
    u = _html.unescape(u)
    if "/ck/a" not in u:
        return u
    m = re.search(r"[?&]u=a1([^&]+)", u)
    if not m:
        return u
    import base64

    s = m.group(1).replace("-", "+").replace("_", "/")
    s += "=" * (-len(s) % 4)
    try:
        return base64.b64decode(s).decode("utf-8", errors="ignore")
    except Exception:  # noqa: BLE001
        return u


def _bing_search(query: str, max_results: int, timeout: int) -> list[dict]:
    body = urllib.parse.urlencode({"q": query}).encode()
    req = urllib.request.Request(
        BING + "?" + body.decode(), headers={"User-Agent": USER_AGENT}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        html = resp.read(900_000).decode("utf-8", errors="ignore")
    out: list[dict] = []
    seen: set[str] = set()
    for block in BING_BLOCK_RE.findall(html):
        um = BING_URL_RE.search(block)
        if not um:
            continue
        url = _unwrap_bing(um.group(1))
        title = _clean(um.group(2))
        sm = BING_SNIP_RE.search(block)
        snippet = _clean(sm.group(1))[:220] if sm else ""
        if not title or url in seen or "//www.bing.com" in url:
            continue
        seen.add(url)
        out.append({"title": title, "url": url, "snippet": snippet})
        if len(out) >= max_results:
            break
    return out


def web_search(query: str, max_results: int = 4,
               timeout: int = 25) -> list[dict]:
    """Bing primary (tolerant parser), DuckDuckGo HTML fallback."""
    try:
        r = _bing_search(query, max_results, timeout)
        if r:
            return r
    except Exception:  # noqa: BLE001 - fall through to DDG
        pass
    body = urllib.parse.urlencode({"q": query}).encode()
    req = urllib.request.Request(
        DDG + "?" + body.decode(), headers={"User-Agent": USER_AGENT}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            html = resp.read(800_000).decode("utf-8", errors="ignore")
    except Exception:  # noqa: BLE001 - search flakiness expected
        return []
    out: list[dict] = []
    seen: set[str] = set()
    for m in RESULT_RE.finditer(html):
        url = _decode_ddg_url(m.group(1))
        title = _clean(m.group(2))
        snippet = _clean(m.group(3))[:220]
        if not title or url in seen or "duckduckgo.com" in url:
            continue
        seen.add(url)
        out.append({"title": title, "url": url, "snippet": snippet})
        if len(out) >= max_results:
            break
    return out


def reddit_search(query: str, max_results: int = 4,
                  timeout: int = 25) -> list[dict]:
    """Keyless public Reddit JSON search - real owner/customer voices."""
    url = (
        "https://www.reddit.com/search.json?"
        + urllib.parse.urlencode(
            {"q": query, "sort": "relevance", "limit": max_results})
    )
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.load(resp)
    except Exception:  # noqa: BLE001 - reddit rate-limits aggressively
        return []
    out: list[dict] = []
    for child in data.get("data", {}).get("children", []):
        d = child.get("data", {})
        title = _clean(d.get("title", ""))
        if not title:
            continue
        body = _html.unescape(str(d.get("selftext", "")))[:200]
        out.append({
            "title": title,
            "sub": d.get("subreddit", ""),
            "score": d.get("score", 0),
            "url": "https://reddit.com" + str(d.get("permalink", "")),
            "body": body,
        })
        if len(out) >= max_results:
            break
    return out




def mine_reviews(lead_name: str, city: str = "") -> list[str]:
    """Extract review quotes from search results — real customer voice."""
    queries = [
        f'"{lead_name}" reviews "great" OR "amazing" OR "best"',
        f'"{lead_name}" {city} customer experience',
    ]
    quotes = []
    for q in queries:
        for r in web_search(q, max_results=4):
            snip = r.get("snippet", "")
            if any(w in snip.lower() for w in
                   ("great", "amazing", "best", "love", "excellent",
                    "delicious", "comfortable", "friendly", "amazing")):
                quotes.append(f'"{snip[:150]}" — {r["title"][:40]}')
    return quotes[:4]


def research_lead(lead_name: str, vertical_key: str,
                  market_label: str, city_hint: str = "") -> str:
    """Returns markdown field-notes block for the brief."""
    from .markets import VERTICAL_PROFILES, DEFAULT_PROFILE
    from .speculative import speculative_research

    prof = VERTICAL_PROFILES.get(vertical_key, DEFAULT_PROFILE)
    trade = vertical_key.replace("_", " ") if vertical_key else "local business"

    sections: list[str] = []

    # ── speculative parallel prefetch ───────────────────────────────
    prefetch: dict[str, list[dict]] = {}
    try:
        prefetch = speculative_research(lead_name, vertical_key or "local", city_hint)
    except Exception:
        pass  # non-fatal if parallel fetch fails

    # 1. Design trends — use prefetch if available, else normal search
    if "trends" in prefetch and prefetch["trends"]:
        lines = [f"- **{x['title']}** — {x['snippet']}" for x in prefetch["trends"][:4]]
        sections.append(
            "### Design trends & references for this trade\n"
            + "\n".join(lines)
        )
    else:
        q1 = f"best {trade} website design inspiration {market_label}"
        r1 = web_search(q1)
        if r1:
            lines = [f"- **{x['title']}** — {x['snippet']}" for x in r1]
            sections.append(
                "### Design trends & references for this trade\n"
                + "\n".join(lines)
            )

    # 2. Technical features — use prefetch if available, else normal search
    if "tech" in prefetch and prefetch["tech"]:
        lines = [f"- **{x['title']}** — {x['snippet']}" for x in prefetch["tech"][:4]]
        sections.append(
            "### Technical features top sites in this trade ship\n"
            "(booking flows, ordering, calculators, chat, PWA, structured "
            "data — mine these for the MUST/SCALING feature plan)\n"
            + "\n".join(lines)
        )
    else:
        q_tech = (f"{trade} website essential features online booking "
                  f"ordering live chat schema speed")
        r_tech = web_search(q_tech, max_results=4)
        if r_tech:
            lines = [f"- **{x['title']}** — {x['snippet']}" for x in r_tech]
            sections.append(
                "### Technical features top sites in this trade ship\n"
                "(booking flows, ordering, calculators, chat, PWA, structured "
                "data — mine these for the MUST/SCALING feature plan)\n"
                + "\n".join(lines)
            )

    # 3. Discovery & trust — use prefetch traces if available, else normal search
    if "traces" in prefetch and prefetch["traces"]:
        seen_u = set()
        traces = []
        for x in prefetch["traces"][:6]:
            if x["url"] in seen_u:
                continue
            seen_u.add(x["url"])
            traces.append(
                f"- **{x['title']}** — {x['url']} — {x['snippet']}"
            )
        if traces:
            sections.append(
                "### This business's multi-platform presence & intent "
                "signals (socials, reviews, announcements — trust/social-"
                "proof framing and feature ideas only; never invent from "
                "these)\n" + "\n".join(traces)
            )
    else:
        q_disc = (f"how customers find local {trade} near me "
                  f"google business profile reviews")
        r_disc = web_search(q_disc, max_results=3)
        if r_disc:
            lines = [f"- **{x['title']}** — {x['snippet']}" for x in r_disc]
            sections.append(
                "### Discovery & trust: how this trade's customers actually "
                "find and judge businesses\n"
                + "\n".join(lines)
            )

    if lead_name:
        q2 = f'"{lead_name}" {city_hint}'.strip() \
            + " reviews OR instagram OR facebook"
        r2 = web_search(q2, max_results=4)
        q2b = (f'site:instagram.com OR site:facebook.com OR '
               f'site:youtube.com "{lead_name}"')
        r2b = web_search(q2b, max_results=3)
        q2c = f'"{lead_name}" news OR announcement OR opening'
        r2c = web_search(q2c, max_results=3)
        traces = []
        seen_u = set()
        for x in (r2 + r2b + r2c):
            if x["url"] in seen_u:
                continue
            seen_u.add(x["url"])
            traces.append(
                f"- **{x['title']}** — {x['url']} — {x['snippet']}")
        if traces:
            sections.append(
                "### This business's multi-platform presence & intent "
                "signals (socials, reviews, announcements — trust/social-"
                "proof framing and feature ideas only; never invent from "
                "these)\n" + "\n".join(traces)
            )

    rr = reddit_search(
        f"{trade} website booking OR inquiries OR \"no website\"")
    rr2 = reddit_search(f"small business {trade} site redesign worth it")
    reddit_rows = [
        f"- **{x['title']}** (r/{x['sub']}, ↑{x['score']}) — "
        f"{x['body'] or '—'}"
        for x in (rr + rr2)[:5]
    ]
    if reddit_rows:
        sections.append(
            "### Real voices: owners & customers discussing this exact "
            "problem on Reddit\n(use for empathy and feature ideas; quote "
            "only with attribution as community sentiment)\n"
            + "\n".join(reddit_rows)
        )

    quotes = mine_reviews(lead_name, city_hint)
    if quotes:
        sections.append(
            "### Real customer voice (from public reviews)\n"
            "Use these as tone/quality signals. Do NOT fabricate "
            "testimonials from these — they inform copy direction only.\n"
            + "\n".join(f"- {q}" for q in quotes)
        )

    # 4. What customers expect — use prefetch "expect" if available, else normal search
    if "expect" in prefetch and prefetch["expect"]:
        lines = [f"- **{x['title']}** — {x['snippet']}" for x in prefetch["expect"][:3]]
        sections.append(
            "### What customers expect from this trade's sites\n"
            + "\n".join(lines)
        )
    else:
        q3 = f"{trade} website must have features customers expect"
        r3 = web_search(q3, max_results=3)
        if r3:
            lines = [f"- **{x['title']}** — {x['snippet']}" for x in r3]
            sections.append(
                "### What customers expect from this trade's sites\n"
                + "\n".join(lines)
            )

    if not sections:
        return ""
    header = (
        "## FIELD RESEARCH (live web, gathered just now)\n\n"
        "Use these as design-direction, feature-planning and honest "
        "context signals. Do NOT copy content from these sources and do "
        "NOT treat them as facts about the business unless they match "
        "Facts JSON. Where a researched feature clearly fits this trade, "
        "add it under a `TODO-OWNER:` note rather than silently shipping "
        "a fake version.\n"
    )
    return header + "\n\n".join(sections) + "\n"


def detect_vertical_key(facts: dict) -> str:
    """Best-effort vertical key from facts for research queries."""
    from .markets import VERTICAL_PROFILES

    hay = (
        str(facts.get("tagline", "")) + " "
        + " ".join(str(s) for s in (facts.get("services") or [])) + " "
        + str(facts.get("_vertical_tags", ""))
    ).lower()
    best, hits = "", 0
    for key, prof in VERTICAL_PROFILES.items():
        n = sum(1 for kw in prof["match"] if kw in hay)
        if n > hits:
            best, hits = key, n
    return best

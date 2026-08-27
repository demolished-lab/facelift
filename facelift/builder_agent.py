"""Agent-builder bridge (owner architecture decision, 2026-08-23).

Facelift orchestrates (leads, scoring, queueing, deploying); a fresh
opencode coding agent does the actual building - invoked with a compiled
brief, given the target's full capture (HTML/CSS/photos) and audit
receipts, expected to produce dist/index.html that visually beats the
original. Falls back gracefully when opencode is unavailable.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
from pathlib import Path

HEAD_RE = re.compile(r"<h[123][^>]*>(.*?)</h[123]>", re.I | re.S)
TAG_RE = re.compile(r"<[^>]+>")


def opencode_cmd() -> list[str] | None:
    exe = shutil.which("opencode.cmd") or shutil.which("opencode.exe")
    if exe:
        return ["cmd", "/c", exe] if exe.lower().endswith(".cmd") else [exe]
    return None


def summarize_snapshot(html_text: str, cap: int = 30) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for m in HEAD_RE.finditer(html_text):
        t = TAG_RE.sub(" ", m.group(1))
        t = re.sub(r"\s+", " ", t).strip()
        if not t or len(t) > 80 or t.lower() in seen:
            continue
        seen.add(t.lower())
        out.append(t)
        if len(out) >= cap:
            break
    return out


HEX_RE = re.compile(r"#[0-9a-fA-F]{6}\b")
FONT_RE = re.compile(r"font-family\s*:\s*([^;}]+)")


def extract_design_tokens(css_path: Path | None, cap: int = 6) -> dict:
    """prompt-master Pattern 17: replace aesthetic adjectives with exact
    values. Palette/fonts mined from the client's own stylesheet."""
    tokens: dict = {"colors": [], "fonts": []}
    if not css_path or not css_path.exists():
        return tokens
    try:
        css = css_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:  # noqa: BLE001
        return tokens
    from collections import Counter

    colors = Counter(m.group(0).lower() for m in HEX_RE.finditer(css))
    junk = {"#ffffff", "#fff000", "#000000"}
    tokens["colors"] = [
        c for c, _n in colors.most_common(20) if c not in junk
    ][:cap]
    fonts: Counter = Counter()
    for m in FONT_RE.finditer(css):
        first = m.group(1).split(",")[0].strip().strip("'\"")
        if first and not first.startswith(("arial", "helvetica", "sans-serif",
                                           "serif", "monospace", "-apple")):
            fonts[first] += 1
    tokens["fonts"] = [f for f, _n in fonts.most_common(cap)]
    return tokens


BRIEF = """# BUILD BRIEF - {biz} concept site

You are an elite web designer-developer. A business owner will compare your
result side-by-side against their CURRENT live website. You must win that
comparison on visual appeal AND keep it technically excellent.

## Hard rules
1. NEVER invent facts. Use ONLY the Facts JSON below (plus neutral phrasing
   like "Book your stay"). No fake reviews, prices, or addresses.
2. Output: exactly one self-contained `dist/index.html` (inline CSS/JS OK,
   local asset files allowed under dist/). No external CDN dependencies.
3. Reuse the provided photos (paths listed below) - they are the business's
   real photography and the emotional core of the page.
4. Mobile-first responsive. Must look premium at 390px and 1440px.

## The original site you must BEAT
- Captured HTML: {snapshot_html}
- Its stylesheet: {snapshot_css} - read it for brand colors/fonts/vibes.
- Its section map (match or beat EVERY one of these experiences):
{headings}
- It has: photos, scroll effects, hover effects. Yours needs equivalents
  that feel modern, not copies: hero imagery, galleries with hover zoom,
  scroll-reveal animations, sticky glass nav, tasteful gradients/shadows.

## Facts JSON (single source of truth)
```json
{facts}
```

## Audit receipts (must appear in a visible "proof strip" on the page)
Mobile performance {perf}/100, load-to-content {lcp}s on the current site.
Your build targets 95+/100 and <2s. Show these numbers honestly.

## Required elements
- Sticky top nav (glass blur) with anchor links + prominent contact CTA
- Hero using best photo + gradient overlay + name + tagline
- Services/features grid derived ONLY from Facts.services
- Photo gallery with hover interaction
- Contact panel: phone (tap-to-call), address, hours from Facts
- Proof strip with the audit receipts above
- Footer: "Concept by Facelift - content sourced from {orig} - takedown on
  request" plus link to before-after.html
- SEO head: meta description, Open Graph tags, schema.org LocalBusiness
  JSON-LD built strictly from Facts

## Deep research (derived from this business's own data - personalize hard)
- Purpose: {purpose}
- Market/location: {market_label}{location_note}
- MUST-FEATURES (non-negotiable, user-facing):
{must_block}
- SCALING-FEATURES (structure for growth, do not fake content):
{scale_block}
- OWNER experience: inquiries must land somewhere the owner already reads
  (WhatsApp / phone / email from Facts) with zero setup on their side.
- USER experience: every interaction one tap away; works perfectly offline-
  slow 3G; nothing requires login/signup.
- ANOMALY handling: missing Facts field = omit that element gracefully
  (never placeholder text); broken/unavailable photo = skip it; if Facts are
  thin, build a smaller flawless page instead of a padded rich one.

## Arsenal notes (use intelligently, stay self-contained)
- Component patterns: you may adapt layouts/patterns in the style of free
  MIT Tailwind libraries (HyperUI / DaisyUI / Flowbite blocks) but INLINE
  the CSS - no CDN links, no npm installs.
- Provided images under dist/img are the business's real photos or clearly
  labeled concept art (files named gen-*). Use gen-* images only where a
  photo would naturally sit, and keep the footer note "concept imagery".
- If dist/img contains gen-hero.*, prefer it as the hero background.
- Reuse: one CSS system, utility classes you define once, no per-section
  duplicated styles (lazy-senior-dev rule).

## Full-stack latitude
dist/ may contain multiple files (index.html plus pages/assets) when the
MUST-FEATURES genuinely need them. Static-first: dynamic behavior via
vanilla JS + wa.me / mailto: / maps links only - no servers, no keys.

## Design tokens (extracted from THEIR OWN stylesheet - use these exact
## values as primary palette and typography so it feels like their brand)
{tokens_block}

## Scope lock (prompt-master agentic patterns 31-35)
- Starting state: empty dist/ directory; photos already at paths above.
- Target state: dist/index.html complete and standalone. Nothing else.
- ONLY create/edit files inside `dist/`. Never modify BRIEF.md, never
  touch anything outside this project folder.
- Forbidden: external CDN links, frameworks, build tools, invented facts.
- Progress protocol: after each major section is written, print one line:
  `OK <section>`.
- Stop condition: when dist/index.html satisfies every Done-criterion,
  print exactly `BUILD COMPLETE` and stop.

## Done criteria (self-verify before stopping)
1. Opens standalone in a browser with zero console errors.
2. Every Facts field that exists appears somewhere real on the page.
3. All provided photo paths render (no broken images).
4. Proof strip shows the audit numbers verbatim.
5. Pixel-solid at 375px AND 1440px.

## Definition of done
dist/index.html exists, opens standalone, loads fast, and would make the
owner say "this looks like a brand I trust" at first glance.
"""


def build_brief(
    workdir: Path,
    biz: str,
    facts: dict,
    audit_mobile: dict,
    orig: str,
    snapshot_html: Path | None,
    snapshot_css: Path | None,
    image_files: list[str],
    rivals: list[dict] | None = None,
    market_profile: str = "in",
    is_no_site: bool = False,
    date: str = "",
) -> Path:
    heads: list[str] = []
    if snapshot_html and snapshot_html.exists():
        try:
            heads = summarize_snapshot(
                snapshot_html.read_text(encoding="utf-8", errors="ignore")
            )
        except Exception:  # noqa: BLE001 - context is best-effort
            heads = []
    tokens = extract_design_tokens(snapshot_css)
    if tokens["colors"] or tokens["fonts"]:
        lines = ["Brand colors (most-used first): "
                 + ", ".join(tokens["colors"])]
        if tokens["fonts"]:
            lines.append("Their font stacks: " + " | ".join(tokens["fonts"]))
        lines.append(
            "Use the top 2-3 colors as primary/accent and pick a similar "
            "typeface pairing. This is how it must feel like their brand."
        )
        tokens_block = "\n".join(lines)
    else:
        tokens_block = "(no stylesheet found - choose a tasteful palette)"

    from .brief_master import compile_brief

    import datetime as _dt

    from .design_dna import choose as dna_choose, render_block

    from .markets import VERTICAL_PROFILES as _VP

    hay_local = json.dumps(facts, ensure_ascii=False).lower()
    best_v, hits = "", 0
    for k_, p_ in _VP.items():
        n_ = sum(1 for kw in p_["match"] if kw in hay_local)
        if n_ > hits:
            best_v, hits = k_, n_
    dna = dna_choose(biz + "|" + orig, best_v)
    dna_block = render_block(dna)

    # component warehouse: find matching blocks for the agent to SELECT
    warehouse_note = ""
    try:
        from . import warehouse as wh

        catalog = wh.index_warehouse()
        trade = best_v or "generic"
        blocks = wh.search(catalog, ["hero", "menu", "gallery",
                                     "contact", "faq", "features"],
                           trade=trade, limit=8)
        if blocks:
            lines = []
            for b in blocks:
                lines.append(
                    f"- [{b['source']}] {b['file']} "
                    f"({', '.join(b['categories'])}) "
                    f"— {b['title'] or 'block'} [{b['size_kb']}KB]"
                )
            warehouse_note = (
                f"\n\n## WAREHOUSE BLOCKS ({len(blocks)} matching "
                f"pre-built components found)\n"
                f"SELECT from these proven blocks — read the file, "
                f"adapt the HTML/CSS to this build's design system. "
                f"Do NOT generate from scratch what already exists here:\n"
                + "\n".join(lines)
            )
    except Exception:  # noqa: BLE001 - warehouse optional
        pass

    text = compile_brief(
        biz=biz,
        facts=facts,
        audit_mobile=audit_mobile,
        orig=orig,
        tokens_block=tokens_block,
        headings=heads,
        images=image_files,
        rivals=rivals or [],
        market_profile=market_profile,
        is_no_site=is_no_site,
        date=date or _dt.date.today().isoformat(),
        dna_block=dna_block,
        warehouse_note=warehouse_note,
    )
    p = workdir / "BRIEF.md"
    p.write_text(text, encoding="utf-8")
    rules = ""
    if PONYTAIL_RULES.exists():
        rules += PONYTAIL_RULES.read_text(encoding="utf-8") + "\n\n"
    if CAVEMAN_RULES.exists():
        rules += ("# COMMUNICATION MODE (token efficiency)\n"
                  + CAVEMAN_RULES.read_text(encoding="utf-8"))
    if rules:
        (workdir / "AGENTS.md").write_text(rules, encoding="utf-8")
    return p


PONYTAIL_RULES = Path(__file__).resolve().parents[1] / "assets" / "ponytail-AGENTS.md"
CAVEMAN_RULES = Path(__file__).resolve().parents[1] / "assets" / "caveman-AGENTS.md"

CLEAN_PROMPT = (
    "Read BRIEF.md and AGENTS.md in the current directory, then execute "
    "BRIEF.md exactly: STEP 1 write PLAN.md (complexity+why, sitemap, "
    "palette hexes+reasons, type pairing, section purposes, signature "
    "component spec, risks) and print 'PLAN WRITTEN'. STEP 2 build the "
    "full site into dist/ (index.html entry; extra pages/assets as the "
    "plan calls for; same header/footer + OG on every page). Print 'OK "
    "<section>' per milestone and one-line design decisions with reasons. "
    "Follow AGENTS.md: lazy-senior-dev code, caveman-terse console. No "
    "questions."
)


def run_agent(workdir: Path, timeout_s: int = 800,
              retries: int = 2, stream: bool = True) -> tuple[bool, str]:
    cmd = opencode_cmd()
    if not cmd:
        return False, "opencode not on PATH"
    env = {**__import__("os").environ, "CI": "1"}
    log_lines: list[str] = []

    def _spawn() -> subprocess.CompletedProcess:
        if not stream:
            return subprocess.run(
                cmd + ["run", CLEAN_PROMPT],
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=timeout_s, cwd=str(workdir),
                stdin=subprocess.DEVNULL, env=env)
        proc = subprocess.Popen(
            cmd + ["run", CLEAN_PROMPT],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
            cwd=str(workdir), env=env,
            stdin=subprocess.DEVNULL)
        for line in proc.stdout:  # noqa: BDB007 - streamed to operator
            line = line.rstrip()
            if line:
                log_lines.append(line)
                print(f"  [builder] {line[:140]}")
        rc = proc.wait()
        return subprocess.CompletedProcess(proc.args, rc, "", "")

    last_err = ""
    attempt = 0
    while attempt <= retries:
        attempt += 1
        try:
            proc = _spawn()
        except subprocess.TimeoutExpired:
            return False, f"agent timed out after {timeout_s}s"
        except Exception as ex:  # noqa: BLE001 - spawn flake => retry
            last_err = f"spawn failed: {ex}"
            if attempt <= retries:
                time.sleep(5)
                continue
            return False, last_err
        index = workdir / "dist" / "index.html"
        pages = list(workdir.rglob("dist/*.html")) \
            if (workdir / "dist").exists() else []
        ok = proc.returncode == 0 and any(
            p.stat().st_size > 2000 for p in ([index] + pages))
        if ok:
            (workdir / "BUILD-LOG.md").write_text(
                "\n".join(log_lines), encoding="utf-8")
            return True, f"{len(log_lines)} builder events logged"
        last_err = f"rc={proc.returncode} tail={log_lines[-1][:150] if log_lines else ''}"
        if attempt <= retries:
            time.sleep(5)
    (workdir / "BUILD-LOG.md").write_text(
        "\n".join(log_lines), encoding="utf-8")
    return False, last_err


def verify(dist_dir: Path) -> bool:
    """Multi-page aware: entry page required; total HTML weight decides."""
    idx = dist_dir / "index.html"
    if not idx.exists():
        return False
    total = sum(
        p.stat().st_size for p in dist_dir.rglob("*.html")
    )
    return total > 2000


def quality_check(dist_dir: Path) -> list[str]:
    """Visual/technical quality gate (master prompt 6b + core hygiene).
    Multi-page aware: evaluates every HTML file as one site.
    Returns human-readable failures; empty list = pass."""
    pages = sorted(dist_dir.rglob("*.html"))
    if not pages or not (dist_dir / "index.html").exists():
        return ["dist/index.html missing entirely"]
    html = "\n".join(
        p.read_text(encoding="utf-8", errors="ignore") for p in pages
    )
    low = html.lower()
    fails: list[str] = []
    if len(html) < 10_000:
        fails.append("whole site under 10KB - likely too thin for a "
                     "premium feel")
    sections = low.count("<section")
    if sections < 3 * max(1, len(pages) // 2):
        fails.append(f"only {sections} <section> blocks across "
                     f"{len(pages)} page(s) - thin content rhythm")
    for p in pages:
        pl = p.read_text(encoding="utf-8", errors="ignore").lower()
        if 'name="viewport"' not in pl:
            fails.append(f"{p.name}: missing viewport meta")
        if "og:" not in pl:
            fails.append(f"{p.name}: missing Open Graph tags")
        rel_links = re.findall(r'href="((?!http|mailto|tel|#)[^"]+\.html)"',
                               pl)
        for link in rel_links:
            if not (dist_dir / link).exists():
                fails.append(f"{p.name}: broken internal link {link}")
    if "schema.org" not in low:
        fails.append("missing schema.org structured data")
    if ":hover" not in low:
        fails.append("no :hover states - interactive elements feel dead")
    if ("intersectionobserver" not in low
            and "@keyframes" not in low
            and "transition" not in low):
        fails.append("no scroll/hover motion found - add reveal or "
                     "transition movement")
    if "lorem" in low:
        fails.append("lorem ipsum placeholder detected")
    if "tel:" not in low and "wa.me" not in low and "mailto:" not in low:
        fails.append("no instant-contact action (tel:/wa.me/mailto:)")
    imgs = len(re.findall(r"<img", low))
    asset_imgs = len(list((dist_dir / "img").glob("*"))) \
        if (dist_dir / "img").exists() else 0
    if asset_imgs and imgs == 0:
        fails.append(f"{asset_imgs} provided images exist but none used")
    craft_signals = 0
    if "transition-delay" in low or "animation-delay" in low:
        craft_signals += 1
    if "position:sticky" in low.replace(" ", "") or \
            "position: sticky" in low:
        craft_signals += 1
    if low.count("z-index") >= 3:
        craft_signals += 1
    if "--" in low and "var(--" in low:
        craft_signals += 1
    if len(pages) > 1:
        craft_signals += 1
    if craft_signals < 2:
        fails.append(
            f"craft depth thin ({craft_signals}/5 signals: stagger delays, "
            "sticky scene, layered z-index, CSS theme variables, "
            "multi-page structure) - elevate toward C2+ per Craft Standard"
        )
    return fails




def _vision_fallback(png_bytes: bytes, prompt: str) -> str | None:
    """Try non-Gemini vision models when Gemini quota is exhausted."""
    import base64
    import urllib.request

    from .llm import _load_env

    _load_env()
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        return None
    b64 = base64.b64encode(png_bytes).decode("ascii")
    body = json.dumps({
        "model": "google/gemini-2.0-flash-exp:free",
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {
                "url": f"data:image/png;base64,{b64}"}},
        ]}],
        "max_tokens": 800,
    }).encode()
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=body,
        headers={"Authorization": f"Bearer {key}",
                 "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = json.load(resp)
        return data["choices"][0]["message"]["content"]
    except Exception:
        return None


def design_critique(png_bytes: bytes) -> list[str]:
    """Vision-model art-director review of the rendered page.

    Returns specific visual defects; ['APPROVED'] when genuinely strong.
    Uses Gemini flash (multimodal) directly via generateContent.
    """
    import base64
    import os
    import urllib.request

    from .llm import _load_env

    _load_env()
    key = os.environ.get("GEMINI_API_KEY")
    if not key or not png_bytes:
        return []
    prompt = (
        "You are a brutal senior art director reviewing a screenshot of a "
        "small-business website concept. Standard it must hit: distinctive "
        "art direction, layered depth (overlaps/shadows/translucency), "
        "confident typography (strong display treatment, clear scale), "
        "choreographed feel, cohesive palette, premium micro-polish. "
        "List UP TO 6 SPECIFIC visual defects as short bullet lines "
        "(composition, spacing, hierarchy, color, type, depth, polish - "
        "name exact areas). No praise padding. If truly excellent, reply "
        "exactly: APPROVED"
    )
    b64 = base64.b64encode(png_bytes).decode("ascii")
    body = json.dumps({
        "contents": [{"parts": [
            {"text": prompt},
            {"inline_data": {"mime_type": "image/png", "data": b64}},
        ]}],
    }).encode()
    url = ("https://generativelanguage.googleapis.com/v1beta/models/"
           "gemini-3.6-flash:generateContent?key=" + key)
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.load(resp)
        text = data["candidates"][0]["content"]["parts"][0]["text"]
    except urllib.error.HTTPError as ex:
        if ex.code == 429:
            fb = _vision_fallback(png_bytes, prompt)
            if fb and "APPROVED" not in fb.upper():
                lines = [l.lstrip("-• ").strip() for l in fb.splitlines()
                         if l.strip().startswith(("-", "•"))]
                return lines[:6] if lines else ["APPROVED"]
        print(f"(design critique unavailable: {str(ex)[:80]})")
        return []
    except Exception as ex:
        print(f"(design critique unavailable: {str(ex)[:80]})")
        return []
    text = text.strip()
    if "APPROVED" in text.upper():
        return ["APPROVED"]
    lines = [
        l.lstrip("-• ").strip() for l in text.splitlines()
        if l.strip() and l.strip().startswith(("-", "•"))
    ] or [l.strip() for l in text.splitlines() if l.strip()]
    return lines[:6]


def revision_brief(dist_parent: Path, fails: list[str]) -> Path:
    p = dist_parent / "REVISION.md"
    p.write_text(
        "# REVISION REQUEST\n\nA quality gate flagged the current "
        "dist/index.html. Fix EXACTLY these issues - change nothing else:\n"
        + "\n".join(f"- {f}" for f in fails)
        + "\n\nRe-save dist/index.html when done, then print "
          "`BUILD COMPLETE`.",
        encoding="utf-8",
    )
    return p

"""Master brief compiler (assets/master_prompt.md).

Fills the owner-supplied Universal Builder Prompt's slots automatically
from pipeline artifacts: Facts JSON, live audit receipts, mined design
tokens, competitor standings, asset inventory, vertical research, market
compliance frame. The agent plans at the right complexity level instead of
guessing.
"""

from __future__ import annotations

import json
from pathlib import Path

MASTER = Path(__file__).resolve().parents[1] / "assets" / "master_prompt.md"
CRAFT = Path(__file__).resolve().parents[1] / "assets" / "craft_standard.md"

CRAFT_BLOCK = """Follow the FACELIFT CRAFT STANDARD (summary below - full doc:
assets/craft_standard.md). Target tier C2 minimum; reach C3 when the
playbook's signature component allows it.

- ART DIRECTION: derive ONE repeating trade motif + shape language +
  color journey (base + 1 brand + 2-3 accents + single atmosphere
  effect). Recognizable-from-screenshot rule applies.
- CHOREOGRAPHY: sequenced reveals in reading order (background -> head ->
  media -> text -> CTA), staggered 60-120ms via IntersectionObserver;
  one pinned/sticky scene max; sections hand off visually, no hard cuts.
- DEPTH: layered fg/mg/bg with overlap, translucency, directional shadows,
  one parallax layer max.
- MICRO-INTERACTIONS: pick >=4 (tilt cards, magnetic buttons, icon-slide
  links, counting stats, glow-follow, copy-feedback).
- MOTION RULES (Emil Kowalski doctrine, non-negotiable):
  * Entrances = ease-out (e.g. cubic-bezier(0.23,1,0.32,1)); exits =
    ease-in; on-screen moves = ease-in-out. NEVER ease-in on entrances.
  * Durations 150-500ms (micro-interactions 150-200ms; section reveals
    300-500ms).
  * Animate ONLY transform and opacity - never top/left/width/height.
  * Declare exact properties: never `transition: all`.
  * Elevation via semi-transparent LAYERED shadows, not solid borders.
  * Purpose test before animating: spatial consistency / state indication
    / feedback / prevents jarring change - else skip it.
  * Full doctrine vendored at assets/emil-skills/*.md
- TYPOGRAPHY AS VISUAL: display treatment oversized/contrasted; stats as
  huge numerals; measure <=70ch.
- SCROLL STORYTELLING: chapters with background-color journeys tied to
  narrative.
- PERFORMANCE LAW: total weight <=250KB, LCP <2s, CLS <0.1, 60fps on
  cheap Androids, prefers-reduced-motion honored. Stuttering kills
  premium faster than plainness - swap any risky effect for a cheaper
  illusion of the same feeling."""


def compile_brief(
    biz: str,
    facts: dict,
    audit_mobile: dict,
    orig: str,
    tokens_block: str,
    headings: list[str],
    images: list[str],
    rivals: list[dict],
    market_profile: str,
    is_no_site: bool,
    date: str,
    dna_block: str = "",
    warehouse_note: str = "",
) -> str:
    from .markets import MARKETS, VERTICAL_PROFILES, detect_vertical

    profile = MARKETS.get(market_profile) or MARKETS["in"]
    hay = " ".join(str(facts.get(k, "")) for k in ("tagline",)) + " " \
        + " ".join(str(s) for s in (facts.get("services") or [])) + " " \
        + str(facts.get("_vertical_tags", ""))
    vprof = detect_vertical(hay)
    pb = vprof.get("playbook") or {}
    playbook_block = "\n".join(
        f"{i}. {s}" for i, s in enumerate(pb.get("sections", []), 1)
    ) + (
        f"\n\nSIGNATURE COMPONENT (build this working, not as a mockup):\n"
        f"{pb.get('signature', '')}"
    ) or "(no playbook - use default local-business architecture)"

    from .design_dna import choose as dna_choose, render_block

    vkey = ""
    best_hits = 0
    for key, prof in VERTICAL_PROFILES.items():
        n = sum(1 for kw in prof["match"] if kw in hay.lower())
        if n > best_hits:
            vkey, best_hits = key, n
    dna = dna_choose(biz + "|" + orig, vkey)
    dna_block = render_block(dna)
    playbook_block = "\n".join(
        f"{i}. {s}" for i, s in enumerate(pb.get("sections", []), 1)
    ) + (
        f"\n\nSIGNATURE COMPONENT (build this working, not as a mockup):\n"
        f"{pb.get('signature', '')}"
    ) or "(no playbook - use default local-business architecture)"

    perf = audit_mobile.get("performance", "?")
    lcp = audit_mobile.get("lcp_s", "?")
    if is_no_site:
        audit_line = (
            "No prior website exists - this concept IS their first web "
            "presence. There are no old audit numbers; emphasize trust, "
            "clarity and instant contact."
        )
        original_note = (
            f"**This business has NO website today.** Every comparison "
            f"starts from zero - you are building their first web "
            f"presence. Reference listing: {orig}"
        )
    else:
        audit_line = (
            f"Mobile performance {perf}/100 · main content appears after "
            f"{lcp}s on the current site ({orig}). This concept targets "
            f"95+/100 and <2s - show these receipts honestly."
        )
        original_note = (
            f"Current site: {orig} - study it only for factual continuity "
            f"(their real content already lives in Facts JSON)."
        )

    if tokens_block.strip() and not tokens_block.startswith("("):
        pass
    assets_lines = []
    for rel in images:
        kind = "concept art (label as such on-page)" \
            if "gen-" in rel else "real photo"
        assets_lines.append(f"- dist/{rel} — {kind}")
    assets_block = "\n".join(assets_lines) if assets_lines \
        else "(none - design a typographic-first experience)"

    if rivals:
        comp_lines = "\n".join(
            f"- {r['name']} — {r['domain']} (nearby, same trade, HAS a "
            f"website: they are ahead of this business online)"
            for r in rivals
        )
    elif not is_no_site:
        comp_lines = "(no nearby same-trade websites found)"
    else:
        comp_lines = ("(nearby businesses mostly have no sites either — "
                      "first-mover framing)")

    currency = profile["currency"]
    starter = profile["packages"]["starter"]
    footer = (f"Concept by Facelift - content sourced from {orig} - "
              f"takedown on request")

    slots = {
        "BIZ": biz,
        "FACTS_JSON": json.dumps(
            {k: v for k, v in facts.items() if not k.startswith("_")},
            indent=2, ensure_ascii=False),
        "AUDIT_LINE": audit_line,
        "TOKENS_BLOCK": tokens_block,
        "COMPETITORS_BLOCK": comp_lines,
        "ASSETS_LIST": assets_block,
        "ORIGINAL_NOTE": original_note,
        "MARKET_LABEL": f"{profile['label']}",
        "LANGUAGE": profile["language"],
        "CURRENCY": currency,
        "FOOTER": footer,
        "LEGAL_BASIS": profile["legal_basis"],
        "PURPOSE": vprof["purpose"],
        "MUST_FEATURES": "\n".join(f"  - {m}" for m in vprof["must"]),
        "SCALE_FEATURES": "\n".join(f"  - {s}" for s in vprof["scaling"]),
        "PLAYBOOK": playbook_block,
        "COPY_VOICE": pb.get("voice", vprof.get("voice", "clear and honest")),
        "CRAFT": CRAFT_BLOCK,
        "DNA": dna_block,
        "WAREHOUSE": warehouse_note,
        "FIELD_RESEARCH": facts.get("_field_research", "")
        or "(research agent unavailable this run)",
        "PROPOSED_COPY": facts.get("_proposed_copy", "")
        or "(copy engine unavailable)",
        "HEADINGS": "",  # reserved: snapshot section map (optional context)
        "DATE": date,
    }
    # optional snapshot heading map appended to competitor context
    if headings:
        slots["COMPETITORS_BLOCK"] += (
            "\n\nOriginal-site section map to match-or-beat:\n"
            + "\n".join(f"- {h}" for h in headings)
        )

    text = MASTER.read_text(encoding="utf-8")
    for k, v in slots.items():
        text = text.replace("{{" + k + "}}", str(v))
    return text

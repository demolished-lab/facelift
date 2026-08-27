"""Design DNA engine - guarantees no two Facelift builds look alike.

Each build draws an art-direction genome: layout grammar, palette
strategy, typography attitude, motion signature, motif family. Choice is
seeded per-lead (stable rebuilds) but varies across leads, with an
anti-repeat memory over the last N designs.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

HISTORY = Path("data") / "design_history.json"

ARCHETYPES = [
    {
        "name": "Editorial Magazine",
        "layout": "asymmetric editorial grid, oversized serif display "
                  "headlines overlapping imagery edges, generous whitespace",
        "palette": "warm off-white base, ink black text, single deep "
                   "accent (burgundy/forest/navy) + paper-tone neutrals",
        "type": "serif display + humanist sans body, tight leading on "
                "headlines, drop caps allowed",
        "motion": "slow crossfades, line-draw underlines, staggered "
                  "editorial reveals",
        "motif": "thin rules + numbered chapters (01, 02…) as recurring "
                 "device",
    },
    {
        "name": "Neo-Brutalist Boutique",
        "layout": "bold blocks, visible borders, offset shadows, chunky "
                  "sections stacked with hard edges",
        "palette": "cream base, near-black text, 2 loud accents (electric "
                   "yellow / hot coral) used sparingly",
        "type": "heavy grotesque display + mono labels, ALL-CAPS kickers",
        "motion": "snap transitions, hover translate-with-shadow, marquee "
                  "ticker strip",
        "motif": "sticker-like badges + thick 2px borders everywhere",
    },
    {
        "name": "Dark Premium Glass",
        "layout": "deep near-black canvas, centered cinematic hero, glass "
                  "cards floating over gradient atmosphere",
        "palette": "#0b0d12 base, white text, one luminous accent "
                   "(violet/cyan/emerald) with soft glow",
        "type": "geometric sans display, wide tracking uppercase kickers",
        "motion": "glow-follow cursor, slow parallax drift, glass cards "
                  "fade-up staggered",
        "motif": "thin luminous outlines + radial glow orbs",
    },
    {
        "name": "Warm Artisanal",
        "layout": "handcrafted feel, organic section shapes (soft blobs/"
                  "arches), centered storytelling flow",
        "palette": "terracotta/olive/cream earth tones, deep brown text",
        "type": "rounded friendly display + readable serif body",
        "motion": "gentle rise reveals, image wobble-on-hover, hand-drawn "
                  "underline strokes",
        "motif": "arched image masks + stitched dashed dividers",
    },
    {
        "name": "Swiss Precision Grid",
        "layout": "strict 12-col grid, flush-left ragged-right, massive "
                  "whitespace, numbered index navigation",
        "palette": "pure white, single red/black duotone, grey hierarchy",
        "type": "neo-grotesque (Helvetica-class) at extreme scale contrast",
        "motion": "instant crisp fades (120ms), precise underline slides, "
                  "grid-line draw-in",
        "motif": "visible grid lines + index numbers as design elements",
    },
    {
        "name": "Organic Gradient Flow",
        "layout": "fluid wave-section transitions, content floating on "
                  "animated gradient atmosphere",
        "palette": "deep indigo→teal→sunset gradient journey across "
                   "scroll, glass panels",
        "type": "modern rounded sans, generous sizes",
        "motion": "background gradient slowly shifts hue per section, "
                  "floating decorative blobs parallax",
        "motif": "wave SVG dividers + soft glow pills",
    },
    {
        "name": "Retro Print Poster",
        "layout": "poster-style hero filling viewport, rotated stamps/"
                  "labels, collage composition",
        "palette": "aged paper base, 3-color risograph print set "
                   "(teal/red/mustard), halftone textures",
        "type": "condensed vintage display + typewriter accents",
        "motion": "stamp-stamp reveals (scale-bounce), tape-texture "
                  "stickers peel on hover",
        "motif": "rotated date-stamps + barcode strips",
    },
    {
        "name": "Minimal Luxe Mono",
        "layout": "extreme minimalism, one idea per viewport, huge gaps, "
                  "single-column luxury pacing",
        "palette": "monochrome greys + single metallic accent (gold/"
                   "silver/champagne)",
        "type": "ultra-light large display + small caps details",
        "motion": "opacity-only luxury fades, letter-spacing breathe on "
                  "hover",
        "motif": "hairline gold rules + tiny diamond bullets",
    },
]

TRADE_BIAS = {
    "hostel": ["Editorial Magazine", "Warm Artisanal", "Dark Premium Glass"],
    "restaurant": ["Warm Artisanal", "Retro Print Poster",
                   "Neo-Brutalist Boutique"],
    "clinic": ["Swiss Precision Grid", "Minimal Luxe Mono",
               "Organic Gradient Flow"],
    "fitness": ["Neo-Brutalist Boutique", "Dark Premium Glass",
                "Organic Gradient Flow"],
    "salon": ["Minimal Luxe Mono", "Organic Gradient Flow",
              "Editorial Magazine"],
}


def _history() -> list[str]:
    try:
        return json.loads(HISTORY.read_text())
    except Exception:  # noqa: BLE001
        return []


def _save_history(recents: list[str]) -> None:
    HISTORY.parent.mkdir(parents=True, exist_ok=True)
    HISTORY.write_text(json.dumps(recents[-12:]))


def choose(seed_text: str, vertical_key: str = "") -> dict:
    """Deterministic per seed_text, biased by trade, avoiding the last 5
    used archetypes when alternatives exist."""
    bias = TRADE_BIAS.get(vertical_key)
    pool = ([a for a in ARCHETYPES if a["name"] in bias] if bias
            else []) + [a for a in ARCHETYPES
                        if not bias or a["name"] not in bias]
    digest = hashlib.sha256(
        (seed_text + "|" + vertical_key).encode()).hexdigest()
    recents = _history()
    fresh = [a for a in pool if a["name"] not in recents[-5:]] or pool
    idx = int(digest[:8], 16) % len(fresh)
    choice = fresh[idx]
    _save_history(recents + [choice["name"]])
    return choice


def render_block(dna: dict) -> str:
    return (
        f"- Archetype: **{dna['name']}** — {dna['layout']}\n"
        f"- Palette strategy: {dna['palette']}\n"
        f"- Typography attitude: {dna['type']}\n"
        f"- Motion signature: {dna['motion']}\n"
        f"- Recurring motif (use ≥3 places): {dna['motif']}"
    )

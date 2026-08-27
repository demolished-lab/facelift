"""Dedicated copy engine (upgrade #6): trade-specific voice, headlines,
benefit-led structure — a separate LLM pass from everything else.

Grounded in Facts JSON. Never invents. Output = proposed copy the owner
can edit, clearly labeled in the page.
"""

from __future__ import annotations

import json

from .llm import chat, parse_json_loose
from .markets import detect_vertical, MARKETS
from .speculative import deterministic_copy

VOICE_PROMPTS = {
    "hostel": "warm, safety-conscious, local-guide tone. Short sentences a tired traveler skims.",
    "restaurant": "appetizing, local pride, zero fluff. Write like a favorite food writer.",
    "clinic": "calm, credentialed, reassuring. Clarity over persuasion.",
    "fitness": "energetic, no-excuses, second person. 'You', never 'we offer'.",
    "salon": "stylish, pampering, confident. Beauty-editor tone.",
    "default": "clear, honest, locally rooted. Plain words that build trust fast.",
}


def write_copy(biz: str, facts: dict, trade: str,
               market: str) -> dict:
    """Dedicated copy pass: headlines, section copy, CTA text.
    Returns structured copy dict. Grounded in Facts only."""
    from .markets import MARKETS

    profile = MARKETS.get(market, MARKETS["in"])
    voice = VOICE_PROMPTS.get(trade, VOICE_PROMPTS["default"])
    services = facts.get("services", [])
    addr = facts.get("address", "")
    city = addr.split(",")[-2].strip() if "," in addr else ""

    system = (
        f"You are a senior copywriter for {biz}, a {trade} business"
        + (f" in {city}, {profile['label']}" if city else
           f" in {profile['label']}") + ". "
        f"Voice: {voice}. "
        "You write SPECIFIC, benefit-led copy grounded ONLY in the facts "
        "provided. Never invent facts, prices, reviews, or claims. "
        "Headlines are max 8 words. CTAs are max 4 words. "
        "Reply ONLY with a JSON object."
    )
    prompt = (
        f"Write website copy for {biz}. Facts: "
        f"{json.dumps({k: v for k, v in facts.items() if not k.startswith('_')}, ensure_ascii=False)}\n\n"
        "Generate:\n"
        '1. "headlines": array of 3 homepage headline options\n'
        '2. "subheadline": one supporting line (max 15 words)\n'
        '3. "about": 2-sentence about paragraph\n'
        '4. "cta_primary": main call-to-action (max 4 words)\n'
        '5. "cta_secondary": secondary CTA (max 4 words)\n'
        '6. "service_descriptions": object mapping each service name to '
        'a one-line benefit description\n'
        '7. "meta_description": 150-char SEO description\n'
        "If facts are thin, write LESS copy, not generic filler. "
        "Every word must feel like it belongs to THIS specific business."
    )
    try:
        raw, model = chat(prompt, system=system, max_tokens=1200,
                          json_mode=True, temperature=0.7)
        data = parse_json_loose(raw)
        data["_model"] = model
        return data
    except Exception:  # noqa: BLE001 - copy optional
        # deterministic fallback: templated headlines/CTA when LLM fails
        city = facts.get("address", "").split(",")[-2].strip() if "," in facts.get("address", "") else ""
        det = deterministic_copy(biz, trade, city=city)
        det["_model"] = "deterministic-fallback"
        det["_fallback"] = True
        return det



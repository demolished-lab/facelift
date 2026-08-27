"""Concept imagery generator (FR-3 for CREATE-class leads).

Auto-prompts an image model (Gemini flash-image, already behind the
owner's free key) to produce photorealistic, brand-safe visuals for
businesses that have NO photography of their own. Every generated asset
is labeled concept art on the page so nothing misrepresents the business.
"""

from __future__ import annotations

import base64
import json
import urllib.parse
import urllib.request

from .llm import _load_env

GEN_URL = ("https://generativelanguage.googleapis.com/v1beta/models/"
           "gemini-2.5-flash-image:generateContent")


def _key() -> str | None:
    _load_env()
    import os

    return os.environ.get("GEMINI_API_KEY")


def _gemini(prompt: str, timeout_s: int = 120) -> bytes | None:
    key = _key()
    if not key:
        return None
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]},
    }).encode()
    req = urllib.request.Request(
        f"{GEN_URL}?key={key}",
        data=body,
        headers={"Content-Type": "application/json",
                 "User-Agent": "facelift/0.1"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            data = json.load(resp)
        parts = data["candidates"][0]["content"]["parts"]
        for p in parts:
            inline = p.get("inlineData")
            if inline and inline.get("data"):
                return base64.b64decode(inline["data"])
    except Exception:  # noqa: BLE001 - caller degrades gracefully
        return None
    return None


def _pollinations(prompt: str, width: int = 1280, height: int = 768,
                  timeout_s: int = 90) -> bytes | None:
    import random

    seed = random.randint(1, 999_999)
    url = (
        "https://image.pollinations.ai/prompt/"
        + urllib.parse.quote(prompt[:900])
        + f"?width={width}&height={height}&nologo=true&seed={seed}"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "facelift/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            data = resp.read(12_000_000)
        return data if len(data) > 20_000 else None
    except Exception:  # noqa: BLE001 - caller degrades gracefully
        return None


def generate(prompt: str, timeout_s: int = 120) -> bytes | None:
    """Free-first chain: Pollinations (keyless) -> Gemini flash-image."""
    import urllib.parse

    img = _pollinations(prompt)
    if img:
        return img
    return _gemini(prompt, timeout_s=timeout_s)


STYLE_BASE = (
    "photorealistic, natural light, shot on a phone camera, realistic "
    "Indian small-business setting, warm and inviting, no text, no "
    "watermarks, no logos, no readable signs, faces not identifiable"
)

VERTICAL_SCENES = {
    "hostel": [
        "cozy backpacker hostel common room in the evening, string lights, "
        "plants, travelers' backpacks on bunks, shared table",
        "clean simple private room with a window, ceiling fan, folded "
        "towels on a bed, morning light",
    ],
    "restaurant": [
        "small restaurant interior at dusk, set tables, warm pendant "
        "lamps, kitchen glow in the background",
        "close-up of appetizing plated food on a wooden table",
    ],
    "clinic": [
        "calm modern clinic waiting area, chairs, plant, soft daylight, "
        "reception desk",
    ],
    "fitness": [
        "compact gym interior with racks and mats, morning light through "
        "windows, chalk dust in the air",
    ],
    "salon": [
        "stylish small salon interior, mirrors with warm bulbs, clean "
        "stations, plants",
    ],
}
DEFAULT_SCENES = [
    "welcoming storefront and counter of a small local business, tidy, "
    "daylight, products neatly arranged",
]


def scenes_for_vertical(vertical_key: str, detected_text: str) -> list[str]:
    from .markets import detect_vertical

    prof = detect_vertical(detected_text)
    key = vertical_key or next(
        (k for k, p in __import__("facelift.markets",
                                  fromlist=["x"]).VERTICAL_PROFILES.items()
         if p is prof),
        None,
    )
    scenes = VERTICAL_SCENES.get(key or "", DEFAULT_SCENES)
    return [f"{s}, {STYLE_BASE}" for s in scenes]

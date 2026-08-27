"""Free-tier LLM router (BLUEPRINT §3).

Owner-provided OpenRouter key first; rotating ':free' model chain because
free availability shifts daily. Hard rules: free-only allowlist, providers
bench themselves on 429/errors, every failure surfaces instead of silently
degrading quality.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
OR_URL = "https://openrouter.ai/api/v1/chat/completions"
NIM_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
USER_AGENT = "facelift/0.1"

PROVIDERS = [
    {
        "name": "openrouter",
        "url": OR_URL,
        "key_env": "OPENROUTER_API_KEY",
        "models": [
            "deepseek/deepseek-chat-v3-0324:free",
            "meta-llama/llama-3.3-70b-instruct:free",
            "google/gemini-2.0-flash-exp:free",
            "qwen/qwen-2.5-72b-instruct:free",
        ],
    },
    {
        "name": "gemini",
        "url": GEMINI_URL,
        "key_env": "GEMINI_API_KEY",
        "models": [
            "gemini-3.6-flash",
            "gemini-flash-latest",
            "gemini-flash-lite-latest",
        ],
    },
    {
        "name": "nvidia-nim",
        "url": NIM_URL,
        "key_env": "NVIDIA_API_KEY",
        "models": [
            "meta/llama-3.3-70b-instruct",
            "meta/llama-3.1-8b-instruct",
        ],
    },
]

BENCH_SECONDS = 1800
_benched: dict[str, float] = {}
_failures: dict[str, int] = {}


def _load_env() -> None:
    if not ENV_PATH.exists():
        return
    for line in ENV_PATH.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


def candidates() -> list[tuple[str, str, str]]:
    """Returns [(provider_name, url, api_key, model)] for all unbenched slots."""
    _load_env()
    now = time.monotonic()
    out = []
    for p in PROVIDERS:
        key = os.environ.get(p["key_env"])
        if not key:
            continue
        for model in p["models"]:
            slot = f"{p['name']}:{model}"
            until = _benched.get(slot, 0)
            if until and now >= until:
                _benched.pop(slot, None)
                _failures.pop(slot, None)
            if slot not in _benched:
                out.append((slot, p["url"], key, model))
    return out


def chat(prompt: str, system: str | None = None, max_tokens: int = 900,
         temperature: float = 0.2, json_mode: bool = False) -> tuple[str, str]:
    slots = candidates()
    if not slots:
        raise RuntimeError("no LLM providers available - check .env keys/benches")

    messages = ([{"role": "system", "content": system}] if system else []) + [
        {"role": "user", "content": prompt}
    ]
    last_err: Exception | None = None
    for slot, url, key, model in slots:
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if json_mode and "generativelanguage.googleapis.com" in url:
            payload["response_format"] = {"type": "json_object"}
        body = json.dumps(payload).encode()
        req = urllib.request.Request(
            url,
            data=body,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "User-Agent": USER_AGENT,
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                data = json.load(resp)
            _failures.pop(slot, None)
            text = (data["choices"][0]["message"].get("content") or "").strip()
            if not text:
                raise ValueError("empty completion")
            return text, slot
        except urllib.error.HTTPError as ex:
            last_err = ex
            if ex.code == 429:
                _benched[slot] = time.monotonic() + BENCH_SECONDS
            else:
                _failures[slot] = _failures.get(slot, 0) + 1
                if _failures[slot] >= 2:
                    _benched[slot] = time.monotonic() + BENCH_SECONDS // 6
        except Exception as ex:  # noqa: BLE001 - triage upstream
            last_err = ex
            _failures[slot] = _failures.get(slot, 0) + 1
    raise RuntimeError(f"all candidate model slots failed: {last_err}")


def _repair_truncated(t: str) -> dict | None:
    start = t.find("{")
    if start == -1:
        return None
    body = t[start:].rstrip()
    while body.endswith(","):
        body = body[:-1].rstrip()
    stack: list[str] = []
    in_str = False
    esc = False
    for ch in body:
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch in "{[":
            stack.append(ch)
        elif ch in "}]":
            if stack:
                stack.pop()
    if in_str:
        body += '"'
    closers = "".join("}" if c == "{" else "]" for c in reversed(stack))
    try:
        return json.loads(body + closers)
    except ValueError:
        return None


def parse_json_loose(text: str) -> dict:
    import re

    t = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", t, re.S)
    if fence:
        t = fence.group(1)
    start = t.find("{")
    if start == -1:
        raise ValueError(f"no JSON object in model output: {text[:120]!r}")
    dec = json.JSONDecoder()
    idx = start
    while idx != -1:
        try:
            obj, _end = dec.raw_decode(t[idx:])
            return obj
        except ValueError:
            idx = t.find("{", idx + 1)
    repaired = _repair_truncated(t)
    if repaired is not None:
        return repaired
    raise ValueError(f"unparseable JSON in model output: {text[:200]!r}")

"""Deployer v2 — raw Cloudflare Workers REST API (stdlib only).

Replaces wrangler entirely (immune to oauth-cache/scope-probe issues).
Model: per-site KV namespace holds every asset; a tiny module Worker
serves them at <name>.<subdomain>.workers.dev. Free tier covers this
comfortably (100k reads/day, 1k writes/day).

Endpoints used (all stdlib urllib):
  GET  /accounts/:id/workers/subdomain         -> workers.dev subdomain
  POST /accounts/:id/workers/subdomain         -> claim one if missing
  GET  /accounts/:id/storage/kv/namespaces     -> list
  POST /accounts/:id/storage/kv/namespaces     -> create per-site ns
  PUT  /accounts/:id/storage/kv/namespaces/:ns/bulk   -> batch assets
  PUT  /accounts/:id/workers/scripts/:name     -> module upload (multipart)
  PUT  /accounts/:id/workers/scripts/:name/subdomain -> enable route
  DELETE /accounts/:id/workers/scripts/:name   -> takedown
"""

from __future__ import annotations

import base64
import json
import os
import re
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

from .llm import _load_env

API = "https://api.cloudflare.com/client/v4"
SUBDOMAIN_CANDIDATES = ["facelift", "facelift-agency", "facelift-hq"]


def _token() -> str:
    _load_env()
    tok = os.environ.get("CF_API_TOKEN")
    if not tok:
        raise RuntimeError("CF_API_TOKEN missing in .env")
    return tok


def _account() -> str:
    _load_env()
    aid = os.environ.get("CF_ACCOUNT_ID")
    if not aid:
        raise RuntimeError("CF_ACCOUNT_ID missing in .env")
    return aid


def _req(method: str, path: str, *, json_body=None, raw_body=None,
         headers=None, timeout: int = 120):
    h = {"Authorization": f"Bearer {_token()}",
         "User-Agent": "facelift/0.1"}
    if headers:
        h.update(headers)
    data = None
    if json_body is not None:
        data = json.dumps(json_body).encode()
        h["Content-Type"] = "application/json"
    elif raw_body is not None:
        data = raw_body
    req = urllib.request.Request(API + path, data=data, method=method,
                                 headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def _api_ok(d: dict) -> dict:
    if not d.get("success"):
        errs = "; ".join(str(e.get("message")) for e in d.get("errors", []))
        raise RuntimeError(f"cloudflare api error: {errs[:300]}")
    return d["result"]


def get_subdomain() -> str:
    r = _api_ok(_req("GET", f"/accounts/{_account()}/workers/subdomain"))
    sub = r.get("subdomain")
    if sub:
        return sub
    for cand in SUBDOMAIN_CANDIDATES:
        cand += f"-{uuid.uuid4().hex[:6]}"
        try:
            _api_ok(_req("POST", f"/accounts/{_account()}/workers/subdomain",
                         json_body={"subdomain": cand}))
            return cand
        except RuntimeError:
            continue
    raise RuntimeError("could not claim a workers.dev subdomain")


def ensure_namespace(title: str) -> str:
    r = _api_ok(_req("GET",
                     f"/accounts/{_account()}/storage/kv/namespaces"))
    for ns in r:
        if ns.get("title") == title:
            return ns["id"]
    r = _api_ok(_req("POST",
                     f"/accounts/{_account()}/storage/kv/namespaces",
                     json_body={"title": title}))
    return r["id"]


def kv_bulk(ns_id: str, items: list[tuple[str, bytes]]) -> None:
    """Base64 batch write; chunks to keep requests sane."""
    payload_items = [
        {"key": k,
         "value": base64.b64encode(v).decode(),
         "base64": True}
        for k, v in items
    ]
    for i in range(0, len(payload_items), 40):
        chunk = payload_items[i:i + 40]
        _api_ok(_req("PUT",
                     f"/accounts/{_account()}/storage/kv/namespaces/"
                     f"{ns_id}/bulk",
                     json_body=chunk, timeout=300))


WORKER_JS = """export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    let p = decodeURIComponent(url.pathname);
    if (p.endsWith("/")) p += "index.html";
    p = p.replace(/^\\/+/, "");
    const TYPES = {
      html: "text/html; charset=utf-8",
      png: "image/png", jpg: "image/jpeg", jpeg: "image/jpeg",
      webp: "image/webp", avif: "image/avif", gif: "image/gif",
      svg: "image/svg+xml", css: "text/css; charset=utf-8",
      js: "text/javascript; charset=utf-8",
      json: "application/json", txt: "text/plain; charset=utf-8",
      ico: "image/x-icon", woff2: "font/woff2"
    };
    async function serve(key) {
      const buf = await env.ASSETS.get(key, { type: "arrayBuffer" });
      if (buf === null) return null;
      const ext = key.split(".").pop().toLowerCase();
      return new Response(buf, {
        headers: {
          "content-type": TYPES[ext] || "application/octet-stream",
          "cache-control": ext === "html"
            ? "public, max-age=300"
            : "public, max-age=86400"
        }
      });
    }
    let res = await serve(p);
    if (!res && !p.includes(".")) {
      res = await serve(p.replace(/\/+$/, "") + "/index.html");
    }
    if (!res) res = await serve("index.html");
    if (res) return res;
    return new Response("Not found", { status: 404 });
  }
};
"""


def _multipart(parts: list[tuple[str, str, bytes]]) -> tuple[bytes, str]:
    boundary = "----facelift" + uuid.uuid4().hex
    body = bytearray()
    for name, ctype, data in parts:
        body += (f"--{boundary}\r\n"
                 f'Content-Disposition: form-data; name="{name}"; '
                 f'filename="{name}"\r\n'
                 f"Content-Type: {ctype}\r\n\r\n").encode()
        body += data + b"\r\n"
    body += f"--{boundary}--\r\n".encode()
    return bytes(body), boundary


def upload_script(name: str, worker_js: str, ns_id: str) -> None:
    meta = {
        "main_module": "worker.js",
        "compatibility_date": "2025-01-01",
        "bindings": [{"type": "kv_namespace", "name": "ASSETS",
                      "namespace_id": ns_id}],
    }
    parts = [
        ("metadata", "application/json", json.dumps(meta).encode()),
        ("worker.js", "application/javascript+module",
         worker_js.encode()),
    ]
    body, boundary = _multipart(parts)
    _req("PUT",
         f"/accounts/{_account()}/workers/scripts/{name}",
         raw_body=body,
         headers={"Content-Type":
                  f"multipart/form-data; boundary={boundary}"},
         timeout=300)


def enable_subdomain(name: str) -> None:
    _req("PUT",
         f"/accounts/{_account()}/workers/scripts/{name}/subdomain",
         json_body={"enabled": True, "previews_enabled": True})


def collect_files(dist: Path) -> list[tuple[str, bytes]]:
    out = []
    for p in sorted(dist.rglob("*")):
        if p.is_file():
            rel = p.relative_to(dist).as_posix()
            out.append((rel, p.read_bytes()))
    return out


def deploy_dir(dist: Path, name: str) -> str:
    name = re.sub(r"[^a-z0-9_-]", "-", name.lower())
    sub = get_subdomain()
    ns_id = ensure_namespace(f"{name}-assets")

    files = collect_files(dist)
    if not files:
        raise RuntimeError("dist empty - nothing to deploy")
    kv_items = []
    for rel, data in files:
        kv_items.append((rel, data))
    # html served from KV too; index.html handled by worker fallback
    kv_bulk(ns_id, kv_items)

    upload_script(name, WORKER_JS, ns_id)
    try:
        enable_subdomain(name)
    except Exception:  # noqa: BLE001 - modern uploads enable by default
        pass

    url = f"https://{name}.{sub}.workers.dev"
    for _ in range(6):
        time.sleep(5)
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "facelift/0.1"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                if resp.status == 200:
                    return url
        except Exception:  # noqa: BLE001 - propagation takes a moment
            continue
    return url


def takedown(name: str) -> None:
    try:
        _req("DELETE", f"/accounts/{_account()}/workers/scripts/{name}")
    except Exception as ex:  # noqa: BLE001 - already gone is fine
        print(f"(takedown note: {str(ex)[:80]})")


def purge_namespace(title_prefix: str) -> None:
    """Optional hygiene: delete namespaces of expired previews."""
    r = _api_ok(_req("GET",
                     f"/accounts/{_account()}/storage/kv/namespaces"))
    for ns in r:
        if str(ns.get("title", "")).startswith(title_prefix):
            try:
                _req("DELETE",
                     f"/accounts/{_account()}/storage/kv/namespaces/"
                     f"{ns['id']}")
            except Exception:  # noqa: BLE001
                pass

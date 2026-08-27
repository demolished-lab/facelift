"""FR-4 contact waterfall (PRD FR-4.1, SECURITY-AUDIT F2/F3).

Order: self-published on their site (DPDP 7(a)-clean, verified) ->
WHOIS registrant (verified=confidence 70) -> role inboxes recorded but
UNVERIFIED and therefore unsendable as email (usable only as contact-form
targets). Guessing person-level patterns is banned in v0.
"""

from __future__ import annotations

import re
import socket

import urllib.request

from .measure import USER_AGENT

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_TEL_RE = re.compile(r"tel:\+?([\d\s()\-]{7,20})")
BAD_EMAIL_PARTS = (
    ".png", ".jpg", ".jpeg", ".webp", ".gif", "example.", "sentry",
    "your-email", "email.com", "@2x", "wixpress",
)

CONTACT_PATHS = ("/contact", "/contact-us", "/about", "/about-us")

WHOIS_SERVERS = {
    "com": "whois.verisign-grs.com",
    "net": "whois.verisign-grs.com",
    "org": "whois.publicinterestregistry.net",
    "in": "whois.registry.in",
    "io": "whois.nic.io",
    "co": "whois.nic.co",
    "dev": "whois.nic.google",
}
WHOIS_JUNK = ("privacy", "redact", "proxy", "abuse@", "registrar.",
              "whoisguard", "domainsafe", "data-protected")


def _fetch(url: str, timeout: int = 15) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read(1_500_000).decode("utf-8", errors="ignore")


def harvest_from_site(domain: str) -> tuple[set[str], set[str]]:
    emails: set[str] = set()
    phones: set[str] = set()
    for path in ("", ) + CONTACT_PATHS:
        url = f"https://{domain}{path}"
        try:
            page = _fetch(url)
        except Exception:  # noqa: BLE001 - missing pages are normal
            continue
        body = re.sub(r"<(script|style).*?</\1>", " ", page, flags=re.S | re.I)
        for m in EMAIL_RE.findall(body):
            e = m.strip().lower()
            if len(e) > 50 or any(b in e for b in BAD_EMAIL_PARTS):
                continue
            emails.add(e)
        for m in PHONE_TEL_RE.findall(page):
            digits = re.sub(r"[^\d+]", "", m)
            if len(re.sub(r"\D", "", digits)) >= 8:
                phones.add(digits)
    return emails, phones


def _whois_query(server: str, domain: str) -> str:
    with socket.create_connection((server, 43), timeout=12) as s:
        s.sendall(f"{domain}\r\n".encode())
        chunks = []
        while True:
            data = s.recv(4096)
            if not data:
                break
            chunks.append(data.decode("utf-8", errors="ignore"))
    return "\n".join(chunks)


def whois_email(domain: str) -> str | None:
    tld = domain.rsplit(".", 1)[-1]
    server = WHOIS_SERVERS.get(tld, "whois.iana.org")
    try:
        text = _whois_query(server, domain)
    except Exception:  # noqa: BLE001 - whois flakiness expected
        return None
    low = text.lower()
    if "refer:" in low and server == "whois.iana.org":
        ref = low.split("refer:")[1].split()[0]
        try:
            text = _whois_query(ref.strip(), domain)
            low = text.lower()
        except Exception:  # noqa: BLE001
            pass
    registrant_zone = low.split("registrant:")[0][-400:] + low[:2000]
    found = EMAIL_RE.findall(registrant_zone)
    for e in found:
        e = e.strip().lower()
        if any(j in e for j in WHOIS_JUNK):
            continue
        return e
    return None


def waterfall(domain: str) -> list[tuple[str, str, str, int, bool]]:
    """Returns [(kind, value, source, confidence, verified)]."""
    out: list[tuple[str, str, str, int, bool]] = []
    seen: set[str] = set()
    emails, phones = harvest_from_site(domain)
    for e in sorted(emails):
        if e not in seen:
            out.append(("email", e, "site", 90, True))
            seen.add(e)
    we = whois_email(domain)
    if we and we not in seen:
        out.append(("email", we, "whois", 70, False))
        seen.add(we)
    else:
        for role in ("info", "contact", "hello"):
            guess = f"{role}@{domain}"
            if guess not in seen:
                # Unverifiable guess: NEVER email-sendable (F2). Form-only.
                out.append(("form_target", guess, "role_guess", 30, False))
                seen.add(guess)
                break
    for p in sorted(phones)[:2]:
        out.append(("phone", p, "site", 85, True))
    return out

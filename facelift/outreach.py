"""FR-5 outreach: compliance engine, message builder, gated sender.

Gates (SECURITY-AUDIT G2-G6, F2-F4): verified self-published contact only,
suppression checked at send instant, jurisdiction allowlist, owner approval
bound to body hash, mandatory identity footer. Sender = Gmail-class mailbox
via app password; caps enforced from event history.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import os
import re
import smtplib
from email import message_from_bytes
from email.header import decode_header
from email.message import EmailMessage

from .llm import _load_env
from .markets import MARKETS
from .store import Store

ALLOWED_MARKETS = {"in", "us"}
BLOCKED_MARKETS = {"de", "ca"}
DAILY_SEND_CAP = 30


class NotReady(RuntimeError):
    pass


def _decode(s: str) -> str:
    out = ""
    for t, enc in decode_header(s):
        out += t.decode(enc or "utf-8", errors="ignore") \
            if isinstance(t, bytes) else t
    return out


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def poll_replies(store: Store, limit: int = 25) -> list[dict]:
    """IMAP reply watcher (FR-5.5): opt-outs suppress automatically,
    bounces suppress, hot replies flagged for the operator."""
    import imaplib

    _load_env()
    user = os.environ.get("FACELIFT_SENDER_EMAIL", "operator@example.com")
    pw = os.environ.get("GMAIL_APP_PASSWORD")
    if not pw:
        raise NotReady("GMAIL_APP_PASSWORD missing in .env")

    out: list[dict] = []
    m = imaplib.IMAP4_SSL("imap.gmail.com", 993)
    m.login(user, pw)
    m.select("INBOX")
    since = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=7)
             ).strftime("%d-%b-%Y")
    typ, data = m.search(None, f'(SINCE "{since}")')
    ids = (data[0].split() if typ == "OK" else [])[-limit:]
    for mid in reversed(ids):
        typ, msg_data = m.fetch(mid, "(RFC822)")
        if typ != "OK":
            continue
        msg = message_from_bytes(msg_data[0][1])
        frm = _decode(msg.get("From", ""))
        subj = _decode(msg.get("Subject", ""))
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    body = part.get_payload(decode=True).decode(
                        "utf-8", errors="ignore")
                    break
        else:
            body = msg.get_payload(decode=True).decode(
                "utf-8", errors="ignore")
        blob = (subj + " " + body[:1500]).lower()
        fm = re.search(r"[\w.+-]+@[\w.-]+", frm)
        sender_email = fm.group(0).lower() if fm else None

        if "mailer-daemon" in frm.lower() or "delivery" in subj.lower():
            kind = "bounce"
        elif any(k in blob for k in (
                "not interested", "unsubscribe", "remove me",
                "stop emailing", "no thanks")):
            kind = "opt_out"
        elif any(k in blob for k in (
                "interested", "price", "how much", "call me",
                "tell me more")):
            kind = "hot"
        else:
            kind = "other"

        if sender_email and kind in ("opt_out", "bounce"):
            store.suppress(sender_email, f"reply:{kind}", _now())
        if kind != "other":
            store.log("reply", {"kind": kind, "subject": subj[:80],
                                "email": sender_email}, ts=_now())
        out.append({"from": frm[:60], "subject": subj[:70],
                    "kind": kind, "email": sender_email})
    m.logout()
    return out


def track_for_learning(store: Store, lead_id: str) -> dict:
    """Capture build attributes for the learning loop."""
    rebuilt = store.last_event_detail(lead_id, "rebuilt") or {}
    return {"lead_id": lead_id, "worker": rebuilt.get("worker", ""),
            "tracked_at": _now()}


def record_send_for_learning(store: Store, lead_id: str, msg: dict) -> None:
    attrs = track_for_learning(store, lead_id)
    attrs["sent_hash"] = msg.get("body_hash", "")
    attrs["sent_to"] = msg.get("to", "")
    store.log("learning_send", attrs, lead_id, ts=_now())


def _today() -> str:
    return dt.datetime.now(dt.timezone.utc).date().isoformat()


def compliance_verdict(market: str) -> tuple[bool, str]:
    if market in BLOCKED_MARKETS:
        return False, f"jurisdiction {market} blocked by policy"
    if market not in ALLOWED_MARKETS:
        return False, f"no compliance profile for {market}"
    profile = MARKETS[market]
    sender = profile["sender"]
    if not sender.get("address_line"):
        return False, "sender address_line empty (CAN-SPAM/DPDP requirement)"
    if not sender.get("privacy_url"):
        return False, "privacy_url empty - host privacy page first"
    basis = profile["legal_basis"]
    return True, f"ok ({basis})"


def render(lead_name: str, domain: str, market: str, preview_url: str,
           pair_url: str, stats: dict) -> dict:
    profile = MARKETS[market]
    sender = profile["sender"]
    perf = stats.get("perf", "?")
    lcp = stats.get("lcp", "?")

    # Signal-based selling: lead with the SPECIFIC evidence, not generic
    # pain. The signal is the measured audit receipt — it's verifiable.
    signals = []
    if isinstance(perf, int) and perf < 50:
        signals.append(f"speed score {perf}/100 (Google flags below 50)")
    if isinstance(lcp, (int, float)) and lcp > 4:
        signals.append(f"{lcp}s before content appears on a phone")
    signal_line = "; ".join(signals) if signals else "no mobile-optimized presence"

    subject = f"{lead_name}: {lcp}s load time on phones — I already fixed it"
    currency = profile["currency"]
    starter = profile["packages"]["starter"]
    body = (
        f"Hi,\n\n"
        f"I ran a speed audit on {domain} — {signal_line}.\n\n"
        f"Rather than tell you, I built the fix:\n"
        f"Before/after: {pair_url}\n"
        f"Live concept: {preview_url}\n\n"
        f"Same content, your photos, loads in under 2 seconds. "
        f"If you want it as your real site, it starts at "
        f"{currency} {starter:,} — delivered in days, not weeks.\n\n"
        f"Reply 'no' and I'll never email again.\n\n"
        f"- {sender['name']}\n{sender['email']}\n"
        f"{sender.get('address_line','')}\n"
        f"Privacy: {sender.get('privacy_url','')}\n"
    )
    body_hash = hashlib.sha256(body.encode()).hexdigest()[:16]
    return {"subject": subject, "body": body, "body_hash": body_hash}


def draft(store: Store, lead_id: str) -> dict:
    lead = store.get_lead(lead_id)
    if lead is None:
        raise NotReady(f"no such lead {lead_id}")
    contacts = [c for c in store.list_contacts(lead_id)
                if c["kind"] == "email" and c["verified"]]
    if not contacts:
        raise NotReady("no verified email contact - run contacts first")
    rebuilt = store.last_event_detail(lead_id, "rebuilt")
    if not rebuilt:
        raise NotReady("lead has no deployed preview - run rebuild first")
    audit_ev = store.last_event_detail(lead_id, "audited") or {}
    mobile = audit_ev.get("mobile") or {}
    ok, reason = compliance_verdict(lead.market_profile)
    if not ok:
        raise NotReady(f"compliance gate: {reason}")
    msg = render(
        lead.name, lead.domain, lead.market_profile,
        rebuilt["url"], rebuilt["url"].rstrip("/") + "/before-after.html",
        {"perf": mobile.get("performance", "?"),
         "lcp": mobile.get("lcp_s", "?")},
    )
    msg.update({"to": contacts[0]["value"], "market": lead.market_profile})
    store.log("drafted", msg, lead_id,
              ts=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"))
    return msg


def sends_today(store: Store) -> int:
    r = store.conn.execute(
        "SELECT COUNT(*) AS c FROM events WHERE kind='sent' AND ts LIKE ?",
        (f"{_today()}%",),
    ).fetchone()
    return int(r["c"])


def send(store: Store, lead_id: str, approve_hash: str) -> str:
    ev = store.last_event_detail(lead_id, "drafted")
    if not ev:
        raise NotReady("no draft found - run draft first")
    if approve_hash != ev["body_hash"]:
        raise NotReady("approval hash mismatch - re-run draft and approve "
                       "the exact current body")
    if store.is_suppressed(ev["to"]):
        raise NotReady("contact is suppressed")
    if sends_today(store) >= DAILY_SEND_CAP:
        raise NotReady(f"daily cap {DAILY_SEND_CAP} reached - try tomorrow")
    _load_env()
    app_pw = os.environ.get("GMAIL_APP_PASSWORD")
    if not app_pw:
        raise NotReady("GMAIL_APP_PASSWORD missing in .env (Google account "
                       "-> Security -> 2-Step Verification -> App passwords)")
    smtp_user = os.environ.get(
        "FACELIFT_SENDER_EMAIL", "operator@example.com"
    )
    m = EmailMessage()
    m["From"] = smtp_user
    m["To"] = ev["to"]
    m["Subject"] = ev["subject"]
    m.set_content(ev["body"])
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as s:
        s.login(smtp_user, app_pw)
        s.send_message(m)
    record_send_for_learning(store, lead_id, ev)
    store.log("sent", {"to": ev["to"], "hash": ev["body_hash"]}, lead_id,
              ts=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"))
    return ev["to"]

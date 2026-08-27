# Facelift — an autonomous web agency, running on ₹0

> One command (`python main.py`) roams public data for businesses with no
> website or a broken one, researches them like a designer would, builds a
> personalized multi-page site with an AI coding agent, deploys to a global
> edge, and drafts compliance-gated outreach — stopping for human approval
> before anything leaves the building.

This repository is the **live showcase**. The interesting part is the
machine that produced these pages — documented below.

---

## Live showcase

Every concept below is a working first draft: real trade playbook, unique
design genome, performance-budgeted, multi-page.

| Concept | Trade | Design archetype | Notes |
|---|---|---|---|
| [Manohar Dairy & Restaurant](https://demolished-lab.github.io/facelift-sites/manohar-dairy-restaurant/) | dairy-restaurant | Swiss Precision Grid | order-composer → WhatsApp, menu page |
| [Bharat Cineplex](https://demolished-lab.github.io/facelift-sites/bharat-cineplex/) | cinema | Editorial Magazine | programme page, MovieTheater schema |
| [Shree Krishna Chaat](https://demolished-lab.github.io/facelift-sites/shree-krishna-chaat/) | street food | Swiss duotone | 91KB total site weight |
| [JHouse](https://demolished-lab.github.io/facelift-sites/jugaad-hostel/) | hostel | Neo-Brutalist Boutique | booking-inquiry composer |
| [Ravi Alpahar](https://demolished-lab.github.io/facelift-sites/ravi-alpahar/) | retail | — | first-site class |
| [56 Shops](https://demolished-lab.github.io/facelift-sites/1801726861/) | retail collective | — | first-site class |

---

## Architecture

```
                    ┌── L0 SOURCES ──────────────────────────────┐
                    │ Overpass (OSM) · Wayback CDX · Bing/DDG    │
                    │ field traces · CSV import                  │
                    └──────┬─────────────────────────────────────┘
                           ▼
   L1 MEASURE ── Lighthouse(local) · PSI(25k/d) · staleness signals
   │                 · ugly_score (deterministic, evidence-linked)
   ▼
   L2 TRIAGE ──── LLM small-business gate + deterministic rule veto
   ▼                 (rejected TCS, Infosys, Ranbaxy, embassies…)
   L3 RESEARCH ── field notes: design trends · tech-feature scans ·
   │                 discovery behavior · lead's multi-platform traces
   ▼
   L4 BUILD ───── Design DNA (anti-repeat) × TRADE PLAYBOOK ×
   │                 v0/Lovable design rules × Emil motion doctrine
   │                 → opencode coding agent → PLAN.md → dist/
   ▼
   L5 VERIFY ──── quality gate (structure+craft signals) →
   │                 vision-model art critique → revision loop
   ▼
   L6 DEPLOY ──── native Cloudflare REST (KV assets + module worker)
   │                 + GitHub Pages mirror (India-ISP proof, dual-CDN)
   ▼
   L7 PROVE ───── before/after report · rival spec-showdown matrix ·
   │                 audit receipts printed verbatim on-page
   ▼
   L8 CONTACT ─── waterfall: site-scrape → WHOIS → pattern+SMTP →
   │                 role-inbox → suppression store (forever)
   ▼
   L9 OUTREACH ── jurisdiction compliance engine (CAN-SPAM/DPDP §7a/GDPR)
                     → approval-hash gated send → reply tracking
```

## What's genuinely different here

**1. Grounding over generation.**
The builder never "knows" the business. It receives a Facts JSON extracted
from public listings and is contractually forbidden from inventing anything
— missing data becomes visible `TODO-OWNER:` slots placed exactly where
that content belongs. The owner sees their site asking to be completed.

**2. Design DNA — anti-repetition by construction.**
Eight art-direction archetypes (layout grammar, palette strategy, type
attitude, motion signature, motif family) selected by hash-seeded draw,
biased by trade, with a 12-entry memory that forbids recent repeats.
No two builds share a visual identity — verified across cinema, food,
hostel and retail verticals.

**3. Playbooks, not templates.**
Each trade carries a section architecture + one *signature interactive
component* (tap-to-order basket, room-selector booking composer,
appointment composer) implemented working end-to-end via `wa.me`/`mailto:`
composition — zero backend, zero keys, zero monthly cost.

**4. Critic-gated shipping.**
After build: deterministic quality gate (craft signals: stagger delays,
sticky scenes, z-layering, token systems), then a vision-model art
director reviews the *rendered screenshot* and files specific defects into
a revision brief. The agent fixes and re-ships. Taste via iteration.

**5. Dual-CDN delivery.**
Native Cloudflare REST deployer (KV asset bulk + module upload, stdlib
only — wrangler retired) plus a GitHub Pages mirror. Workers.dev is
ISP-blocked in several regions; the mirror guarantees reach.

**6. Compliance as code.**
Jurisdiction engine (CAN-SPAM identity block, DPDP §7(a) sourcing rule,
GDPR legitimate-interest records), permanent suppression store checked at
send-instant, approval tokens bound to message hashes. Outreach physically
cannot fire without owner approval + verified self-published contact.

## Cost engineering (verified across ~10 full runs)

| Resource | Tier | Spend |
|---|---|---|
| Discovery | Overpass API (keyless) | ₹0 |
| Audits | Local Lighthouse + PSI key (25k/d) | ₹0 |
| Research | Bing/DDG keyless + Gemini Flash (free tier) | ₹0 |
| Build agent | opencode + free-model router (Groq/Gemini/OR/NIM, 429-benched) | ₹0 |
| Imagery | Pollinations (keyless) → Gemini fallback | ₹0 |
| Hosting | CF Workers+KV free · GitHub Pages | ₹0 |
| **Total monthly** | | **≤ ₹2,000** (gateway fees on success only) |

Build receipts: 5.3–8.3 min per site · 91–135KB total weight (vs 11.4MB
originals) · LCP target <2s · CLS <0.1 · Lighthouse-audited.

## Failure handling (the unglamorous 60%)

Named failure classes with canned mitigations: PSI 429 → local-Lighthouse
fallback · Overpass 500/502 → sequential single-key probes + retry ·
LLM provider exhaustion → 4-slot benching router (Groq→Gemini→OR→NIM) ·
agent spawn flakes → retry w/ backoff · route-activation lag →
content-marker verification (status codes lie). Unknown failures become
structured ANON records — parked, never silently wrong.

## Compliance & ethics stance

- Contact data **only** from what a business published about itself
  (site, listings, brand social handles). No people-search, no breach
  data, no presence surveillance — allowlist enforced in code.
- Permanent opt-out honored at send-instant; takedown honored in minutes.
- Every concept page ships a visible takedown promise.
- Outreach blocked by default to strict-consent jurisdictions.

## Honest limitations

- Thin-fact leads produce intentionally smaller sites (grounding over
  padding) — quality tracks data quality.
- Vision-critic depends on free vision quota; degrades to deterministic
  gate when exhausted.
- Dynamic/L3+ builds (auth, DB) are architected but not yet field-proven.
- Single-operator scale today; multi-tenant is deliberately out of scope.

## Stack

Python 3.11 stdlib-first · SQLite (WAL) · Cloudflare Workers+KV REST ·
GitHub Pages · opencode CLI as build-worker · crawl4ai-class fetching ·
Playwright/Chrome headless capture · free-tier LLM router.

Influences/vendored doctrine: v0 & Lovable design constitutions,
Emil Kowalski's motion rules, ponytail (YAGNI ladder), caveman (token
discipline), prompt-master (brief engineering).

---

*Contact:* operator@example.com · every concept page carries a takedown
promise and this identity.

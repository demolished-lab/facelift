"""Stage registry and lead state machine (BLUEPRINT §5).

Scaffold scope: ordered stages, gate checks, and a fully offline demo walk
that proves wiring without touching any network. Real handlers plug into
HANDLERS as FR-1..FR-6 land; an empty handler parks the lead rather than
faking progress (PRD FR-8 spirit).
"""

from __future__ import annotations

import datetime as dt

from .models import ACTIVE_STAGES, Lead, Stage
from .store import Store

HANDLERS: dict[Stage, callable] = {}


def register(stage: Stage):
    def deco(fn):
        HANDLERS[stage] = fn
        return fn
    return deco


def next_stage(stage: Stage) -> Stage | None:
    try:
        i = ACTIVE_STAGES.index(stage)
    except ValueError:
        return None
    return ACTIVE_STAGES[i + 1] if i + 1 < len(ACTIVE_STAGES) else Stage.REPLIED


def advance(store: Store, lead: Lead) -> Lead:
    target = next_stage(lead.stage)
    if target is None:
        return lead
    handler = HANDLERS.get(target)
    if handler is None:
        store.log("park_no_handler", {"target": target.value}, lead.id,
                  ts=_now())
        lead.stage = Stage.PARKED
        store.upsert_lead(lead)
        return lead
    lead = handler(store, lead)
    store.upsert_lead(lead)
    return lead


def demo_walk(store: Store) -> Lead:
    lead = Lead(
        id="demo-001",
        domain="rani-tiffin-house.example",
        name="Rani Tiffin House",
        market_profile="in",
        source="scaffold-demo",
        source_url="https://rani-tiffin-house.example",
        ugly_score=78,
        signals=[
            {"signal": "psi_mobile_perf", "value": 31},
            {"signal": "no_viewport_meta", "value": True},
            {"signal": "footer_year", "value": 2014},
        ],
    )
    store.upsert_lead(lead)
    store.log("demo_created", {"score": lead.ugly_score}, lead.id, ts=_now())
    while lead.stage not in (Stage.PARKED, Stage.REPLIED, Stage.WON):
        lead = advance(store, lead)
    return lead


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

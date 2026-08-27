"""Data shapes for every pipeline artifact (PRD §7).

Single source of truth for field names across stages and the store.
Scaffold scope: Lead lifecycle plus suppression records; Audit/Rebuild/
Message/Deal arrive as dicts until their FRs are implemented.
"""

from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass, field
from enum import StrEnum


class Stage(StrEnum):
    DISCOVERED = "discovered"
    SCORED = "scored"
    AUDITED = "audited"
    BUILT = "built"
    REBUILT = "rebuilt"
    CONTACTS_FOUND = "contacts_found"
    DRAFTED = "drafted"
    SENT = "sent"
    REPLIED = "replied"
    WON = "won"
    PARKED = "parked"
    DEAD = "dead"
    SUPPRESSED = "suppressed"


ACTIVE_STAGES = [
    Stage.DISCOVERED,
    Stage.SCORED,
    Stage.AUDITED,
    Stage.REBUILT,
    Stage.CONTACTS_FOUND,
    Stage.DRAFTED,
    Stage.SENT,
    Stage.REPLIED,
]

TERMINAL_STAGES = [Stage.WON, Stage.PARKED, Stage.DEAD, Stage.SUPPRESSED]


@dataclass
class Lead:
    id: str
    domain: str
    name: str
    market_profile: str = "in"
    source: str = "manual"
    source_url: str = ""
    ugly_score: int = 0
    signals: list[dict] = field(default_factory=list)
    stage: Stage = Stage.DISCOVERED

    def to_row(self) -> dict:
        d = dataclasses.asdict(self)
        d["stage"] = self.stage.value
        return d

    @classmethod
    def from_row(cls, row: dict) -> "Lead":
        row = dict(row)
        row["stage"] = Stage(row["stage"])
        if isinstance(row.get("signals"), str):
            row["signals"] = json.loads(row["signals"])
        return cls(**row)


@dataclass
class Suppression:
    value: str
    reason: str
    added_at: str

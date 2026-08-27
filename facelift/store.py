"""SQLite store (BLUEPRINT §2 cross layer).

WAL mode, schema-as-code. Scaffold tables: leads, suppressions, events.
Every write is idempotent on primary keys so pipeline re-runs are safe.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from .models import Lead

DEFAULT_DB = Path("data") / "facelift.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS leads (
    id TEXT PRIMARY KEY,
    domain TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    market_profile TEXT NOT NULL DEFAULT 'in',
    source TEXT NOT NULL,
    source_url TEXT NOT NULL DEFAULT '',
    ugly_score INTEGER NOT NULL DEFAULT 0,
    signals TEXT NOT NULL DEFAULT '[]',
    stage TEXT NOT NULL DEFAULT 'discovered'
);
CREATE TABLE IF NOT EXISTS suppressions (
    value TEXT PRIMARY KEY,
    reason TEXT NOT NULL,
    added_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    value TEXT NOT NULL,
    person TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL,
    confidence INTEGER NOT NULL DEFAULT 50,
    verified INTEGER NOT NULL DEFAULT 0,
    UNIQUE(lead_id, kind, value)
);
CREATE TABLE IF NOT EXISTS events (
    ts TEXT NOT NULL,
    lead_id TEXT,
    kind TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT '{}'
);
"""


class Store:
    def __init__(self, path: Path | str | None = DEFAULT_DB):
        path = Path(path) if path is not None else DEFAULT_DB
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.executescript(SCHEMA)

    def upsert_lead(self, lead: Lead) -> None:
        row = lead.to_row()
        row["signals"] = json.dumps(row["signals"])
        cols = ",".join(row)
        vals = ",".join("?" * len(row))
        self.conn.execute(
            f"INSERT INTO leads ({cols}) VALUES ({vals}) "
            "ON CONFLICT(id) DO UPDATE SET " + ",".join(
                f"{c}=excluded.{c}" for c in row if c != "id"
            ),
            tuple(row.values()),
        )
        self.conn.commit()

    def try_stage_transition(self, lead_id: str, new_stage: str, old_stage: str) -> bool:
        """Atomic check-and-set: only transitions if lead is still at old_stage.

        Returns True if transition succeeded (lead was claimed), False if
        another agent already claimed it (stage no longer matches old_stage).
        """
        cur = self.conn.execute(
            "SELECT stage FROM leads WHERE id=?",
            (lead_id,),
        ).fetchone()["stage"]
        if cur != old_stage:
            return False
        self.conn.execute(
            "UPDATE leads SET stage=? WHERE id=? AND stage=?",
            (new_stage, lead_id, old_stage),
        )
        if self.conn.total_changes == 0:
            # another transaction committed first between SELECT and UPDATE
            # re-read current stage and retry once
            cur2 = self.conn.execute(
                "SELECT stage FROM leads WHERE id=?",
                (lead_id,),
            ).fetchone()["stage"]
            if cur2 != old_stage:
                return False
            self.conn.execute(
                "UPDATE leads SET stage=? WHERE id=? AND stage=?",
                (new_stage, lead_id, old_stage),
            )
        self.conn.commit()
        # verify it actually changed
        final = self.conn.execute(
            "SELECT stage FROM leads WHERE id=?",
            (lead_id,),
        ).fetchone()["stage"]
        return final == new_stage

    def get_lead(self, lead_id: str) -> Lead | None:
        r = self.conn.execute(
            "SELECT * FROM leads WHERE id=?", (lead_id,)
        ).fetchone()
        return Lead.from_row(dict(r)) if r else None

    def list_leads(self) -> list[Lead]:
        rs = self.conn.execute("SELECT * FROM leads ORDER BY ugly_score DESC")
        return [Lead.from_row(dict(r)) for r in rs]

    def stage_counts(self) -> dict[str, int]:
        rs = self.conn.execute(
            "SELECT stage, COUNT(*) AS n FROM leads GROUP BY stage"
        )
        return {r["stage"]: r["n"] for r in rs}

    def is_suppressed(self, value: str) -> bool:
        return (
            self.conn.execute(
                "SELECT 1 FROM suppressions WHERE value=?", (value,)
            ).fetchone()
            is not None
        )

    def suppress(self, value: str, reason: str, added_at: str) -> None:
        self.conn.execute(
            "INSERT OR IGNORE INTO suppressions VALUES (?,?,?)",
            (value, reason, added_at),
        )
        self.conn.commit()

    def log(self, kind: str, detail: dict[str, Any], lead_id: str | None = None,
            ts: str = "") -> None:
        self.conn.execute(
            "INSERT INTO events VALUES (?,?,?,?)",
            (ts, lead_id, kind, json.dumps(detail)),
        )
        self.conn.commit()

    def last_event_detail(self, lead_id: str, kind: str) -> dict | None:
        r = self.conn.execute(
            "SELECT detail FROM events WHERE lead_id=? AND kind=? "
            "ORDER BY rowid DESC LIMIT 1",
            (lead_id, kind),
        ).fetchone()
        return json.loads(r["detail"]) if r else None

    def add_contact(self, lead_id: str, kind: str, value: str, source: str,
                    confidence: int, verified: bool, person: str = "") -> None:
        self.conn.execute(
            "INSERT OR IGNORE INTO contacts "
            "(lead_id,kind,value,person,source,confidence,verified) "
            "VALUES (?,?,?,?,?,?,?)",
            (lead_id, kind, value.strip(), person, source, confidence,
             int(verified)),
        )
        self.conn.commit()

    def list_contacts(self, lead_id: str) -> list[dict]:
        rs = self.conn.execute(
            "SELECT * FROM contacts WHERE lead_id=? ORDER BY confidence DESC",
            (lead_id,),
        )
        return [dict(r) for r in rs]

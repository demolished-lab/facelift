"""Multi-agent orchestration — parallel workers with synced data.

Every worker shares the same SQLite WAL store + filesystem; the
orchestrator spawns role-specialized agents that pull from a queue,
execute independently, and write back atomically. No lead is built
twice — stage transitions are the lock.
"""

from __future__ import annotations

import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]


class Role(str, Enum):
    RESEARCHER = "researcher"
    BUILDER = "builder"
    REVIEWER = "reviewer"
    HUNTER = "hunter"  # contacts + draft


@dataclass
class Task:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    role: Role = Role.BUILDER
    lead_id: str = ""
    status: str = "pending"  # pending | running | done | failed
    result: dict = field(default_factory=dict)
    started: float = 0
    finished: float = 0

    @property
    def elapsed(self) -> float:
        end = self.finished or time.monotonic()
        return round(end - self.started, 1) if self.started else 0


# role -> callable(lead_id) -> dict
_REGISTRY: dict[Role, Callable[[str], dict]] = {}


def register(role: Role):
    def deco(fn: Callable[[str], dict]):
        _REGISTRY[role] = fn
        return fn
    return deco


def _run_one(task: Task) -> Task:
    task.status = "running"
    task.started = time.monotonic()
    fn = _REGISTRY.get(task.role)
    if not fn:
        task.status = "failed"
        task.result = {"error": f"no handler for {task.role}"}
        task.finished = time.monotonic()
        return task
    try:
        task.result = fn(task.lead_id)
        task.status = "done"
    except Exception as ex:  # noqa: BLE001 - per-task isolation
        task.status = "failed"
        task.result = {"error": str(ex)[:200]}
    task.finished = time.monotonic()
    return task


class Pool:
    """Thread pool that spawns role-specialized agents in parallel.

    Example:
        pool = Pool(max_workers=3)
        tasks = pool.spawn(Role.BUILDER, ["osm-1", "osm-2", "osm-3"])
        # tasks is List[Task] with status/result filled when done
    """

    def __init__(self, max_workers: int = 3):
        self.max_workers = max_workers

    def spawn(self, role: Role, lead_ids: list[str]) -> list[Task]:
        tasks = [Task(role=role, lead_id=lid) for lid in lead_ids]
        with ThreadPoolExecutor(max_workers=self.max_workers) as ex:
            futs = {ex.submit(_run_one, t): t for t in tasks}
            done: list[Task] = []
            for fut in as_completed(futs):
                done.append(fut.result())
        # preserve input order for caller convenience
        order = {t.lead_id: i for i, t in enumerate(tasks)}
        done.sort(key=lambda t: order.get(t.lead_id, 99))
        return done

    def spawn_mixed(self, pairs: list[tuple[Role, str]]) -> list[Task]:
        """Heterogeneous spawn: [(role, lead_id), ...] in parallel."""
        tasks = [Task(role=r, lead_id=lid) for r, lid in pairs]
        with ThreadPoolExecutor(max_workers=self.max_workers) as ex:
            futs = {ex.submit(_run_one, t): t for t in tasks}
            done = [f.result() for f in as_completed(futs)]
        return done


# ── default role handlers (lightweight wrappers around existing modules) ──

@register(Role.RESEARCHER)
def _researcher(lead_id: str) -> dict:
    from facelift.store import Store
    from facelift import research
    from facelift.models import Stage

    s = Store(ROOT / "data" / "facelift.db")
    lead = s.get_lead(lead_id)
    if not lead:
        return {"error": "lead not found"}
    # atomic CAS: SCORED → RESEARCHED, fail if another agent already claimed
    if not s.try_stage_transition(lead_id, Stage.RESEARCHED.value, Stage.SCORED.value):
        return {"error": "lead already claimed by another agent"}
    md = research.research_lead(
        lead.name, research.detect_vertical_key(
            s.last_event_detail(lead_id, "extracted") or {}),
        lead.market_profile)
    return {"chars": len(md), "lead": lead.name}


@register(Role.HUNTER)
def _hunter(lead_id: str) -> dict:
    import subprocess
    import sys

    r = subprocess.run(
        [sys.executable, "-m", "facelift", "contacts", lead_id, "--commit"],
        cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=120)
    return {"rc": r.returncode, "tail": (r.stdout or r.stderr)[-200:]}


@register(Role.BUILDER)
def _builder(lead_id: str) -> dict:
    import subprocess
    import sys
    from facelift.store import Store
    from facelift.models import Stage

    s = Store(ROOT / "data" / "facelift.db")
    lead = s.get_lead(lead_id)
    if not lead:
        return {"error": "lead not found"}
    # atomic CAS: SCORED → BUILT, fail if another agent already claimed
    if not s.try_stage_transition(lead_id, Stage.BUILT.value, Stage.SCORED.value):
        return {"error": "lead already claimed by another agent"}
    r = subprocess.run(
        [sys.executable, "-m", "facelift", "rebuild", lead_id, "--commit"],
        cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=900)
    return {"rc": r.returncode, "tail": (r.stdout or r.stderr)[-300:]}


@register(Role.REVIEWER)
def _reviewer(lead_id: str) -> dict:
    from facelift.store import Store
    from facelift import builder_agent
    from facelift.models import Stage

    s = Store(ROOT / "data" / "facelift.db")
    lead = s.get_lead(lead_id)
    if not lead:
        return {"error": "lead not found"}
    # atomic CAS: SCORED → REVIEWED, fail if another agent already claimed
    if not s.try_stage_transition(lead_id, Stage.REVIEWED.value, Stage.SCORED.value):
        return {"error": "lead already claimed by another agent"}
    ev = s.last_event_detail(lead_id, "rebuilt") or {}
    worker = ev.get("worker", "")
    if not worker:
        return {"error": "not yet built"}
    dist = ROOT / "builds" / worker / "dist"
    fails = builder_agent.quality_check(dist)
    return {"fails": fails, "pass": not fails}

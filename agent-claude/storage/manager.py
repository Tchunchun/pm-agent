"""
StorageManager — atomic JSON-backed persistence for all Tier 1 records.

Files:
  data/requests.json        — list[CustomerRequest]
  data/day_plans.json       — list[DayPlan]
  data/insights.json        — list[StrategicInsight]
  data/workrooms.json       — list[WorkroomSession]
  data/workroom_msgs.json   — list[dict]  (messages tagged by workroom_id)
  data/custom_agents.json   — list[CustomAgent]
"""

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from models.customer_request import CustomerRequest
from models.day_plan import DayPlan
from models.strategic_insight import StrategicInsight
from models.workroom import WorkroomSession, CustomAgent, Decision, GeneratedOutput
from config import DATA_DIR


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_write(path: Path, data: list[dict]) -> None:
    """Write JSON to a temp file then atomically rename to target."""
    dir_ = path.parent
    fd, tmp_path = tempfile.mkstemp(dir=dir_, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _load_json(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


class StorageManager:
    """Single access point for all persistent storage."""

    REQUESTS_FILE = DATA_DIR / "requests.json"
    DAY_PLANS_FILE = DATA_DIR / "day_plans.json"
    INSIGHTS_FILE = DATA_DIR / "insights.json"

    # ------------------------------------------------------------------ #
    # CustomerRequest                                                      #
    # ------------------------------------------------------------------ #

    def save_request(self, req: CustomerRequest) -> CustomerRequest:
        records = _load_json(self.REQUESTS_FILE)
        updated = False
        for i, r in enumerate(records):
            if r["id"] == req.id:
                records[i] = req.model_dump()
                updated = True
                break
        if not updated:
            records.append(req.model_dump())
        _atomic_write(self.REQUESTS_FILE, records)
        return req

    def get_request(self, request_id: str) -> Optional[CustomerRequest]:
        for r in _load_json(self.REQUESTS_FILE):
            if r["id"] == request_id and not r.get("deleted", False):
                return CustomerRequest(**r)
        return None

    def list_requests(
        self,
        *,
        priority: Optional[list[str]] = None,
        status: Optional[list[str]] = None,
        stale_days: Optional[int] = None,
        include_deleted: bool = False,
    ) -> list[CustomerRequest]:
        results = []
        for r in _load_json(self.REQUESTS_FILE):
            if not include_deleted and r.get("deleted", False):
                continue
            req = CustomerRequest(**r)
            if priority and req.priority not in priority:
                continue
            if status and req.status not in status:
                continue
            if stale_days is not None:
                # stale = last_surfaced_at is None OR older than stale_days
                if req.last_surfaced_at is not None:
                    last = datetime.fromisoformat(req.last_surfaced_at)
                    now = datetime.now(timezone.utc)
                    age = (now - last).days
                    if age < stale_days:
                        continue
            results.append(req)
        return results

    def soft_delete_request(self, request_id: str) -> bool:
        records = _load_json(self.REQUESTS_FILE)
        for r in records:
            if r["id"] == request_id:
                r["deleted"] = True
                r["updated_at"] = _now()
                _atomic_write(self.REQUESTS_FILE, records)
                return True
        return False

    def link_request_to_insight(self, request_id: str, insight_id: str) -> None:
        req = self.get_request(request_id)
        if req and insight_id not in req.linked_insight_ids:
            req.linked_insight_ids.append(insight_id)
            self.save_request(req)

    def mark_request_surfaced(self, request_id: str) -> None:
        req = self.get_request(request_id)
        if req:
            req.mark_surfaced()
            self.save_request(req)

    # ------------------------------------------------------------------ #
    # DayPlan                                                             #
    # ------------------------------------------------------------------ #

    def save_day_plan(self, plan: DayPlan) -> DayPlan:
        records = _load_json(self.DAY_PLANS_FILE)
        updated = False
        for i, r in enumerate(records):
            if r["id"] == plan.id:
                records[i] = plan.model_dump()
                updated = True
                break
        if not updated:
            records.append(plan.model_dump())
        _atomic_write(self.DAY_PLANS_FILE, records)
        # After saving, mark all linked requests as surfaced and update insight flags
        self._update_feedback_links(plan)
        return plan

    def _update_feedback_links(self, plan: DayPlan) -> None:
        """Update request surface counts and insight in_day_plan flags."""
        surfaced_request_ids: set[str] = set()
        for item in plan.focus_items:
            for rid in item.linked_request_ids:
                surfaced_request_ids.add(rid)

        for rid in surfaced_request_ids:
            self.mark_request_surfaced(rid)

        # Mark insights whose recommended actions are in this plan
        insight_ids_in_plan: set[str] = set()
        for item in plan.focus_items:
            if item.source_type == "insight" and item.source_ref:
                insight_ids_in_plan.add(item.source_ref)

        for iid in insight_ids_in_plan:
            ins = self.get_insight(iid)
            if ins and not ins.in_day_plan:
                ins.in_day_plan = True
                self.save_insight(ins)

    def get_day_plan(self, date: str) -> Optional[DayPlan]:
        """Return the most recent DayPlan for a given YYYY-MM-DD date."""
        matches = [
            r for r in _load_json(self.DAY_PLANS_FILE) if r.get("date") == date
        ]
        if not matches:
            return None
        # Return latest
        matches.sort(key=lambda r: r.get("generated_at", ""), reverse=True)
        return DayPlan(**matches[0])

    def list_day_plans(self, limit: int = 10) -> list[DayPlan]:
        records = _load_json(self.DAY_PLANS_FILE)
        records.sort(key=lambda r: r.get("date", ""), reverse=True)
        return [DayPlan(**r) for r in records[:limit]]

    def update_focus_item_done(self, plan_date: str, rank: int, done: bool) -> bool:
        records = _load_json(self.DAY_PLANS_FILE)
        # Find most recent plan for date
        date_records = [r for r in records if r.get("date") == plan_date]
        if not date_records:
            return False
        date_records.sort(key=lambda r: r.get("generated_at", ""), reverse=True)
        target_id = date_records[0]["id"]
        for r in records:
            if r["id"] == target_id:
                for item in r.get("focus_items", []):
                    if item.get("rank") == rank:
                        item["done"] = done
                        break
                _atomic_write(self.DAY_PLANS_FILE, records)
                return True
        return False

    # ------------------------------------------------------------------ #
    # StrategicInsight                                                    #
    # ------------------------------------------------------------------ #

    def save_insight(self, insight: StrategicInsight) -> StrategicInsight:
        records = _load_json(self.INSIGHTS_FILE)
        updated = False
        for i, r in enumerate(records):
            if r["id"] == insight.id:
                records[i] = insight.model_dump()
                updated = True
                break
        if not updated:
            records.append(insight.model_dump())
        _atomic_write(self.INSIGHTS_FILE, records)
        # Bidirectional link: update all referenced requests
        for rid in insight.linked_request_ids:
            self.link_request_to_insight(rid, insight.id)
        return insight

    def get_insight(self, insight_id: str) -> Optional[StrategicInsight]:
        for r in _load_json(self.INSIGHTS_FILE):
            if r["id"] == insight_id:
                return StrategicInsight(**r)
        return None

    def list_insights(
        self,
        *,
        insight_type: Optional[list[str]] = None,
        confidence: Optional[list[str]] = None,
        recent_days: Optional[int] = None,
    ) -> list[StrategicInsight]:
        results = []
        for r in _load_json(self.INSIGHTS_FILE):
            ins = StrategicInsight(**r)
            if insight_type and ins.insight_type not in insight_type:
                continue
            if confidence and ins.confidence not in confidence:
                continue
            if recent_days is not None:
                created = datetime.fromisoformat(ins.created_at)
                now = datetime.now(timezone.utc)
                if (now - created).days > recent_days:
                    continue
            results.append(ins)
        results.sort(key=lambda x: x.created_at, reverse=True)
        return results

    # ------------------------------------------------------------------ #
    # Conversation history (legacy "general" chat)                       #
    # ------------------------------------------------------------------ #

    CONVO_FILE = DATA_DIR / "conversation.json"

    def save_conversation(self, messages: list[dict]) -> None:
        _atomic_write(self.CONVO_FILE, messages)

    def load_conversation(self) -> list[dict]:
        return _load_json(self.CONVO_FILE)

    # ------------------------------------------------------------------ #
    # Workroom sessions                                                   #
    # ------------------------------------------------------------------ #

    WORKROOMS_FILE = DATA_DIR / "workrooms.json"
    WORKROOM_MSGS_FILE = DATA_DIR / "workroom_msgs.json"
    CUSTOM_AGENTS_FILE = DATA_DIR / "custom_agents.json"

    def save_workroom(self, workroom: WorkroomSession) -> WorkroomSession:
        records = _load_json(self.WORKROOMS_FILE)
        updated = False
        for i, r in enumerate(records):
            if r["id"] == workroom.id:
                records[i] = workroom.model_dump()
                updated = True
                break
        if not updated:
            records.append(workroom.model_dump())
        _atomic_write(self.WORKROOMS_FILE, records)
        return workroom

    def get_workroom(self, workroom_id: str) -> Optional[WorkroomSession]:
        for r in _load_json(self.WORKROOMS_FILE):
            if r["id"] == workroom_id:
                return WorkroomSession(**r)
        return None

    def list_workrooms(self, include_archived: bool = False) -> list[WorkroomSession]:
        results = []
        for r in _load_json(self.WORKROOMS_FILE):
            ws = WorkroomSession(**r)
            if not include_archived and ws.status == "archived":
                continue
            results.append(ws)
        results.sort(key=lambda w: w.created_at, reverse=True)
        return results

    def archive_workroom(self, workroom_id: str) -> bool:
        ws = self.get_workroom(workroom_id)
        if ws:
            ws.status = "archived"
            self.save_workroom(ws)
            return True
        return False

    def add_workroom_decision(self, workroom_id: str, decision: Decision) -> bool:
        ws = self.get_workroom(workroom_id)
        if ws:
            ws.decisions.append(decision)
            self.save_workroom(ws)
            return True
        return False

    def add_workroom_output(self, workroom_id: str, output: GeneratedOutput) -> bool:
        ws = self.get_workroom(workroom_id)
        if ws:
            ws.generated_outputs.append(output)
            self.save_workroom(ws)
            return True
        return False

    # ------------------------------------------------------------------ #
    # Per-workroom messages                                               #
    # ------------------------------------------------------------------ #

    def save_workroom_messages(self, workroom_id: str, messages: list[dict]) -> None:
        """Replace all messages for a workroom."""
        all_msgs = _load_json(self.WORKROOM_MSGS_FILE)
        # Remove old messages for this workroom
        all_msgs = [m for m in all_msgs if m.get("workroom_id") != workroom_id]
        # Add new ones with workroom_id tag
        for m in messages:
            tagged = dict(m)
            tagged["workroom_id"] = workroom_id
            all_msgs.append(tagged)
        _atomic_write(self.WORKROOM_MSGS_FILE, all_msgs)

    def load_workroom_messages(self, workroom_id: str) -> list[dict]:
        all_msgs = _load_json(self.WORKROOM_MSGS_FILE)
        return [m for m in all_msgs if m.get("workroom_id") == workroom_id]

    # ------------------------------------------------------------------ #
    # Custom agents                                                       #
    # ------------------------------------------------------------------ #

    def save_custom_agent(self, agent: CustomAgent) -> CustomAgent:
        records = _load_json(self.CUSTOM_AGENTS_FILE)
        updated = False
        for i, r in enumerate(records):
            if r["id"] == agent.id:
                records[i] = agent.model_dump()
                updated = True
                break
        if not updated:
            records.append(agent.model_dump())
        _atomic_write(self.CUSTOM_AGENTS_FILE, records)
        return agent

    def list_custom_agents(self) -> list[CustomAgent]:
        return [CustomAgent(**r) for r in _load_json(self.CUSTOM_AGENTS_FILE)]

    def delete_custom_agent(self, agent_id: str) -> bool:
        records = _load_json(self.CUSTOM_AGENTS_FILE)
        new_records = [r for r in records if r["id"] != agent_id]
        if len(new_records) < len(records):
            _atomic_write(self.CUSTOM_AGENTS_FILE, new_records)
            return True
        return False

    def ensure_default_agents(self) -> None:
        """Seed default agents and prune stale defaults on every startup.

        - Adds any default agent whose key is not yet in storage.
        - Removes any stored record that is marked ``is_default=True`` but
          whose key no longer appears in the current ``ALL_DEFAULT_AGENTS``
          list (i.e. it was removed from the codebase).
        - User-created agents (``is_default=False``) are never touched.
        - Existing default agents whose prompts were edited by the user are
          left untouched (only missing keys are added).
        """
        from agents.default_agents import ALL_DEFAULT_AGENTS  # local import avoids circular deps

        default_keys = {a.key for a in ALL_DEFAULT_AGENTS}
        records = _load_json(self.CUSTOM_AGENTS_FILE)
        existing_keys = {r["key"] for r in records}
        changed = False

        # --- prune stale defaults ---
        before_len = len(records)
        records = [
            r for r in records
            if not (r.get("is_default") and r["key"] not in default_keys)
        ]
        if len(records) < before_len:
            changed = True

        # --- sync categories for existing defaults (category is not user-editable) ---
        default_by_key = {a.key: a for a in ALL_DEFAULT_AGENTS}
        for r in records:
            if r.get("is_default") and r["key"] in default_by_key:
                new_cat = default_by_key[r["key"]].category
                if r.get("category") != new_cat:
                    r["category"] = new_cat
                    changed = True

        # --- seed missing defaults ---
        existing_keys = {r["key"] for r in records}
        for agent in ALL_DEFAULT_AGENTS:
            if agent.key not in existing_keys:
                records.append(agent.model_dump())
                changed = True

        if changed:
            _atomic_write(self.CUSTOM_AGENTS_FILE, records)

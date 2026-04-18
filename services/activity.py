"""
Activity feed — per-user event log. In-memory; swap for a real append-only
store later. Each event is small and human-readable so the dashboard can
render it directly.
"""
from __future__ import annotations

import threading
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional


_KIND_LABELS = {
    "fund_distribution":  "Fund distribution paid",
    "fund_yield_tick":    "Yield update",
    "doc_uploaded":       "Document uploaded",
    "doc_extracted":      "Extraction complete",
    "wc_drawn":           "Working capital drawn",
    "wc_repaid":          "Working capital repaid",
    "deal_stage_changed": "Deal stage advanced",
    "account_created":    "Account created",
    "login":              "Sign-in",
}


class ActivityFeed:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._events: dict[str, list[dict]] = {}  # user_id -> events
        self._seed()

    def _seed(self) -> None:
        # Seed for the demo client so the dashboard isn't empty on first login
        now = datetime.now(timezone.utc)
        client_seed_user = "*demo*"
        self._events[client_seed_user] = [
            self._mk("account_created", "Account opened", at=now - timedelta(days=92), meta={"client_id": "demo"}),
            self._mk("doc_uploaded", "T-12 operating statement uploaded", at=now - timedelta(days=78), meta={"deal_id": "JT-2025-42"}),
            self._mk("doc_extracted", "Rent roll extracted (NOI $1.87M)", at=now - timedelta(days=78), meta={"deal_id": "JT-2025-42"}),
            self._mk("deal_stage_changed", "Deal advanced to book building", at=now - timedelta(days=54), meta={"deal_id": "JT-2025-42"}),
            self._mk("fund_distribution", "Distribution paid: $9,800", at=now - timedelta(days=30), meta={"amount_usd": 9800, "kind": "yield"}),
            self._mk("fund_distribution", "Distribution paid: $9,600", at=now - timedelta(days=60), meta={"amount_usd": 9600, "kind": "yield"}),
        ]

    @staticmethod
    def _mk(kind: str, text: str, *, at: Optional[datetime] = None, meta: Optional[dict] = None) -> dict:
        return {
            "id": uuid.uuid4().hex[:12],
            "kind": kind,
            "kind_label": _KIND_LABELS.get(kind, kind),
            "text": text,
            "meta": meta or {},
            "at": (at or datetime.now(timezone.utc)).isoformat(),
        }

    # ---------- writes ----------

    def log(self, user_id: str, kind: str, text: str, *, meta: Optional[dict] = None) -> dict:
        ev = self._mk(kind, text, meta=meta)
        with self._lock:
            self._events.setdefault(user_id, []).insert(0, ev)
            self._events[user_id] = self._events[user_id][:500]
        return ev

    # ---------- reads ----------

    def for_user(self, user_id: str, *, role: str = "client", client_id: Optional[str] = None, limit: int = 25) -> list[dict]:
        with self._lock:
            own = list(self._events.get(user_id, []))
            # Clients also see the demo-seeded events on first run so the dashboard isn't empty
            if role == "client" and not own and client_id == "demo":
                own = list(self._events.get("*demo*", []))
            return own[:limit]

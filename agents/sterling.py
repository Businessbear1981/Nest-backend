"""
Sterling — NEST's investor relations agent. Matches deals to the investor
book, drafts periodic investor updates, and tracks book-building state.
"""
from __future__ import annotations

import threading
from datetime import datetime
from typing import Optional

from services.jimmy_lee import JIMMY_LEE_SYSTEM_PROMPT, count_words, estimate_read_time
from agents._claude import complete, ClaudeUnavailable


class SterlingAgent:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._investors: dict[str, dict] = {}
        self._book: dict[str, dict] = {}  # deal_id -> { allocations, indications }
        self._seed()

    def _seed(self) -> None:
        self._investors = {
            "inv_001": {
                "id": "inv_001",
                "name": "Redwood Family Office",
                "min_ticket": 1_000_000,
                "max_ticket": 10_000_000,
                "prefers": {"asset_classes": ["senior_housing", "industrial"], "yield_floor_pct": 9.0},
                "existing": True,
            },
            "inv_002": {
                "id": "inv_002",
                "name": "Cascadia Endowment",
                "min_ticket": 5_000_000,
                "max_ticket": 25_000_000,
                "prefers": {"asset_classes": ["infrastructure", "industrial"], "yield_floor_pct": 8.0},
                "existing": True,
            },
            "inv_003": {
                "id": "inv_003",
                "name": "Mariner Credit Partners",
                "min_ticket": 2_000_000,
                "max_ticket": 15_000_000,
                "prefers": {"asset_classes": ["senior_housing"], "yield_floor_pct": 10.0},
                "existing": False,
            },
        }

    # ---------- matching ----------

    def match_investors(self, deal: dict) -> list[dict]:
        size = float(deal.get("size_usd", 0))
        asset = str(deal.get("asset_class", "")).lower()
        projected_yield = float(deal.get("projected_yield_pct", 0))
        ranked: list[dict] = []
        with self._lock:
            for inv in self._investors.values():
                score, reasons = 0, []
                prefs = inv.get("prefers", {})
                if asset and asset in prefs.get("asset_classes", []):
                    score += 40
                    reasons.append(f"asset class match ({asset})")
                if projected_yield >= prefs.get("yield_floor_pct", 0):
                    score += 30
                    reasons.append(f"yield {projected_yield}% clears floor {prefs.get('yield_floor_pct')}%")
                if inv["min_ticket"] <= size <= inv["max_ticket"] * 5:
                    score += 20
                    reasons.append("ticket sizing workable")
                if inv.get("existing"):
                    score += 10
                    reasons.append("existing relationship — allocation priority")
                ranked.append({
                    "investor_id": inv["id"],
                    "name": inv["name"],
                    "score": score,
                    "rationale": "; ".join(reasons) or "no strong match signals",
                    "existing": inv.get("existing", False),
                })
        ranked.sort(key=lambda r: r["score"], reverse=True)
        return ranked

    # ---------- investor updates ----------

    def generate_investor_update(self, investor_id: str, deal_id: str, deal: Optional[dict] = None) -> dict:
        inv = self._investors.get(investor_id)
        if inv is None:
            raise KeyError(investor_id)
        deal = deal or {"deal_id": deal_id}
        user_prompt = (
            "Personalized investor update. Brief. Cover: deal progress since last "
            "touch, current yield vs. target, Vector monitoring status (green/amber/red), "
            "and the next expected event with a date. Address the investor by name.\n\n"
            f"Investor: {inv['name']} (existing: {inv['existing']})\n"
            f"Deal: {deal}\n"
        )
        try:
            body = complete(JIMMY_LEE_SYSTEM_PROMPT, user_prompt, max_tokens=600)
            error = None
        except ClaudeUnavailable as e:
            body = f"_[generator offline: {e}]_"
            error = str(e)
        return {
            "investor_id": investor_id,
            "deal_id": deal_id,
            "content": body,
            "word_count": count_words(body),
            "estimated_read_time": estimate_read_time(body),
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "error": error,
        }

    # ---------- book building ----------

    def add_indication(self, deal_id: str, investor_id: str, amount: float) -> dict:
        with self._lock:
            book = self._book.setdefault(deal_id, {"indications": [], "allocations": {}})
            book["indications"].append({
                "investor_id": investor_id,
                "amount": float(amount),
                "received_at": datetime.utcnow().isoformat() + "Z",
            })
            return self._book_state(deal_id)

    def manage_book_building(self, deal_id: str, target_raise: Optional[float] = None) -> dict:
        with self._lock:
            book = self._book.setdefault(deal_id, {"indications": [], "allocations": {}})
            indications = sorted(
                book["indications"],
                key=lambda i: (
                    0 if self._investors.get(i["investor_id"], {}).get("existing") else 1,
                    -i["amount"],
                ),
            )
            remaining = float(target_raise or 0) or sum(i["amount"] for i in indications)
            allocations: dict[str, float] = {}
            for ind in indications:
                if remaining <= 0:
                    allocations[ind["investor_id"]] = 0.0
                    continue
                take = min(ind["amount"], remaining)
                allocations[ind["investor_id"]] = allocations.get(ind["investor_id"], 0.0) + take
                remaining -= take
            book["allocations"] = allocations
            return self._book_state(deal_id, target_raise=target_raise, remaining=remaining)

    def _book_state(self, deal_id: str, *, target_raise: Optional[float] = None, remaining: Optional[float] = None) -> dict:
        book = self._book.get(deal_id, {"indications": [], "allocations": {}})
        total_indicated = sum(i["amount"] for i in book["indications"])
        total_allocated = sum(book["allocations"].values())
        return {
            "deal_id": deal_id,
            "target_raise": target_raise,
            "total_indicated": total_indicated,
            "total_allocated": total_allocated,
            "remaining": remaining,
            "indications": book["indications"],
            "allocations": book["allocations"],
        }

    def investors(self) -> list[dict]:
        with self._lock:
            return list(self._investors.values())

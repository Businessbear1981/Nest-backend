"""
Deals registry — minimal in-memory seed that feeds the public Active Deals
preview and the marketing studio. Swap for persistence when a DB lands.
"""
from __future__ import annotations

import threading
from datetime import date, timedelta


_SEED = [
    {
        "id": "JT-2025-42",
        "name": "Jacaranda Trace",
        "blind_name": "Sunbelt Senior Living Portfolio",
        "asset_class": "senior_housing",
        "location": "Tampa, FL",
        "size_usd": 42_000_000,
        "projected_yield_pct": 11.2,
        "stage": "book_building",
        "target_close": (date.today() + timedelta(days=38)).isoformat(),
        "summary": "Three-property seniors housing portfolio. A/B tranche, LC endgame.",
    },
    {
        "id": "BW-2025-18",
        "name": "Bellwether Cold Storage",
        "blind_name": "PNW Industrial Cold Chain",
        "asset_class": "industrial",
        "location": "Tacoma, WA",
        "size_usd": 18_500_000,
        "projected_yield_pct": 9.8,
        "stage": "structuring",
        "target_close": (date.today() + timedelta(days=71)).isoformat(),
        "summary": "Single-tenant cold storage, 20-yr NNN lease, investment-grade tenant.",
    },
    {
        "id": "CV-2025-26",
        "name": "Cascadia Vista",
        "blind_name": "PNW Multifamily Infill",
        "asset_class": "multifamily",
        "location": "Portland, OR",
        "size_usd": 26_000_000,
        "projected_yield_pct": 10.4,
        "stage": "teaser_live",
        "target_close": (date.today() + timedelta(days=54)).isoformat(),
        "summary": "Mid-rise infill multifamily, lease-up stabilized, refi-ready structure.",
    },
    {
        "id": "MH-2025-12",
        "name": "Mariners' Harbor",
        "blind_name": "PNW Marine Infrastructure",
        "asset_class": "infrastructure",
        "location": "Bellingham, WA",
        "size_usd": 12_750_000,
        "projected_yield_pct": 9.1,
        "stage": "structuring",
        "target_close": (date.today() + timedelta(days=92)).isoformat(),
        "summary": "Deep-water terminal upgrade, 30-yr concession, municipal offtake.",
    },
]


class DealsRegistry:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._deals: dict[str, dict] = {d["id"]: dict(d) for d in _SEED}

    def list_active(self, *, blind: bool = True) -> list[dict]:
        with self._lock:
            out = []
            for d in self._deals.values():
                if d["stage"] in {"closed", "cancelled"}:
                    continue
                copy = dict(d)
                copy["name"] = d["blind_name"] if blind else d["name"]
                out.append(copy)
            return sorted(out, key=lambda d: d["target_close"])

    def get(self, deal_id: str) -> dict | None:
        with self._lock:
            d = self._deals.get(deal_id)
            return dict(d) if d else None

    def pipeline_total(self) -> int:
        with self._lock:
            return sum(int(d["size_usd"]) for d in self._deals.values())

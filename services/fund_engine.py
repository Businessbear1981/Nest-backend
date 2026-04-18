import random
import threading
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Optional

from config import Config


@dataclass
class Distribution:
    date: str
    amount: float
    type: str  # 'principal_paydown' | 'yield' | 'reserve'


@dataclass
class ClientPosition:
    client_id: str
    invested_amount: float
    inception_date: date
    maturity_reserve_date: date
    current_value: float
    ytd_gross_return: float = 0.0
    daily_return: float = 0.0
    monthly_return: float = 0.0
    surplus_to_war_chest: float = 0.0
    distributions: list[Distribution] = field(default_factory=list)
    wc_outstanding: float = 0.0
    wc_rate_pct: float = 0.0


class FundEngine:
    """
    In-memory fund state for the NEST HFT fund. Swap persistence layer
    later; the surface here matches the spec so routes and the ticker
    don't have to change.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._positions: dict[str, ClientPosition] = {}
        self._market = {
            "treasury_10y_pct": 4.32,
            "sofr_pct": 5.31,
            "sp500_ytd_pct": 7.8,
            "hft_fund_ytd_pct": 14.6,
        }
        self._seed_demo()

    def _seed_demo(self) -> None:
        today = date.today()
        demo = ClientPosition(
            client_id="demo",
            invested_amount=1_000_000.0,
            inception_date=today - timedelta(days=92),
            maturity_reserve_date=today + timedelta(days=273),
            current_value=1_036_500.0,
            ytd_gross_return=0.0365,
            daily_return=0.00041,
            monthly_return=0.0118,
            surplus_to_war_chest=12_400.0,
        )
        demo.distributions.append(
            Distribution(date=(today - timedelta(days=30)).isoformat(), amount=9_800.0, type="yield")
        )
        demo.distributions.append(
            Distribution(date=(today - timedelta(days=60)).isoformat(), amount=9_600.0, type="yield")
        )
        self._positions[demo.client_id] = demo

    # ---------- public API ----------

    def get_position(self, client_id: str) -> dict:
        with self._lock:
            pos = self._positions.get(client_id)
            if pos is None:
                raise KeyError(client_id)
            gain = pos.current_value - pos.invested_amount
            b_covered = pos.ytd_gross_return >= Config.B_TRANCHE_COUPON_PCT * (
                (date.today() - pos.inception_date).days / 365.0
            )
            return {
                "client_id": pos.client_id,
                "invested_amount": round(pos.invested_amount, 2),
                "current_value": round(pos.current_value, 2),
                "net_gain": round(gain, 2),
                "yield_ytd_pct": round(pos.ytd_gross_return * 100, 3),
                "daily_return_pct": round(pos.daily_return * 100, 4),
                "monthly_return_pct": round(pos.monthly_return * 100, 3),
                "maturity_reserve_date": pos.maturity_reserve_date.isoformat(),
                "days_to_maturity_reserve_return": (pos.maturity_reserve_date - date.today()).days,
                "b_tranche_covered": b_covered,
                "surplus_to_war_chest": round(pos.surplus_to_war_chest, 2),
                "days_active": (date.today() - pos.inception_date).days,
                "timestamp": datetime.utcnow().isoformat() + "Z",
            }

    def calculate_yield(self, position: dict) -> dict:
        gross = position["current_value"] - position["invested_amount"]
        b_coupon = position["invested_amount"] * Config.B_TRANCHE_COUPON_PCT * (
            position["days_active"] / 365.0
        )
        mgmt_fee = position["invested_amount"] * Config.MGMT_FEE_PCT * (
            position["days_active"] / 365.0
        )
        net = gross - b_coupon - mgmt_fee
        annualized = (net / position["invested_amount"]) * (
            365.0 / max(position["days_active"], 1)
        )
        return {
            "gross_return": round(gross, 2),
            "b_coupon_paid": round(b_coupon, 2),
            "management_fee": round(mgmt_fee, 2),
            "net_to_client": round(net, 2),
            "annualized_yield_pct": round(annualized * 100, 3),
            "benchmark_10yr_treasury_pct": self._market["treasury_10y_pct"],
        }

    def get_distributions(self, client_id: str) -> list[dict]:
        with self._lock:
            pos = self._positions.get(client_id)
            if pos is None:
                raise KeyError(client_id)
            return [d.__dict__ for d in sorted(pos.distributions, key=lambda x: x.date, reverse=True)]

    def working_capital_eligibility(self, client_id: str) -> dict:
        pos_dict = self.get_position(client_id)
        max_draw = round(pos_dict["current_value"] * 0.4, 2)
        rate = round(self._market["sofr_pct"] + Config.WC_SPREAD_BPS / 100.0, 3)
        return {
            "eligible": pos_dict["b_tranche_covered"],
            "max_draw": max_draw,
            "rate_pct": rate,
            "term_days": 180,
            "collateral": f"{pos_dict['current_value']} NAV in fund position",
            "outstanding": pos_dict.get("surplus_to_war_chest", 0.0),
        }

    def request_working_capital(self, client_id: str, amount: float) -> dict:
        with self._lock:
            pos = self._positions.get(client_id)
            if pos is None:
                raise KeyError(client_id)
            elig = self.working_capital_eligibility(client_id)
            if not elig["eligible"]:
                return {"approved": False, "reason": "B-tranche coupon not yet covered"}
            if amount <= 0 or amount > elig["max_draw"]:
                return {"approved": False, "reason": f"Amount must be 0 < x <= {elig['max_draw']}"}
            pos.wc_outstanding += amount
            pos.wc_rate_pct = elig["rate_pct"]
            return {
                "approved": True,
                "amount": amount,
                "rate_pct": elig["rate_pct"],
                "term_days": elig["term_days"],
                "disbursement_date": date.today().isoformat(),
                "outstanding_total": round(pos.wc_outstanding, 2),
            }

    def benchmark(self) -> dict:
        return {**self._market, "timestamp": datetime.utcnow().isoformat() + "Z"}

    def market_snapshot(self) -> dict:
        with self._lock:
            drift = random.uniform(-0.02, 0.02)
            self._market["treasury_10y_pct"] = round(
                max(3.0, min(5.5, self._market["treasury_10y_pct"] + drift)), 3
            )
            self._market["hft_fund_ytd_pct"] = round(
                self._market["hft_fund_ytd_pct"] + random.uniform(-0.05, 0.08), 3
            )
            return dict(self._market, timestamp=datetime.utcnow().isoformat() + "Z")

    def tick_all(self) -> dict[str, dict]:
        """Simulate a tick of fund performance for every position."""
        out: dict[str, dict] = {}
        with self._lock:
            for cid, pos in self._positions.items():
                daily = random.uniform(0.0002, 0.0008)
                pos.daily_return = daily
                pos.monthly_return = pos.monthly_return * 0.97 + daily
                pos.ytd_gross_return += daily / 30.0
                pos.current_value *= 1 + daily
                if random.random() < 0.1:
                    pos.surplus_to_war_chest += pos.invested_amount * daily * 0.25
                out[cid] = self.get_position(cid)
        return out

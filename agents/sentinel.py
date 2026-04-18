"""Sentinel — NEST risk assessment engine.

7 risk dimensions, automated response system, continuous monitoring.
The immune system of the NEST platform.
"""
from datetime import datetime


# ── Risk Dimension Weights ──────────────────────────────────────

RISK_DIMENSIONS = {
    "market_risk":        {"weight": 0.20, "description": "Rate + spread environment"},
    "construction_risk":  {"weight": 0.20, "description": "Cost + schedule + GC quality"},
    "credit_risk":        {"weight": 0.20, "description": "DSCR + LTV + leverage"},
    "operational_risk":   {"weight": 0.15, "description": "Occupancy + NOI + management"},
    "regulatory_risk":    {"weight": 0.10, "description": "Licensing + permits + compliance"},
    "sponsor_risk":       {"weight": 0.10, "description": "Sponsor financial health"},
    "environmental_risk": {"weight": 0.05, "description": "Environmental + catastrophic"},
}

RISK_LEVELS = {
    (0, 25): "green",
    (25, 50): "yellow",
    (50, 75): "red",
    (75, 101): "critical",
}


def _risk_level(score: float) -> str:
    for (lo, hi), level in RISK_LEVELS.items():
        if lo <= score < hi:
            return level
    return "critical"


class SentinelAgent:
    """Monitors risk across 7 dimensions continuously."""

    def __init__(self):
        self._scores = {}  # deal_id -> latest score
        self._alerts = []

    def score_deal(self, deal_id: str, deal_data: dict = None, signals: dict = None) -> dict:
        """Full risk score across all 7 dimensions. 0=safe, 100=max risk."""
        deal_data = deal_data or {}
        signals = signals or {}

        dimension_scores = {
            "market_risk": self.score_market_risk(signals),
            "construction_risk": self.score_construction_risk(deal_data),
            "credit_risk": self.score_credit_risk(deal_data),
            "operational_risk": self.score_operational_risk(deal_data),
            "regulatory_risk": self.score_regulatory_risk(deal_data),
            "sponsor_risk": self.score_sponsor_risk(deal_data),
            "environmental_risk": self.score_environmental_risk(deal_data),
        }

        composite = sum(
            dim["score"] * RISK_DIMENSIONS[name]["weight"]
            for name, dim in dimension_scores.items()
        )

        level = _risk_level(composite)
        actions = self._recommend_actions(dimension_scores, level)

        result = {
            "deal_id": deal_id,
            "composite_score": round(composite, 1),
            "risk_level": level,
            "dimension_scores": {k: {"score": round(v["score"], 1), "level": v["level"], "top_factors": v.get("factors", [])} for k, v in dimension_scores.items()},
            "recommended_actions": actions,
            "lgd_estimate": self._estimate_lgd(composite),
            "surety_stress": round(min(1.0, composite / 100), 3),
            "scored_at": datetime.utcnow().isoformat(),
        }

        self._scores[deal_id] = result
        return result

    def score_market_risk(self, signals: dict) -> dict:
        score = 25  # neutral
        factors = []

        rate_change = signals.get("treasury_change_bps", 0)
        if abs(rate_change) > 75:
            score += 25
            factors.append(f"Rate moved {rate_change}bps — elevated volatility")
        elif abs(rate_change) > 25:
            score += 10

        vix = signals.get("vix", 18)
        if vix > 30:
            score += 20
            factors.append(f"VIX at {vix} — market stress")
        elif vix > 20:
            score += 5

        spread = signals.get("credit_spread_ig_bps", 125)
        if spread > 200:
            score += 15
            factors.append(f"IG spreads at {spread}bps — credit stress")

        access = signals.get("refi_market_access", "open_favorable")
        if access == "closed":
            score += 25
            factors.append("Refi market closed")
        elif access == "restricted":
            score += 15

        return {"score": min(100, max(0, score)), "level": _risk_level(score), "factors": factors}

    def score_construction_risk(self, deal: dict) -> dict:
        score = 15
        factors = []

        schedule_variance = deal.get("schedule_variance_days", 0)
        if schedule_variance > 180:
            score += 40
            factors.append(f"{schedule_variance} days behind schedule — critical delay")
        elif schedule_variance > 90:
            score += 25
            factors.append(f"{schedule_variance} days behind schedule")
        elif schedule_variance > 30:
            score += 10

        budget_variance = deal.get("budget_variance_pct", 0)
        if budget_variance > 20:
            score += 30
            factors.append(f"{budget_variance}% over budget — critical overrun")
        elif budget_variance > 10:
            score += 15

        if deal.get("construction_complete", False):
            score = max(0, score - 30)

        return {"score": min(100, max(0, score)), "level": _risk_level(score), "factors": factors}

    def score_credit_risk(self, deal: dict) -> dict:
        score = 20
        factors = []

        dscr = deal.get("dscr", 1.5)
        if dscr < 1.2:
            score += 35
            factors.append(f"DSCR {dscr:.2f}x — below minimum")
        elif dscr < 1.5:
            score += 15
            factors.append(f"DSCR {dscr:.2f}x — watch level")

        ltv = deal.get("ltv", 65)
        if ltv > 75:
            score += 25
            factors.append(f"LTV {ltv}% — exceeds comfort")
        elif ltv > 65:
            score += 10

        d_ebitda = deal.get("debt_to_ebitda", 5.0)
        if d_ebitda > 7.5:
            score += 20
            factors.append(f"D/EBITDA {d_ebitda:.1f}x — critical leverage")
        elif d_ebitda > 5.5:
            score += 10

        return {"score": min(100, max(0, score)), "level": _risk_level(score), "factors": factors}

    def score_operational_risk(self, deal: dict) -> dict:
        score = 15
        factors = []

        occ = deal.get("occupancy_pct", 85)
        occ_target = deal.get("occupancy_target_pct", 90)
        if occ < occ_target * 0.75:
            score += 35
            factors.append(f"Occupancy {occ}% vs {occ_target}% target — >25% behind")
        elif occ < occ_target * 0.85:
            score += 20
            factors.append(f"Occupancy {occ}% — behind ramp schedule")

        noi_variance = deal.get("noi_variance_pct", 0)
        if noi_variance < -20:
            score += 25
            factors.append(f"NOI {noi_variance}% below proforma")
        elif noi_variance < -10:
            score += 10

        return {"score": min(100, max(0, score)), "level": _risk_level(score), "factors": factors}

    def score_regulatory_risk(self, deal: dict) -> dict:
        score = 10
        factors = []

        if deal.get("license_at_risk", False):
            score += 50
            factors.append("License at risk — critical regulatory issue")
        if deal.get("permit_issues", False):
            score += 25
            factors.append("Permit issues outstanding")
        if deal.get("regulatory_violations", 0) > 0:
            score += 20

        return {"score": min(100, max(0, score)), "level": _risk_level(score), "factors": factors}

    def score_sponsor_risk(self, deal: dict) -> dict:
        score = 15
        factors = []

        liquidity_months = deal.get("sponsor_liquidity_months", 12)
        if liquidity_months < 3:
            score += 40
            factors.append(f"Sponsor liquidity {liquidity_months} months — critical")
        elif liquidity_months < 6:
            score += 20

        if deal.get("sponsor_litigation", False):
            score += 25
            factors.append("Active sponsor litigation")
        if deal.get("key_person_departure", False):
            score += 20
            factors.append("Key person departure without succession")

        return {"score": min(100, max(0, score)), "level": _risk_level(score), "factors": factors}

    def score_environmental_risk(self, deal: dict) -> dict:
        score = 10
        factors = []

        flood_zone = deal.get("flood_zone", "X")
        if flood_zone in ("VE", "A"):
            score += 30
            factors.append(f"Flood zone {flood_zone} — elevated exposure")
        elif flood_zone == "AE":
            score += 15

        if deal.get("contamination_found", False):
            score += 35
            factors.append("Environmental contamination identified")
        if deal.get("hurricane_exposure", False):
            score += 15

        return {"score": min(100, max(0, score)), "level": _risk_level(score), "factors": factors}

    def _recommend_actions(self, dimensions: dict, level: str) -> list:
        actions = []
        if level == "green":
            actions.append({"priority": "low", "action": "Continue standard monitoring", "agent": "sentinel"})
        elif level == "yellow":
            actions.append({"priority": "medium", "action": "Increase monitoring frequency", "agent": "vector"})
            actions.append({"priority": "medium", "action": "Draft warning memo for file", "agent": "morgan"})
        elif level == "red":
            actions.append({"priority": "high", "action": "Alert admin — Sean + Josh notification", "agent": "sentinel"})
            actions.append({"priority": "high", "action": "Start covenant cure clock", "agent": "sentinel"})
            actions.append({"priority": "high", "action": "Draft trustee notification", "agent": "morgan"})
        elif level == "critical":
            actions.append({"priority": "critical", "action": "Trustee notification — send immediately", "agent": "morgan"})
            actions.append({"priority": "critical", "action": "Performance bond evaluation triggered", "agent": "sentinel"})
            actions.append({"priority": "critical", "action": "Surety standby activation notice", "agent": "sentinel"})
        return actions

    def _estimate_lgd(self, composite: float) -> float:
        """Higher risk score = higher LGD estimate."""
        if composite < 25:
            return 5.0
        elif composite < 50:
            return 15.0
        elif composite < 75:
            return 35.0
        else:
            return 55.0

    def get_portfolio_risk(self) -> dict:
        """All scored deals with risk levels."""
        return {
            "deals": list(self._scores.values()),
            "total_scored": len(self._scores),
            "by_level": {
                "green": sum(1 for s in self._scores.values() if s["risk_level"] == "green"),
                "yellow": sum(1 for s in self._scores.values() if s["risk_level"] == "yellow"),
                "red": sum(1 for s in self._scores.values() if s["risk_level"] == "red"),
                "critical": sum(1 for s in self._scores.values() if s["risk_level"] == "critical"),
            },
        }

    def run(self, deal_id: str, deal_data: dict = None, signals: dict = None) -> dict:
        """Full Sentinel run on a single deal."""
        return self.score_deal(deal_id, deal_data, signals)


# Singleton
sentinel = SentinelAgent()

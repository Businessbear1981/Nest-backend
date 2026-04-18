"""Bond Grading Tool — comprehensive bond grade assignment.

Evaluates a proposed bond structure across credit quality, structural features,
collateral, and market conditions to assign an expected rating.

Based on S&P / JP Morgan commercial credit methodology.
"""
from datetime import datetime

# ── S&P-Aligned Rating Criteria ─────────────────────────────────

RATING_CRITERIA = {
    "AAA": {
        "dscr_min": 2.5, "ltv_max": 45, "d_ebitda_max": 3.0,
        "icr_min": 5.0, "lgd_max": 5,
        "requirements": ["3+ years audited financials", "Investment-grade sponsor", "Full cash collateral or AAA surety"],
    },
    "AA": {
        "dscr_min": 2.25, "ltv_max": 50, "d_ebitda_max": 3.5,
        "icr_min": 4.5, "lgd_max": 10,
        "requirements": ["3+ years audited financials", "Strong sponsor track record", "Cash collateral or AA-rated surety"],
    },
    "A": {
        "dscr_min": 2.0, "ltv_max": 55, "d_ebitda_max": 4.5,
        "icr_min": 3.5, "lgd_max": 15,
        "requirements": ["Audited financials", "Proven sponsor", "Hylant surety + LC combination"],
    },
    "BBB_plus": {
        "dscr_min": 1.75, "ltv_max": 62, "d_ebitda_max": 5.5,
        "icr_min": 2.75, "lgd_max": 25,
        "requirements": ["Audited financials", "Sponsor with track record", "Performance bond + LC"],
    },
    "BBB": {
        "dscr_min": 1.60, "ltv_max": 67, "d_ebitda_max": 6.0,
        "icr_min": 2.5, "lgd_max": 30,
        "requirements": ["Financial statements", "Adequate sponsor", "Surety bond"],
    },
    "BBB_minus": {
        "dscr_min": 1.5, "ltv_max": 70, "d_ebitda_max": 6.5,
        "icr_min": 2.25, "lgd_max": 35,
        "requirements": ["Financial statements", "Sponsor meets minimums", "Performance bond minimum"],
    },
    "BB_plus": {
        "dscr_min": 1.35, "ltv_max": 75, "d_ebitda_max": 7.5,
        "icr_min": 2.0, "lgd_max": 45,
        "requirements": ["Sub-investment grade — structural enhancement needed"],
    },
    "BB": {
        "dscr_min": 1.2, "ltv_max": 80, "d_ebitda_max": 8.5,
        "icr_min": 1.75, "lgd_max": 55,
        "requirements": ["Sub-investment grade — significant enhancement needed"],
    },
}

# ── Structural Enhancement Modifiers ────────────────────────────

STRUCTURAL_ENHANCEMENTS = {
    "cash_surety_sbloc": {"notch_up": 2, "lgd_reduction": 20, "description": "Cash collateral SBLOC — strongest enhancement"},
    "performance_bond": {"notch_up": 1, "lgd_reduction": 10, "description": "Performance bond — standard construction enhancement"},
    "lc": {"notch_up": 2, "lgd_reduction": 25, "description": "Letter of credit — bank-backed guarantee"},
    "bank_conduit": {"notch_up": 3, "lgd_reduction": 40, "description": "Bank conduit (B-tranche) — bank manages own proceeds → near-zero LGD"},
    "io_prefunded": {"notch_up": 1, "lgd_reduction": 10, "description": "IO pre-funded from proceeds — eliminates cash flow risk during construction"},
    "maturity_reserve": {"notch_up": 0, "lgd_reduction": 5, "description": "2.5% maturity reserve escrowed"},
    "parametric_insurance": {"notch_up": 1, "lgd_reduction": 15, "description": "Parametric insurance for catastrophic events"},
}

RATING_ORDER = ["AAA", "AA", "A", "BBB_plus", "BBB", "BBB_minus", "BB_plus", "BB", "B"]


class BondGrader:
    """Assigns expected bond rating based on credit quality + structural features."""

    def grade_bond(self, deal_data: dict, bond_data: dict = None,
                   credit_metrics: dict = None) -> dict:
        """Full bond grading analysis.

        Returns expected rating, component scores, enhancement impact, and gap analysis.
        """
        metrics = credit_metrics or {}
        bond = bond_data or {}

        # Step 1: Determine base rating from credit metrics
        base_grade = self._base_grade_from_metrics(metrics)

        # Step 2: Calculate structural enhancement notch-ups
        enhancements = self._evaluate_enhancements(deal_data, bond)
        total_notch_up = sum(e["notch_up"] for e in enhancements)
        total_lgd_reduction = sum(e["lgd_reduction"] for e in enhancements)

        # Step 3: Apply notch-ups to get enhanced grade
        enhanced_grade = self._notch_up(base_grade, total_notch_up)

        # Step 4: Component scoring (0-100 each)
        components = {
            "credit_quality": self._score_credit(metrics),
            "structural_features": self._score_structure(deal_data, bond, enhancements),
            "collateral_quality": self._score_collateral(deal_data),
            "market_conditions": self._score_market(deal_data),
            "sponsor_strength": self._score_sponsor(deal_data),
        }

        composite = sum(c["score"] * c["weight"] for c in components.values())

        # Step 5: Gap analysis — what's needed for target rating
        target = deal_data.get("rating_target", "A")
        gaps = self._gap_analysis(metrics, target)

        return {
            "deal_id": deal_data.get("id", "unknown"),
            "base_grade": base_grade,
            "enhanced_grade": enhanced_grade,
            "target_grade": target,
            "target_achieved": RATING_ORDER.index(enhanced_grade) <= RATING_ORDER.index(target) if enhanced_grade in RATING_ORDER and target in RATING_ORDER else False,
            "composite_score": round(composite, 1),
            "component_scores": {k: {"score": v["score"], "weight": v["weight"]} for k, v in components.items()},
            "enhancements_applied": enhancements,
            "total_notch_up": total_notch_up,
            "effective_lgd": max(0, (metrics.get("lgd_bare", 60)) - total_lgd_reduction),
            "gap_analysis": gaps,
            "requirements": RATING_CRITERIA.get(enhanced_grade, {}).get("requirements", []),
            "graded_at": datetime.utcnow().isoformat(),
        }

    def _base_grade_from_metrics(self, metrics: dict) -> str:
        """Determine base grade from credit metrics alone (no structural enhancement)."""
        dscr = metrics.get("dscr", 0)
        ltv = metrics.get("ltv", 100)
        d_ebitda = metrics.get("debt_to_ebitda", 99)
        icr = metrics.get("interest_coverage", 0)

        for grade, criteria in RATING_CRITERIA.items():
            if (dscr >= criteria["dscr_min"] and
                    ltv <= criteria["ltv_max"] and
                    d_ebitda <= criteria["d_ebitda_max"] and
                    icr >= criteria["icr_min"]):
                return grade
        return "BB"

    def _evaluate_enhancements(self, deal: dict, bond: dict) -> list:
        """Identify which structural enhancements are present."""
        active = []
        surety_type = deal.get("surety_type") or bond.get("b_tranche_overlay", {}).get("surety_type", "")

        if surety_type in STRUCTURAL_ENHANCEMENTS:
            active.append(STRUCTURAL_ENHANCEMENTS[surety_type])
        elif "sbloc" in str(surety_type).lower() or "cash" in str(surety_type).lower():
            active.append(STRUCTURAL_ENHANCEMENTS["cash_surety_sbloc"])

        overlay = bond.get("b_tranche_overlay", {})
        if overlay.get("proceeds_to_bank_aum"):
            active.append(STRUCTURAL_ENHANCEMENTS["bank_conduit"])
        if overlay.get("io_funded_from_proceeds"):
            active.append(STRUCTURAL_ENHANCEMENTS["io_prefunded"])
        if overlay.get("maturity_reserve_pct", 0) > 0:
            active.append(STRUCTURAL_ENHANCEMENTS["maturity_reserve"])

        return active

    def _notch_up(self, base_grade: str, notches: int) -> str:
        """Move grade up by N notches."""
        if base_grade not in RATING_ORDER:
            return base_grade
        idx = RATING_ORDER.index(base_grade)
        new_idx = max(0, idx - notches)
        return RATING_ORDER[new_idx]

    def _score_credit(self, metrics: dict) -> dict:
        dscr = metrics.get("dscr", 0)
        ltv = metrics.get("ltv", 100)
        score = 0
        if dscr >= 2.0: score += 40
        elif dscr >= 1.5: score += 25
        elif dscr >= 1.25: score += 10

        if ltv <= 55: score += 35
        elif ltv <= 65: score += 25
        elif ltv <= 75: score += 15

        icr = metrics.get("interest_coverage", 0)
        if icr >= 3.5: score += 25
        elif icr >= 2.25: score += 15
        elif icr >= 1.5: score += 8

        return {"score": min(100, score), "weight": 0.35}

    def _score_structure(self, deal, bond, enhancements) -> dict:
        score = 20  # base for having a structure
        for e in enhancements:
            score += e["notch_up"] * 10
        return {"score": min(100, score), "weight": 0.25}

    def _score_collateral(self, deal) -> dict:
        score = 50
        project = deal.get("project", {})
        if project.get("project_type") == "shovel_ready": score += 20
        if project.get("total_project_cost_usd", 0) > 50_000_000: score += 10
        if deal.get("readiness_score", 0) > 70: score += 20
        return {"score": min(100, score), "weight": 0.20}

    def _score_market(self, deal) -> dict:
        score = 60
        return {"score": score, "weight": 0.10}

    def _score_sponsor(self, deal) -> dict:
        sponsor = deal.get("sponsor", {})
        score = 40
        if sponsor.get("track_record_projects", 0) >= 5: score += 25
        if sponsor.get("audited_financials_received", False): score += 20
        if sponsor.get("net_worth_usd", 0) > 10_000_000: score += 15
        return {"score": min(100, score), "weight": 0.10}

    def _gap_analysis(self, metrics: dict, target: str) -> list:
        """What needs to improve to reach target rating."""
        target_criteria = RATING_CRITERIA.get(target, RATING_CRITERIA["A"])
        gaps = []

        dscr = metrics.get("dscr", 0)
        if dscr < target_criteria["dscr_min"]:
            gaps.append({"metric": "DSCR", "current": round(dscr, 2), "required": target_criteria["dscr_min"], "gap": round(target_criteria["dscr_min"] - dscr, 2), "action": "Increase NOI or reduce debt service"})

        ltv = metrics.get("ltv", 100)
        if ltv > target_criteria["ltv_max"]:
            gaps.append({"metric": "LTV", "current": round(ltv, 1), "required": target_criteria["ltv_max"], "gap": round(ltv - target_criteria["ltv_max"], 1), "action": "Increase equity or reduce debt"})

        icr = metrics.get("interest_coverage", 0)
        if icr < target_criteria["icr_min"]:
            gaps.append({"metric": "ICR", "current": round(icr, 2), "required": target_criteria["icr_min"], "gap": round(target_criteria["icr_min"] - icr, 2), "action": "Increase EBITDA or reduce interest"})

        return gaps


# Singleton
bond_grader = BondGrader()

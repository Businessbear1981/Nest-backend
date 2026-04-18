"""NEST Credit Engine — core underwriting metrics, stress testing, and scoring.

JP Morgan commercial credit benchmarks hardcoded throughout.
Jacaranda Trace PLOM (Series 2025, $231M, Florida LGFC) is the structural template.
"""
import math

# ── JP Morgan Benchmarks ────────────────────────────────────────

BENCHMARKS = {
    "A": {"dscr": 2.0, "cf_leverage": 1.5, "bs_leverage": 2.0, "ltv": 55, "d_ebitda": 4.5, "icr": 3.5},
    "BBB_plus": {"dscr": 1.75, "cf_leverage": 1.75, "bs_leverage": 2.25, "ltv": 62, "d_ebitda": 5.5, "icr": 2.75},
    "BBB_minus": {"dscr": 1.5, "cf_leverage": 2.0, "bs_leverage": 2.5, "ltv": 70, "d_ebitda": 6.5, "icr": 2.25},
}

GRADE_ORDER = ["AAA", "AA", "A", "BBB_plus", "BBB", "BBB_minus", "BB_plus", "BB", "B"]

# ── Scoring Categories (100 points total) ───────────────────────

SCORE_WEIGHTS = {
    "dscr": 20,
    "ltv": 15,
    "cash_flow_leverage": 10,
    "balance_sheet_leverage": 10,
    "debt_to_ebitda": 10,
    "interest_coverage": 10,
    "sponsor_quality": 10,
    "market_fundamentals": 15,
}


class CreditEngine:
    """Computes all credit metrics for NEST bond structuring."""

    def compute_metrics(self, deal_data: dict) -> dict:
        """Compute full credit metric suite from deal data.

        deal_data keys:
            noi, debt_service, total_debt, total_assets, ebitda,
            interest_expense, equity, project_value, total_project_cost
        """
        noi = deal_data.get("noi", 0)
        debt_service = deal_data.get("debt_service", 1)
        total_debt = deal_data.get("total_debt", 0)
        total_assets = deal_data.get("total_assets", 1)
        ebitda = deal_data.get("ebitda", noi)
        interest_expense = deal_data.get("interest_expense", debt_service * 0.6)
        equity = deal_data.get("equity", total_assets - total_debt)
        project_value = deal_data.get("project_value", total_assets)
        tpc = deal_data.get("total_project_cost", total_assets)

        dscr = noi / debt_service if debt_service > 0 else 0
        ltv = (total_debt / project_value * 100) if project_value > 0 else 100
        cf_leverage = total_debt / noi if noi > 0 else 99
        bs_leverage = total_debt / equity if equity > 0 else 99
        d_ebitda = total_debt / ebitda if ebitda > 0 else 99
        icr = ebitda / interest_expense if interest_expense > 0 else 0
        equity_pct = (equity / tpc * 100) if tpc > 0 else 0

        # LGD calculations
        lgd_bare = self.compute_lgd({})
        lgd_with_surety = self.compute_lgd({"senior_lien": True, "lc_coverage_pct": 0})
        lgd_dual_wrap = self.compute_lgd({"senior_lien": True, "lc_coverage_pct": 50, "io_funded": True})
        lgd_bank_conduit = self.compute_lgd({
            "senior_lien": True, "bank_manages_proceeds": True,
            "io_funded": True, "maturity_reserve_pct": 2.5, "lc_coverage_pct": 100
        })

        # Obligor grade
        grade = self._determine_grade(dscr, ltv, cf_leverage, bs_leverage, d_ebitda, icr)

        # Overall score
        score_result = self.score_deal({
            "dscr": dscr, "ltv": ltv, "cash_flow_leverage": cf_leverage,
            "balance_sheet_leverage": bs_leverage, "debt_to_ebitda": d_ebitda,
            "interest_coverage": icr, "equity_pct": equity_pct,
        })

        return {
            "dscr": round(dscr, 3),
            "ltv": round(ltv, 2),
            "cash_flow_leverage": round(cf_leverage, 3),
            "balance_sheet_leverage": round(bs_leverage, 3),
            "debt_to_ebitda": round(d_ebitda, 3),
            "interest_coverage": round(icr, 3),
            "equity_pct": round(equity_pct, 2),
            "lgd_bare": round(lgd_bare, 2),
            "lgd_with_surety": round(lgd_with_surety, 2),
            "lgd_dual_wrap": round(lgd_dual_wrap, 2),
            "lgd_bank_conduit": round(lgd_bank_conduit, 2),
            "obligor_grade": grade,
            "overall_score": score_result["total_score"],
            "score_breakdown": score_result["category_scores"],
            "recommendation": score_result["recommendation"],
        }

    def run_stress_scenarios(self, base_metrics: dict) -> dict:
        """Run Base / Downside / Stress scenarios.

        base_metrics: output of compute_metrics() plus noi, debt_service
        """
        noi = base_metrics.get("noi", 0)
        ds = base_metrics.get("debt_service", 1)

        scenarios = {}

        # BASE — as modeled
        scenarios["base"] = {
            "label": "Base Case",
            "revenue_adj": 1.0, "cost_adj": 1.0,
            "noi": noi,
            "debt_service": ds,
            "dscr": round(noi / ds, 3) if ds > 0 else 0,
            "surety_activated": False,
            "outcome": "Performing — all covenants met",
        }

        # DOWNSIDE — -15% revenue, +10% costs
        down_noi = noi * 0.85 * 0.9  # revenue down 15%, costs up ~10% of NOI
        down_dscr = down_noi / ds if ds > 0 else 0
        scenarios["downside"] = {
            "label": "Downside (-15% rev, +10% cost)",
            "revenue_adj": 0.85, "cost_adj": 1.10,
            "noi": round(down_noi),
            "debt_service": ds,
            "dscr": round(down_dscr, 3),
            "surety_activated": down_dscr < 1.25,
            "outcome": "Stress — IO reserve drawn" if down_dscr < 1.25 else "Manageable — tight but performing",
        }

        # STRESS — -25% revenue, +8 month delay
        stress_noi = noi * 0.75 * 0.85
        stress_dscr = stress_noi / ds if ds > 0 else 0
        scenarios["stress"] = {
            "label": "Stress (-25% rev, +8mo delay)",
            "revenue_adj": 0.75, "cost_adj": 1.15,
            "noi": round(stress_noi),
            "debt_service": ds,
            "dscr": round(stress_dscr, 3),
            "surety_activated": stress_dscr < 1.0,
            "outcome": "Distressed — surety draw likely" if stress_dscr < 1.0 else "Stress — reserve activated",
        }

        return scenarios

    def compute_lgd(self, params: dict) -> float:
        """Compute Loss Given Default (0-100%).

        Lower LGD = better protection for bondholders.
        NEST's B-tranche bank conduit model approaches 0% LGD.
        """
        base_recovery = params.get("base_recovery_pct", 40)
        bank_manages = params.get("bank_manages_proceeds", False)
        io_funded = params.get("io_funded", False)
        maturity_reserve = params.get("maturity_reserve_pct", 0)
        senior_lien = params.get("senior_lien", False)
        lc_coverage = params.get("lc_coverage_pct", 0)

        lgd = 100 - base_recovery  # start at 60% LGD

        if senior_lien:
            lgd -= 10
        if bank_manages:
            lgd -= 20  # bank controls own proceeds — massive risk reduction
        if io_funded:
            lgd -= 10  # no cash flow risk during construction
        if maturity_reserve > 0:
            lgd -= min(10, maturity_reserve * 4)
        if lc_coverage > 0:
            lgd -= min(25, lc_coverage * 0.25)

        return max(0, min(100, lgd))

    def compute_capital_stack(self, project_cost: float, a_ltc: float = 0.75,
                              b_addon: float = 0.07, duration: int = 5,
                              a_coupon: float = 7.0, b_coupon: float = 12.0) -> dict:
        """Compute full capital stack breakdown per NEST model.

        Series A: 75% LTC, investment grade, Hylant surety / LC
        Series B: +7% (82% CLTV), B/BBB, bank managed
        """
        a_amount = project_cost * a_ltc
        b_amount = project_cost * b_addon
        cltv = (a_ltc + b_addon) * 100
        equity = project_cost - a_amount - b_amount

        # Pre-funded costs
        io_impound = a_amount * (a_coupon / 100) * min(duration, 2)  # 2yr IO from proceeds
        coupon_reserve = (a_amount + b_amount) * 0.025
        surety_premium = a_amount * 0.015
        ae_fee_a = a_amount * 0.025
        ae_fee_b = b_amount * 0.025
        total_raise = a_amount + b_amount + io_impound + coupon_reserve + surety_premium + ae_fee_a + ae_fee_b
        par_value = a_amount + b_amount

        return {
            "project_cost": round(project_cost),
            "a_amount": round(a_amount),
            "a_ltc_pct": a_ltc * 100,
            "a_coupon_pct": a_coupon,
            "b_amount": round(b_amount),
            "b_addon_pct": b_addon * 100,
            "b_coupon_pct": b_coupon,
            "cltv": round(cltv, 1),
            "equity": round(equity),
            "equity_pct": round((1 - a_ltc - b_addon) * 100, 1),
            "io_impound": round(io_impound),
            "coupon_reserve": round(coupon_reserve),
            "surety_premium": round(surety_premium),
            "ae_fee_a": round(ae_fee_a),
            "ae_fee_b": round(ae_fee_b),
            "total_raise": round(total_raise),
            "par_value": round(par_value),
        }

    def score_deal(self, metrics: dict) -> dict:
        """100-point scoring model across 8 categories.

        Returns category_scores, total_score, grade, recommendation.
        """
        scores = {}

        # DSCR (20 pts)
        dscr = metrics.get("dscr", 0)
        if dscr >= 2.5:
            scores["dscr"] = 20
        elif dscr >= 2.0:
            scores["dscr"] = 18
        elif dscr >= 1.75:
            scores["dscr"] = 15
        elif dscr >= 1.5:
            scores["dscr"] = 12
        elif dscr >= 1.25:
            scores["dscr"] = 8
        else:
            scores["dscr"] = 3

        # LTV (15 pts)
        ltv = metrics.get("ltv", 100)
        if ltv <= 50:
            scores["ltv"] = 15
        elif ltv <= 55:
            scores["ltv"] = 13
        elif ltv <= 62:
            scores["ltv"] = 11
        elif ltv <= 70:
            scores["ltv"] = 8
        elif ltv <= 75:
            scores["ltv"] = 5
        else:
            scores["ltv"] = 2

        # Cash flow leverage (10 pts)
        cfl = metrics.get("cash_flow_leverage", 99)
        if cfl <= 1.0:
            scores["cash_flow_leverage"] = 10
        elif cfl <= 1.5:
            scores["cash_flow_leverage"] = 8
        elif cfl <= 2.0:
            scores["cash_flow_leverage"] = 6
        elif cfl <= 2.5:
            scores["cash_flow_leverage"] = 4
        else:
            scores["cash_flow_leverage"] = 2

        # Balance sheet leverage (10 pts)
        bsl = metrics.get("balance_sheet_leverage", 99)
        if bsl <= 1.5:
            scores["balance_sheet_leverage"] = 10
        elif bsl <= 2.0:
            scores["balance_sheet_leverage"] = 8
        elif bsl <= 2.5:
            scores["balance_sheet_leverage"] = 6
        elif bsl <= 3.0:
            scores["balance_sheet_leverage"] = 4
        else:
            scores["balance_sheet_leverage"] = 2

        # Debt/EBITDA (10 pts)
        de = metrics.get("debt_to_ebitda", 99)
        if de <= 3.5:
            scores["debt_to_ebitda"] = 10
        elif de <= 4.5:
            scores["debt_to_ebitda"] = 8
        elif de <= 5.5:
            scores["debt_to_ebitda"] = 6
        elif de <= 6.5:
            scores["debt_to_ebitda"] = 4
        else:
            scores["debt_to_ebitda"] = 2

        # Interest coverage (10 pts)
        icr = metrics.get("interest_coverage", 0)
        if icr >= 4.0:
            scores["interest_coverage"] = 10
        elif icr >= 3.5:
            scores["interest_coverage"] = 8
        elif icr >= 2.75:
            scores["interest_coverage"] = 6
        elif icr >= 2.25:
            scores["interest_coverage"] = 4
        else:
            scores["interest_coverage"] = 2

        # Sponsor quality (10 pts) — from deal data if available
        sponsor = metrics.get("sponsor_quality", 7)
        scores["sponsor_quality"] = min(10, max(0, sponsor))

        # Market fundamentals (15 pts) — from deal data if available
        market = metrics.get("market_fundamentals", 10)
        scores["market_fundamentals"] = min(15, max(0, market))

        total = sum(scores.values())

        if total >= 85:
            grade = "A"
        elif total >= 75:
            grade = "BBB_plus"
        elif total >= 65:
            grade = "BBB"
        elif total >= 55:
            grade = "BBB_minus"
        elif total >= 45:
            grade = "BB_plus"
        else:
            grade = "BB"

        if total >= 80:
            rec = "Strong credit — proceed to structuring"
        elif total >= 65:
            rec = "Acceptable credit — proceed with conditions"
        elif total >= 50:
            rec = "Marginal credit — additional enhancement required"
        else:
            rec = "Sub-investment grade — restructure or decline"

        return {
            "category_scores": scores,
            "total_score": total,
            "grade": grade,
            "recommendation": rec,
        }

    def compute_refi_economics(self, face: float, fee_pct: float = 2.5,
                                cycles: int = 10, bps_per_cycle: float = 25,
                                term_years: int = 5) -> dict:
        """Compute refi cycle economics for NEST's dynamic lifecycle model.

        NEST earns arrangement fee on each refi. Client gets rate reduction.
        10-15 cycles over bond life = massive cumulative economics.
        """
        fee_per_cycle = face * (fee_pct / 100)
        total_fees = fee_per_cycle * cycles
        cumulative_bps = bps_per_cycle * cycles
        client_annual_savings = face * (cumulative_bps / 10000)
        days_between = (term_years * 365) / max(cycles, 1)

        return {
            "face_amount": round(face),
            "fee_pct_per_cycle": fee_pct,
            "fee_per_cycle": round(fee_per_cycle),
            "total_cycles": cycles,
            "total_fees": round(total_fees),
            "cumulative_rate_reduction_bps": cumulative_bps,
            "client_annual_savings_at_maturity": round(client_annual_savings),
            "cycles_per_year": round(cycles / max(term_years, 1), 1),
            "days_between_cycles": round(days_between),
        }

    def _determine_grade(self, dscr, ltv, cf_lev, bs_lev, d_ebitda, icr):
        """Determine obligor grade from JP Morgan benchmarks. Single breach = downgrade."""
        for grade_name, thresholds in BENCHMARKS.items():
            if (dscr >= thresholds["dscr"] and
                    ltv <= thresholds["ltv"] and
                    cf_lev <= thresholds["cf_leverage"] and
                    bs_lev <= thresholds["bs_leverage"] and
                    d_ebitda <= thresholds["d_ebitda"] and
                    icr >= thresholds["icr"]):
                return grade_name
        return "BB"  # sub-investment grade


# Singleton
credit_engine = CreditEngine()

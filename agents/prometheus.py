"""Prometheus — NEST in-house financial modeling engine.

4 modules: proforma modeling, feasibility study, audit simulation, stress testing.
Compresses expensive third-party engagement timeline by 30-40%.
"""
import math
from datetime import datetime
from services.market_benchmarks import get_benchmarks

try:
    from agents._claude import complete, ClaudeUnavailable
    from services.jimmy_lee import JIMMY_LEE_SYSTEM_PROMPT
except ImportError:
    complete = None
    JIMMY_LEE_SYSTEM_PROMPT = ""
    ClaudeUnavailable = Exception


class PrometheusAgent:
    """In-house financial modeling: proforma, feasibility, audit sim, stress test."""

    # ── MODULE 1: PROFORMA MODELING ─────────────────────────────

    def build_proforma(self, inputs: dict) -> dict:
        """Build 10-year month-by-month proforma model.

        Returns revenue, expense, NOI, capital schedules + summary.
        """
        project_type = inputs.get("project_type", "senior_living")
        total_units = inputs.get("total_units", 200)
        unit_mix = inputs.get("unit_mix", {"il": 0.5, "al": 0.3, "mc": 0.2})
        tpc = inputs.get("total_project_cost", 100_000_000)
        construction_months = inputs.get("construction_months", 18)
        stab_target = inputs.get("stabilization_target_pct", 90) / 100
        stab_month = inputs.get("stabilization_month", 36)
        exit_cap = inputs.get("exit_cap_rate", 6.75) / 100
        debt = inputs.get("debt_structure", {})

        benchmarks = get_benchmarks(project_type)
        duration = 120  # 10 years

        # Compute blended revenue per unit
        if project_type == "senior_living":
            rev_per_unit = (
                unit_mix.get("il", 0.5) * benchmarks.get("il_revenue_per_unit_monthly", {}).get("mid", 5200) +
                unit_mix.get("al", 0.3) * benchmarks.get("al_revenue_per_unit_monthly", {}).get("mid", 7200) +
                unit_mix.get("mc", 0.2) * benchmarks.get("mc_revenue_per_unit_monthly", {}).get("mid", 8500)
            )
            opex_per_unit_annual = (
                unit_mix.get("il", 0.5) * benchmarks.get("opex_per_il_unit_annual", {}).get("mid", 55000) +
                unit_mix.get("al", 0.3) * benchmarks.get("opex_per_al_unit_annual", {}).get("mid", 82000) +
                unit_mix.get("mc", 0.2) * benchmarks.get("opex_per_mc_unit_annual", {}).get("mid", 108000)
            )
        else:
            rev_per_unit = inputs.get("revenue_per_unit_monthly", 5200)
            opex_per_unit_annual = inputs.get("opex_per_unit_annual", 55000)

        monthly_opex_per_unit = opex_per_unit_annual / 12
        debt_rate = debt.get("rate_pct", 7.0) / 100
        debt_amount = debt.get("amount", tpc * 0.75)
        monthly_ds = debt_amount * debt_rate / 12

        revenue_schedule = []
        expense_schedule = []
        noi_schedule = []
        capital_schedule = []

        for month in range(1, duration + 1):
            # Construction phase
            if month <= construction_months:
                occ = 0
                draw = tpc / construction_months
            else:
                operating_month = month - construction_months
                if operating_month <= (stab_month - construction_months):
                    t = operating_month / max(1, stab_month - construction_months)
                    occ = stab_target * (3 * t**2 - 2 * t**3)
                else:
                    occ = stab_target
                draw = 0

            occupied = int(total_units * occ)
            gross_rev = occupied * rev_per_unit
            vacancy_loss = (total_units - occupied) * rev_per_unit
            other_income = gross_rev * 0.03
            total_rev = gross_rev + other_income

            mgmt_fee = total_rev * 0.05
            payroll = total_rev * 0.55 if occ > 0 else 0
            utilities = total_units * 150
            insurance = total_units * 80
            taxes = total_units * 200
            maintenance = total_units * 100
            admin = total_units * 75
            total_opex = mgmt_fee + payroll + utilities + insurance + taxes + maintenance + admin

            noi = total_rev - total_opex
            ds = monthly_ds if month > construction_months else 0
            dscr = noi / ds if ds > 0 else 0
            cash_flow = noi - ds

            revenue_schedule.append({
                "month": month, "occupancy_pct": round(occ * 100, 1),
                "gross_revenue": round(gross_rev), "vacancy_loss": round(vacancy_loss),
                "other_income": round(other_income), "total_revenue": round(total_rev),
            })
            expense_schedule.append({
                "month": month, "management_fee": round(mgmt_fee),
                "payroll": round(payroll), "utilities": round(utilities),
                "insurance": round(insurance), "taxes": round(taxes),
                "maintenance": round(maintenance), "admin": round(admin),
                "total_opex": round(total_opex),
            })
            noi_schedule.append({
                "month": month, "noi": round(noi), "debt_service": round(ds),
                "dscr": round(dscr, 3), "cash_flow": round(cash_flow),
            })
            capital_schedule.append({
                "month": month, "construction_draw": round(draw),
                "capex": 0, "total_invested": round(draw),
            })

        # Summary at stabilization
        stab_idx = min(stab_month - 1, len(noi_schedule) - 1)
        stab_noi = noi_schedule[stab_idx]["noi"] * 12
        stab_dscr = noi_schedule[stab_idx]["dscr"]
        exit_value = stab_noi / exit_cap if exit_cap > 0 else 0
        equity = tpc * 0.25
        equity_multiple = exit_value / equity if equity > 0 else 0

        return {
            "revenue_schedule": revenue_schedule,
            "expense_schedule": expense_schedule,
            "noi_schedule": noi_schedule,
            "capital_schedule": capital_schedule,
            "summary": {
                "stabilized_noi_annual": round(stab_noi),
                "stabilized_dscr": round(stab_dscr, 3),
                "stabilized_ltv": round(debt_amount / exit_value * 100, 1) if exit_value > 0 else 0,
                "exit_value": round(exit_value),
                "equity_multiple": round(equity_multiple, 2),
                "total_project_cost": tpc,
                "total_units": total_units,
                "stabilization_month": stab_month,
            },
        }

    def build_occupancy_ramp(self, project_type: str, total_units: int,
                              stabilization_month: int, target_occupancy: float) -> list:
        """Generate occupancy ramp schedule using S-curve."""
        target = target_occupancy / 100 if target_occupancy > 1 else target_occupancy
        ramp = []
        for month in range(1, stabilization_month + 12):
            if month <= stabilization_month:
                t = month / stabilization_month
                occ = target * (3 * t**2 - 2 * t**3)
            else:
                occ = target
            ramp.append({
                "month": month,
                "occupancy_pct": round(occ * 100, 1),
                "occupied_units": int(total_units * occ),
            })
        return ramp

    def benchmark_assumptions(self, project_type: str, assumptions: dict) -> dict:
        """Compare assumptions to market benchmarks, flag variances."""
        benchmarks = get_benchmarks(project_type)
        flags = []
        for key, val in assumptions.items():
            if key in benchmarks:
                bm = benchmarks[key]
                if isinstance(bm, dict) and "low" in bm and "high" in bm:
                    if val < bm["low"]:
                        flags.append({"metric": key, "value": val, "range": f"{bm['low']}-{bm['high']}", "flag": "conservative"})
                    elif val > bm["high"]:
                        flags.append({"metric": key, "value": val, "range": f"{bm['low']}-{bm['high']}", "flag": "aggressive"})
                    else:
                        flags.append({"metric": key, "value": val, "range": f"{bm['low']}-{bm['high']}", "flag": "in_range"})
        return {"flags": flags, "total": len(flags), "aggressive": sum(1 for f in flags if f["flag"] == "aggressive")}

    # ── MODULE 2: FEASIBILITY STUDY ─────────────────────────────

    def generate_feasibility_study(self, deal: dict, proforma: dict) -> dict:
        """Generate preliminary feasibility study via Claude API."""
        summary = proforma.get("summary", {})
        prompt = (
            f"Generate a preliminary feasibility study for:\n"
            f"Project: {deal.get('name', 'Unnamed')}\n"
            f"Location: {deal.get('city', '')}, {deal.get('state', '')}\n"
            f"Asset type: {deal.get('asset_type', 'senior_living')}\n"
            f"Units: {summary.get('total_units', 0)}\n"
            f"TPC: ${summary.get('total_project_cost', 0):,.0f}\n"
            f"Stabilized NOI: ${summary.get('stabilized_noi_annual', 0):,.0f}\n"
            f"Stabilized DSCR: {summary.get('stabilized_dscr', 0):.2f}x\n"
            f"Exit value: ${summary.get('exit_value', 0):,.0f}\n\n"
            f"Sections: (1) Executive Summary (go/no-go). (2) Market Analysis. "
            f"(3) Site Analysis. (4) Financial Feasibility. (5) Risk Assessment. "
            f"(6) Conclusion: FEASIBLE / CONDITIONALLY FEASIBLE / NOT FEASIBLE."
        )
        try:
            study_text = complete(JIMMY_LEE_SYSTEM_PROMPT, prompt, max_tokens=3000)
        except (ClaudeUnavailable, Exception):
            study_text = f"# Feasibility Study — {deal.get('name', 'Project')}\n\nClaude API unavailable. Manual review required."

        go_no_go = "FEASIBLE" if summary.get("stabilized_dscr", 0) >= 1.5 else "CONDITIONALLY FEASIBLE" if summary.get("stabilized_dscr", 0) >= 1.25 else "NOT FEASIBLE"

        return {
            "study_markdown": study_text,
            "go_no_go": go_no_go,
            "key_risks": [
                "Construction delay risk" if summary.get("stabilization_month", 36) > 36 else None,
                "Occupancy ramp risk" if summary.get("stabilized_dscr", 0) < 1.75 else None,
                "Rate environment risk",
            ],
            "recommended_next_steps": [
                "Commission KPMG feasibility study" if go_no_go != "NOT FEASIBLE" else "Restructure deal",
                "Engage Hylant for surety indication",
                "Order Phase I ESA",
            ],
        }

    # ── MODULE 3: AUDIT SIMULATION ──────────────────────────────

    def simulate_audit(self, sponsor_financials: dict, project_financials: dict) -> dict:
        """Find problems before the real CPA does."""
        findings = []

        # Sponsor checks
        revenue = sponsor_financials.get("revenue", 0)
        ebitda = sponsor_financials.get("ebitda", 0)
        net_worth = sponsor_financials.get("net_worth", 0)
        total_debt = sponsor_financials.get("total_debt", 0)

        if ebitda and revenue:
            margin = ebitda / revenue
            if margin > 0.40:
                findings.append({"severity": "major", "area": "revenue_recognition", "finding": f"EBITDA margin {margin:.0%} unusually high — verify revenue recognition", "fix_required_for_bond": True})
            if margin < 0.10:
                findings.append({"severity": "major", "area": "profitability", "finding": f"EBITDA margin {margin:.0%} below minimum threshold", "fix_required_for_bond": True})

        if net_worth and total_debt:
            leverage = total_debt / net_worth if net_worth > 0 else 99
            if leverage > 3.0:
                findings.append({"severity": "critical", "area": "leverage", "finding": f"Sponsor leverage {leverage:.1f}x exceeds comfort — requires additional equity or guarantor", "fix_required_for_bond": True})

        related_party = sponsor_financials.get("related_party_transactions", 0)
        if related_party > 0:
            findings.append({"severity": "major", "area": "related_party", "finding": f"${related_party:,.0f} in related-party transactions — must be arm's-length or eliminated", "fix_required_for_bond": True})

        # Project checks
        tpc = project_financials.get("total_project_cost", 0)
        soft_costs = project_financials.get("soft_costs", 0)
        contingency = project_financials.get("contingency", 0)

        if tpc > 0:
            if soft_costs / tpc < 0.10:
                findings.append({"severity": "major", "area": "soft_costs", "finding": f"Soft costs {soft_costs/tpc:.0%} of TPC — minimum 10-15% required", "fix_required_for_bond": True})
            if contingency / tpc < 0.03:
                findings.append({"severity": "major", "area": "contingency", "finding": f"Contingency {contingency/tpc:.0%} of TPC — minimum 3-5% required", "fix_required_for_bond": True})

        # Normalize EBITDA
        owner_comp = sponsor_financials.get("owner_compensation", 0)
        market_comp = sponsor_financials.get("market_compensation", 0)
        non_recurring = sponsor_financials.get("non_recurring_items", 0)
        normalized_ebitda = ebitda + (owner_comp - market_comp) + non_recurring

        readiness = max(0, 100 - len(findings) * 15)

        return {
            "audit_findings": findings,
            "adjusted_ebitda": round(normalized_ebitda),
            "adjusted_net_worth": round(net_worth),
            "audit_readiness_score": readiness,
            "pre_audit_action_plan": [f["finding"] for f in findings if f["fix_required_for_bond"]],
        }

    # ── MODULE 4: STRESS TESTING ────────────────────────────────

    def run_stress_tests(self, proforma: dict, bond_structure: dict = None) -> dict:
        """4-scenario stress test: Base, Downside, Stress, Catastrophic."""
        noi_schedule = proforma.get("noi_schedule", [])
        if not noi_schedule:
            return {"error": "No NOI schedule in proforma"}

        # Get stabilized month values
        stab_noi = proforma.get("summary", {}).get("stabilized_noi_annual", 0) / 12
        stab_ds = noi_schedule[-1].get("debt_service", 0) if noi_schedule else 0

        scenarios = {}
        configs = [
            ("base", "Base Case", 1.0, 1.0, 0),
            ("downside", "Downside (-15% rev, +10% cost)", 0.85, 1.10, 0),
            ("stress", "Stress (-25% rev, +20% cost, +6mo delay)", 0.75, 1.20, 6),
            ("catastrophic", "Catastrophic (-40% rev, COVID/hurricane)", 0.60, 1.30, 12),
        ]

        for key, label, rev_mult, cost_mult, delay_months in configs:
            adj_noi = stab_noi * rev_mult / cost_mult
            dscr = adj_noi / stab_ds if stab_ds > 0 else 0
            surety_draw = dscr < 1.0
            deficit = max(0, stab_ds - adj_noi) * 12

            scenarios[key] = {
                "label": label,
                "revenue_multiplier": rev_mult,
                "cost_multiplier": cost_mult,
                "delay_months": delay_months,
                "adjusted_noi_monthly": round(adj_noi),
                "dscr": round(dscr, 3),
                "surety_draw_required": surety_draw,
                "annual_deficit": round(deficit),
                "outcome": (
                    "Performing" if dscr >= 1.5 else
                    "Tight but serviceable" if dscr >= 1.25 else
                    "Reserve activated" if dscr >= 1.0 else
                    "Surety draw required" if dscr >= 0.75 else
                    "Default scenario — full surety claim"
                ),
            }

        return scenarios

    def compute_break_even(self, proforma: dict) -> dict:
        """Compute occupancy, rate, and delay break-even points."""
        summary = proforma.get("summary", {})
        noi_annual = summary.get("stabilized_noi_annual", 0)
        noi_schedule = proforma.get("noi_schedule", [])
        ds_monthly = noi_schedule[-1].get("debt_service", 0) if noi_schedule else 0
        ds_annual = ds_monthly * 12

        stab_occ = 0.90  # default
        rev_schedule = proforma.get("revenue_schedule", [])
        stab_rev = rev_schedule[-1].get("total_revenue", 0) * 12 if rev_schedule else 0

        # Occupancy break-even
        if stab_rev > 0 and ds_annual > 0:
            occ_be = (ds_annual / stab_rev) * stab_occ * 100
        else:
            occ_be = 0

        margin = stab_occ * 100 - occ_be if occ_be > 0 else 0

        return {
            "occupancy_break_even_pct": round(occ_be, 1),
            "margin_of_safety_pct": round(margin, 1),
            "annual_debt_service": round(ds_annual),
            "stabilized_noi": round(noi_annual),
        }

    # ── FULL RUN ────────────────────────────────────────────────

    def run(self, deal_id: str, inputs: dict = None) -> dict:
        """Full Prometheus run: proforma → benchmarks → feasibility → stress."""
        inputs = inputs or {
            "project_type": "senior_living",
            "total_units": 200,
            "total_project_cost": 100_000_000,
            "stabilization_month": 36,
            "debt_structure": {"rate_pct": 7.0, "amount": 75_000_000},
        }

        proforma = self.build_proforma(inputs)
        benchmarks = self.benchmark_assumptions(
            inputs.get("project_type", "senior_living"), inputs
        )
        stress = self.run_stress_tests(proforma)
        break_even = self.compute_break_even(proforma)

        return {
            "deal_id": deal_id,
            "proforma_summary": proforma["summary"],
            "benchmarks": benchmarks,
            "stress_tests": stress,
            "break_even": break_even,
            "run_at": datetime.utcnow().isoformat(),
        }


# Singleton
prometheus = PrometheusAgent()

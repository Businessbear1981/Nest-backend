"""Maxwell — Credit analyst agent.
Full JPM benchmark comparison with narrative grading.
"""
from services.core import credit, JPM, call_claude, ts


class MaxwellAgent:
    def analyze(self, deal: dict) -> dict:
        metrics = credit.compute(deal)
        commentary = call_claude(
            f"Provide a 3-paragraph credit analysis for this deal. "
            f"DSCR: {metrics['dscr']}, LTV: {metrics['ltv_pct']}%, "
            f"Grade: {metrics['obligor_grade']}, Score: {metrics['deal_score']}. "
            f"Reference JPM benchmarks. Be direct.",
        )
        return {
            "metrics": metrics,
            "commentary": commentary,
            "timestamp": ts(),
        }

    def normalize_ebitda(self, financials: dict) -> dict:
        raw_ebitda = financials.get("ebitda_usd", 0)
        adjustments = []
        adj = 0

        non_recurring = financials.get("non_recurring_usd", 0)
        if non_recurring:
            adj -= non_recurring
            adjustments.append({"item": "Non-recurring items", "amount": -non_recurring})

        owner_comp = financials.get("excess_owner_comp_usd", 0)
        if owner_comp:
            adj += owner_comp
            adjustments.append({"item": "Excess owner compensation", "amount": owner_comp})

        one_time = financials.get("one_time_costs_usd", 0)
        if one_time:
            adj += one_time
            adjustments.append({"item": "One-time costs addback", "amount": one_time})

        normalized = raw_ebitda + adj
        return {
            "raw_ebitda_usd": round(raw_ebitda),
            "adjustments": adjustments,
            "total_adjustment_usd": round(adj),
            "normalized_ebitda_usd": round(normalized),
            "timestamp": ts(),
        }

    def grade_obligor(self, metrics: dict) -> dict:
        dscr = metrics.get("dscr", 0)
        ltv = metrics.get("ltv_pct", 100)
        grade = metrics.get("obligor_grade", "Sub-IG")

        benchmarks_comparison = {}
        for g, b in JPM.items():
            benchmarks_comparison[g] = {
                "dscr_meets": dscr >= b["dscr"],
                "ltv_meets": ltv <= b["ltv"],
                "cf_meets": metrics.get("cash_flow_leverage", 99) <= b["cf"],
                "bs_meets": metrics.get("balance_sheet_leverage", 99) <= b["bs"],
                "de_meets": metrics.get("debt_to_ebitda", 99) <= b["de"],
                "icr_meets": metrics.get("interest_coverage", 0) >= b["icr"],
            }
            met = sum(1 for v in benchmarks_comparison[g].values() if v)
            benchmarks_comparison[g]["metrics_met"] = f"{met}/6"

        narrative = call_claude(
            f"Write a 2-sentence obligor grade narrative. "
            f"Grade: {grade}. DSCR: {dscr}. LTV: {ltv}%. "
            f"Reference specific JPM thresholds the obligor meets or misses."
        )

        return {
            "obligor_grade": grade,
            "benchmarks_comparison": benchmarks_comparison,
            "narrative": narrative,
            "timestamp": ts(),
        }


maxwell = MaxwellAgent()

"""
MerlinAgent — M&A intelligence, target scoring, and deal structuring.

Responsibilities:
  - Score acquisition targets across 8 weighted dimensions
  - Run 3-level game theory analysis on targets
  - Build business plans via Claude API
  - Model IRR across 3x3 scenario matrix
  - Scan EDGAR for acquisition targets by NAICS
  - Orchestrate full deal analysis pipeline
"""
import math
import random
from datetime import datetime

# Safe imports — all optional at runtime
try:
    from agents._claude import ask_claude
except ImportError:
    ask_claude = None

try:
    from services.jimmy_lee import jimmy_lee
except ImportError:
    jimmy_lee = None

try:
    from blockchain.nest_chain import chain
except ImportError:
    chain = None

try:
    from game_theory.engine import game_engine
except ImportError:
    game_engine = None


# NAICS priority tiers for NEST acquisition strategy
NAICS_PRIORITY = {
    "tier1": {
        "description": "Core targets — fragmented services with recurring revenue",
        "codes": {
            "561730": "Landscaping Services",
            "561720": "Janitorial Services",
            "561210": "Facilities Support Services",
            "238220": "Plumbing, Heating, and AC Contractors",
            "238210": "Electrical Contractors",
            "238160": "Roofing Contractors",
            "811111": "General Auto Repair",
            "812310": "Coin-Operated Laundries",
        },
    },
    "tier2": {
        "description": "Adjacent — light industrial and specialty services",
        "codes": {
            "423830": "Industrial Machinery Distribution",
            "484110": "General Freight Trucking (Local)",
            "562111": "Solid Waste Collection",
            "621610": "Home Health Care Services",
            "624120": "Services for Elderly / Disabled",
            "722513": "Limited-Service Restaurants",
        },
    },
    "tier3": {
        "description": "Opportunistic — asset-heavy with turnaround potential",
        "codes": {
            "236220": "Commercial Building Construction",
            "531120": "Lessors of Nonresidential Buildings",
            "532120": "Truck / Trailer Rental",
            "441110": "New Car Dealers",
        },
    },
}


class MerlinAgent:
    """M&A acquisition intelligence agent."""

    # Scoring dimensions and weights
    SCORING_WEIGHTS = {
        "revenue_quality": 0.18,
        "margin_profile": 0.15,
        "owner_dependency": 0.14,
        "customer_concentration": 0.12,
        "growth_trajectory": 0.10,
        "defensibility": 0.10,
        "workforce_stability": 0.11,
        "asset_quality": 0.10,
    }

    def __init__(self):
        self.analysis_cache = {}

    # ------------------------------------------------------------------ #
    #  TARGET SCORING (8 dimensions)                                      #
    # ------------------------------------------------------------------ #

    def score_target(self, target: dict) -> dict:
        """
        Score an acquisition target on 8 weighted dimensions (0-100 each).

        target: {name, revenue, ebitda, ebitda_margin, revenue_growth,
                 top_customer_pct, owner_involved, employee_tenure_avg,
                 recurring_revenue_pct, asset_age_years, patents, contracts,
                 sector, naics}
        """
        scores = {}

        # 1. Revenue quality — recurring revenue, diversification
        recurring_pct = target.get("recurring_revenue_pct", 0.20)
        revenue = target.get("revenue", 0)
        scores["revenue_quality"] = min(100, recurring_pct * 100 + (10 if revenue > 5_000_000 else 0))

        # 2. Margin profile
        margin = target.get("ebitda_margin", 0.10)
        if margin >= 0.25:
            scores["margin_profile"] = 95
        elif margin >= 0.18:
            scores["margin_profile"] = 80
        elif margin >= 0.12:
            scores["margin_profile"] = 60
        elif margin >= 0.08:
            scores["margin_profile"] = 40
        else:
            scores["margin_profile"] = 20

        # 3. Owner dependency (lower is better)
        owner_involved = target.get("owner_involved", True)
        if not owner_involved:
            scores["owner_dependency"] = 90
        else:
            mgmt_depth = target.get("management_depth", 1)
            scores["owner_dependency"] = min(80, 30 + mgmt_depth * 15)

        # 4. Customer concentration (lower top-customer % is better)
        top_cust = target.get("top_customer_pct", 0.30)
        scores["customer_concentration"] = max(10, 100 - top_cust * 200)

        # 5. Growth trajectory
        growth = target.get("revenue_growth", 0.0)
        if growth >= 0.15:
            scores["growth_trajectory"] = 90
        elif growth >= 0.08:
            scores["growth_trajectory"] = 70
        elif growth >= 0.02:
            scores["growth_trajectory"] = 50
        elif growth >= -0.05:
            scores["growth_trajectory"] = 30
        else:
            scores["growth_trajectory"] = 15

        # 6. Defensibility — patents, long-term contracts, licenses
        patents = target.get("patents", 0)
        contracts = target.get("contracts", 0)
        licenses = target.get("licenses", 0)
        def_score = min(100, patents * 15 + contracts * 10 + licenses * 12 + 20)
        scores["defensibility"] = def_score

        # 7. Workforce stability
        tenure_avg = target.get("employee_tenure_avg", 3.0)
        turnover = target.get("turnover_rate", 0.20)
        scores["workforce_stability"] = min(100, tenure_avg * 12 + (1 - turnover) * 40)

        # 8. Asset quality
        asset_age = target.get("asset_age_years", 5)
        if asset_age <= 3:
            scores["asset_quality"] = 85
        elif asset_age <= 7:
            scores["asset_quality"] = 65
        elif asset_age <= 12:
            scores["asset_quality"] = 45
        else:
            scores["asset_quality"] = 25

        # Weighted composite
        composite = sum(
            scores[dim] * weight
            for dim, weight in self.SCORING_WEIGHTS.items()
        )

        # NAICS tier bonus
        naics = target.get("naics", "")
        tier = "none"
        tier_bonus = 0
        for t_name, t_data in NAICS_PRIORITY.items():
            if naics in t_data["codes"]:
                tier = t_name
                tier_bonus = {"tier1": 8, "tier2": 4, "tier3": 1}.get(t_name, 0)
                break

        composite = min(100, composite + tier_bonus)

        # Recommendation
        if composite >= 75:
            recommendation = "STRONG_BUY"
        elif composite >= 60:
            recommendation = "BUY"
        elif composite >= 45:
            recommendation = "REVIEW"
        else:
            recommendation = "PASS"

        return {
            "target_name": target.get("name", "Unknown"),
            "composite_score": round(composite, 1),
            "dimension_scores": {k: round(v, 1) for k, v in scores.items()},
            "naics_tier": tier,
            "tier_bonus": tier_bonus,
            "recommendation": recommendation,
            "timestamp": datetime.utcnow().isoformat(),
        }

    # ------------------------------------------------------------------ #
    #  GAME THEORY INTEGRATION                                            #
    # ------------------------------------------------------------------ #

    def run_game_theory(self, target: dict, market_data: dict = None,
                        competitors: list = None, history: list = None) -> dict:
        """Run full 3-level game theory analysis on a target."""
        if game_engine is None:
            return {"error": "game_theory.engine not available"}

        secondary = {
            "market_data": market_data or {"signals": {}},
            "competitors": competitors or [],
            "nest_params": {"max_multiple": 8.0, "synergy_pct": 0.12, "cost_of_capital": 0.10},
        }

        result = game_engine.run_full_analysis(
            analysis_type="acquisition",
            primary_data=target,
            secondary_data=secondary,
            history=history or [],
        )

        # Record on chain
        if chain is not None:
            try:
                chain.record_ma_analysis(
                    company_name=target.get("name", "unknown"),
                    analysis_data={"composite": result.get("synthesis", {}).get("composite_score")},
                    game_theory_result=result.get("synthesis", {}).get("recommendation"),
                    level="full",
                )
            except Exception:
                pass

        return result

    # ------------------------------------------------------------------ #
    #  BUSINESS PLAN (Claude API)                                         #
    # ------------------------------------------------------------------ #

    def build_business_plan(self, target: dict, score_result: dict,
                             game_theory_result: dict = None) -> dict:
        """Generate acquisition business plan via Claude API."""
        if ask_claude is None:
            return {"error": "Claude API not available", "plan": None}

        prompt = f"""You are MERLIN, NEST's M&A intelligence agent. Build a concise acquisition
business plan for the following target:

Company: {target.get('name', 'Unknown')}
Sector: {target.get('sector', 'Unknown')}
Revenue: ${target.get('revenue', 0):,.0f}
EBITDA: ${target.get('ebitda', 0):,.0f}
EBITDA Margin: {target.get('ebitda_margin', 0):.1%}

Acquisition Score: {score_result.get('composite_score', 'N/A')}/100
Recommendation: {score_result.get('recommendation', 'N/A')}

Game Theory Recommendation: {game_theory_result.get('synthesis', {}).get('recommendation', 'N/A') if game_theory_result else 'N/A'}

Provide:
1. Executive Summary (3 sentences)
2. Investment Thesis (3 bullet points)
3. Value Creation Plan (100-day, Year 1, Year 2-3)
4. Key Risks and Mitigants (top 3)
5. Recommended Deal Structure (purchase price range, financing mix, earnout terms)
"""
        try:
            response = ask_claude(prompt, system="You are MERLIN, a sharp M&A analyst. Be concise and specific.")
            return {"plan": response, "generated_at": datetime.utcnow().isoformat()}
        except Exception as e:
            return {"error": str(e), "plan": None}

    # ------------------------------------------------------------------ #
    #  IRR MODELING (3x3 scenario matrix)                                 #
    # ------------------------------------------------------------------ #

    def model_irr(self, target: dict, hold_years: int = 5) -> dict:
        """
        3x3 IRR matrix: entry multiple x exit multiple x growth rate.

        Rows: entry multiple (low, base, high)
        Cols: exit multiple (contraction, stable, expansion)
        Layers: growth (bear, base, bull)
        """
        ebitda = target.get("ebitda", 1_000_000)
        growth_scenarios = {"bear": 0.02, "base": 0.07, "bull": 0.12}
        entry_multiples = {"low": 4.5, "base": 6.0, "high": 7.5}
        exit_multiples = {"contraction": 4.0, "stable": 6.0, "expansion": 8.0}

        matrix = {}
        for g_label, g_rate in growth_scenarios.items():
            matrix[g_label] = {}
            for e_label, entry_mult in entry_multiples.items():
                matrix[g_label][e_label] = {}
                entry_price = ebitda * entry_mult
                for x_label, exit_mult in exit_multiples.items():
                    future_ebitda = ebitda * ((1 + g_rate) ** hold_years)
                    exit_price = future_ebitda * exit_mult
                    # Add cumulative free cash flow (assume 60% of EBITDA)
                    total_fcf = sum(
                        ebitda * ((1 + g_rate) ** y) * 0.60
                        for y in range(1, hold_years + 1)
                    )
                    total_return = exit_price + total_fcf
                    if entry_price > 0:
                        irr = (total_return / entry_price) ** (1 / hold_years) - 1
                    else:
                        irr = 0.0
                    moic = total_return / entry_price if entry_price > 0 else 0.0

                    matrix[g_label][e_label][x_label] = {
                        "irr": round(irr, 4),
                        "irr_pct": f"{irr:.1%}",
                        "moic": round(moic, 2),
                        "entry_price": round(entry_price, 0),
                        "exit_price": round(exit_price, 0),
                    }

        # Find base case
        base_case = matrix["base"]["base"]["stable"]

        return {
            "target_name": target.get("name", "Unknown"),
            "hold_years": hold_years,
            "matrix": matrix,
            "base_case_irr": base_case["irr_pct"],
            "base_case_moic": base_case["moic"],
            "meets_hurdle": base_case["irr"] >= 0.20,
            "hurdle_rate": "20%",
        }

    # ------------------------------------------------------------------ #
    #  EDGAR SCANNER                                                      #
    # ------------------------------------------------------------------ #

    def scan_edgar_for_targets(self, naics_codes: list = None, min_revenue: float = 2_000_000,
                                max_revenue: float = 50_000_000) -> dict:
        """
        Scan EDGAR (via Jimmy Lee service) for acquisition targets by NAICS.
        Falls back to synthetic data if service unavailable.
        """
        if naics_codes is None:
            naics_codes = list(NAICS_PRIORITY["tier1"]["codes"].keys())

        targets = []

        if jimmy_lee is not None:
            try:
                for code in naics_codes:
                    results = jimmy_lee.search_companies(
                        naics=code,
                        min_revenue=min_revenue,
                        max_revenue=max_revenue,
                    )
                    if results:
                        targets.extend(results)
            except Exception:
                pass

        # If no external results, generate synthetic scan results
        if not targets:
            sectors = ["Landscaping", "HVAC", "Plumbing", "Janitorial", "Auto Repair",
                        "Electrical", "Waste Collection", "Home Health"]
            for i, code in enumerate(naics_codes[:8]):
                sector = sectors[i % len(sectors)]
                rev = random.uniform(min_revenue, max_revenue)
                margin = random.uniform(0.08, 0.28)
                targets.append({
                    "name": f"{sector} Co #{i + 1}",
                    "naics": code,
                    "sector": sector,
                    "revenue": round(rev, 0),
                    "ebitda": round(rev * margin, 0),
                    "ebitda_margin": round(margin, 3),
                    "ev_usd": round(rev * margin * random.uniform(4, 7), 0),
                    "source": "synthetic_scan",
                })

        return {
            "scan_date": datetime.utcnow().isoformat(),
            "naics_codes_searched": naics_codes,
            "revenue_range": [min_revenue, max_revenue],
            "targets_found": len(targets),
            "targets": targets,
        }

    # ------------------------------------------------------------------ #
    #  FULL ANALYSIS PIPELINE                                             #
    # ------------------------------------------------------------------ #

    def run_full_analysis(self, target: dict, market_data: dict = None,
                           competitors: list = None, history: list = None,
                           include_business_plan: bool = False) -> dict:
        """
        Orchestrate complete analysis: score + game theory + IRR + optional plan.
        """
        result = {
            "target": target.get("name", "Unknown"),
            "analysis_started": datetime.utcnow().isoformat(),
        }

        # Step 1: Score
        score = self.score_target(target)
        result["scoring"] = score

        # Step 2: Game theory
        gt = self.run_game_theory(target, market_data, competitors, history)
        result["game_theory"] = gt

        # Step 3: IRR model
        irr = self.model_irr(target)
        result["irr_model"] = irr

        # Step 4: Business plan (optional, requires Claude API)
        if include_business_plan:
            plan = self.build_business_plan(target, score, gt)
            result["business_plan"] = plan

        # Composite verdict
        score_val = score.get("composite_score", 50)
        gt_composite = gt.get("synthesis", {}).get("composite_score", 0.5)
        irr_meets = irr.get("meets_hurdle", False)

        if score_val >= 70 and gt_composite >= 0.55 and irr_meets:
            verdict = "STRONG_PROCEED"
        elif score_val >= 55 and gt_composite >= 0.40:
            verdict = "PROCEED_WITH_DILIGENCE"
        elif score_val >= 40:
            verdict = "FURTHER_REVIEW"
        else:
            verdict = "PASS"

        result["verdict"] = verdict
        result["analysis_completed"] = datetime.utcnow().isoformat()

        # Cache
        self.analysis_cache[target.get("name", "unknown")] = result

        # Record on chain
        if chain is not None:
            try:
                chain.record_ma_analysis(
                    company_name=target.get("name", "unknown"),
                    analysis_data={"score": score_val, "irr_meets_hurdle": irr_meets},
                    game_theory_result=verdict,
                    level="full_pipeline",
                )
            except Exception:
                pass

        return result


merlin = MerlinAgent()

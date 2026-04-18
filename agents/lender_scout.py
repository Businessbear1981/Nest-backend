"""
LenderScoutAgent — automated lender matching, scoring, and outreach.

Responsibilities:
  - Score lenders across 10 weighted dimensions
  - Search and filter lender database
  - Generate personalized outreach via Claude API
  - Run full lender-match pipeline with game theory + chain recording
"""
from datetime import datetime

# Safe imports
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


# Seed lender database
SEED_LENDERS = [
    {
        "id": "lender_001",
        "name": "Pacific Western Capital",
        "type": "regional_bank",
        "base_rate": 0.068,
        "cost_of_funds": 0.042,
        "min_deal": 1_000_000,
        "max_deal": 25_000_000,
        "sectors": ["services", "light_industrial", "healthcare"],
        "max_ltv": 0.75,
        "min_dscr": 1.20,
        "avg_close_days": 45,
        "risk_appetite": 0.6,
        "deal_volume_ytd": 12,
        "portfolio_stress": 0.02,
        "sba_preferred": True,
        "geography": ["CA", "OR", "WA", "AZ"],
    },
    {
        "id": "lender_002",
        "name": "Heartland Business Credit",
        "type": "cdfi",
        "base_rate": 0.072,
        "cost_of_funds": 0.038,
        "min_deal": 500_000,
        "max_deal": 10_000_000,
        "sectors": ["services", "construction", "retail"],
        "max_ltv": 0.80,
        "min_dscr": 1.15,
        "avg_close_days": 35,
        "risk_appetite": 0.7,
        "deal_volume_ytd": 8,
        "portfolio_stress": 0.01,
        "sba_preferred": True,
        "geography": ["TX", "OK", "AR", "LA", "MO"],
    },
    {
        "id": "lender_003",
        "name": "Summit Acquisition Finance",
        "type": "specialty_finance",
        "base_rate": 0.085,
        "cost_of_funds": 0.055,
        "min_deal": 5_000_000,
        "max_deal": 75_000_000,
        "sectors": ["services", "manufacturing", "distribution", "healthcare"],
        "max_ltv": 0.70,
        "min_dscr": 1.30,
        "avg_close_days": 60,
        "risk_appetite": 0.5,
        "deal_volume_ytd": 18,
        "portfolio_stress": 0.04,
        "sba_preferred": False,
        "geography": ["national"],
    },
    {
        "id": "lender_004",
        "name": "Founders Bridge Capital",
        "type": "mezzanine",
        "base_rate": 0.120,
        "cost_of_funds": 0.070,
        "min_deal": 2_000_000,
        "max_deal": 30_000_000,
        "sectors": ["services", "tech_enabled", "healthcare", "consumer"],
        "max_ltv": 0.85,
        "min_dscr": 1.10,
        "avg_close_days": 30,
        "risk_appetite": 0.8,
        "deal_volume_ytd": 6,
        "portfolio_stress": 0.03,
        "sba_preferred": False,
        "geography": ["national"],
    },
    {
        "id": "lender_005",
        "name": "Community First Bank",
        "type": "community_bank",
        "base_rate": 0.062,
        "cost_of_funds": 0.035,
        "min_deal": 250_000,
        "max_deal": 5_000_000,
        "sectors": ["services", "retail", "food_service", "construction"],
        "max_ltv": 0.80,
        "min_dscr": 1.25,
        "avg_close_days": 40,
        "risk_appetite": 0.5,
        "deal_volume_ytd": 4,
        "portfolio_stress": 0.01,
        "sba_preferred": True,
        "geography": ["TX", "NM"],
    },
]


class LenderScoutAgent:
    """Automated lender matching and outreach agent."""

    SCORING_WEIGHTS = {
        "rate_competitiveness": 0.18,
        "deal_size_fit": 0.14,
        "sector_alignment": 0.13,
        "ltv_flexibility": 0.10,
        "dscr_flexibility": 0.08,
        "close_speed": 0.10,
        "risk_appetite_match": 0.09,
        "geographic_fit": 0.06,
        "sba_capability": 0.05,
        "relationship_value": 0.07,
    }

    def __init__(self):
        self.lender_db = list(SEED_LENDERS)
        self.match_history = []

    # ------------------------------------------------------------------ #
    #  LENDER SCORING (10 dimensions)                                     #
    # ------------------------------------------------------------------ #

    def score_lender(self, lender: dict, deal: dict) -> dict:
        """
        Score a lender against a specific deal across 10 dimensions (0-100).

        deal: {amount, ltv, dscr, term_months, sector, geography, sba_eligible, urgency}
        """
        scores = {}
        deal_amount = deal.get("amount", 5_000_000)
        deal_ltv = deal.get("ltv", 0.70)
        deal_dscr = deal.get("dscr", 1.25)
        deal_sector = deal.get("sector", "services")
        deal_geo = deal.get("geography", "TX")
        deal_urgency = deal.get("urgency", "normal")  # fast, normal, flexible

        # 1. Rate competitiveness (lower = better)
        rate = lender.get("base_rate", 0.08)
        if rate <= 0.055:
            scores["rate_competitiveness"] = 95
        elif rate <= 0.070:
            scores["rate_competitiveness"] = 80
        elif rate <= 0.085:
            scores["rate_competitiveness"] = 60
        elif rate <= 0.100:
            scores["rate_competitiveness"] = 40
        else:
            scores["rate_competitiveness"] = 20

        # 2. Deal size fit
        min_d = lender.get("min_deal", 0)
        max_d = lender.get("max_deal", float("inf"))
        if min_d <= deal_amount <= max_d:
            # Sweet spot: middle 50% of range
            mid = (min_d + max_d) / 2
            rng = max_d - min_d
            dist = abs(deal_amount - mid) / (rng / 2) if rng > 0 else 0
            scores["deal_size_fit"] = max(50, 95 - dist * 30)
        else:
            scores["deal_size_fit"] = 10

        # 3. Sector alignment
        lender_sectors = lender.get("sectors", [])
        if deal_sector in lender_sectors or "services" in lender_sectors:
            scores["sector_alignment"] = 90
        elif any(s in deal_sector for s in lender_sectors):
            scores["sector_alignment"] = 60
        else:
            scores["sector_alignment"] = 25

        # 4. LTV flexibility
        max_ltv = lender.get("max_ltv", 0.70)
        if max_ltv >= deal_ltv + 0.10:
            scores["ltv_flexibility"] = 90
        elif max_ltv >= deal_ltv:
            scores["ltv_flexibility"] = 70
        elif max_ltv >= deal_ltv - 0.05:
            scores["ltv_flexibility"] = 40
        else:
            scores["ltv_flexibility"] = 10

        # 5. DSCR flexibility
        min_dscr = lender.get("min_dscr", 1.25)
        if min_dscr <= deal_dscr - 0.15:
            scores["dscr_flexibility"] = 90
        elif min_dscr <= deal_dscr:
            scores["dscr_flexibility"] = 70
        elif min_dscr <= deal_dscr + 0.10:
            scores["dscr_flexibility"] = 40
        else:
            scores["dscr_flexibility"] = 15

        # 6. Close speed
        avg_days = lender.get("avg_close_days", 60)
        if deal_urgency == "fast":
            target_days = 30
        elif deal_urgency == "flexible":
            target_days = 90
        else:
            target_days = 60

        if avg_days <= target_days * 0.6:
            scores["close_speed"] = 95
        elif avg_days <= target_days:
            scores["close_speed"] = 75
        elif avg_days <= target_days * 1.3:
            scores["close_speed"] = 50
        else:
            scores["close_speed"] = 25

        # 7. Risk appetite match
        risk = lender.get("risk_appetite", 0.5)
        deal_risk = 0.5 + (deal_ltv - 0.65) * 2  # higher LTV = riskier
        diff = abs(risk - deal_risk)
        scores["risk_appetite_match"] = max(20, 90 - diff * 150)

        # 8. Geographic fit
        geo = lender.get("geography", [])
        if "national" in geo or deal_geo in geo:
            scores["geographic_fit"] = 90
        else:
            scores["geographic_fit"] = 20

        # 9. SBA capability
        sba_eligible = deal.get("sba_eligible", False)
        sba_pref = lender.get("sba_preferred", False)
        if sba_eligible and sba_pref:
            scores["sba_capability"] = 95
        elif not sba_eligible:
            scores["sba_capability"] = 60  # neutral
        else:
            scores["sba_capability"] = 30

        # 10. Relationship value (repeat lenders score higher)
        past_deals = sum(
            1 for h in self.match_history
            if h.get("lender_id") == lender.get("id")
        )
        scores["relationship_value"] = min(100, 40 + past_deals * 20)

        # Weighted composite
        composite = sum(
            scores[dim] * weight
            for dim, weight in self.SCORING_WEIGHTS.items()
        )

        return {
            "lender_id": lender.get("id"),
            "lender_name": lender.get("name"),
            "composite_score": round(composite, 1),
            "dimension_scores": {k: round(v, 1) for k, v in scores.items()},
            "base_rate": lender.get("base_rate"),
            "lender_type": lender.get("type"),
        }

    # ------------------------------------------------------------------ #
    #  SEARCH & FILTER                                                    #
    # ------------------------------------------------------------------ #

    def search_lenders(self, deal: dict, top_n: int = 5) -> dict:
        """Score all lenders against a deal and return top N."""
        scored = []
        for lender in self.lender_db:
            result = self.score_lender(lender, deal)
            scored.append(result)

        scored.sort(key=lambda x: x["composite_score"], reverse=True)
        top = scored[:top_n]

        return {
            "deal_summary": {
                "amount": deal.get("amount"),
                "sector": deal.get("sector"),
                "geography": deal.get("geography"),
            },
            "total_lenders_scored": len(scored),
            "top_matches": top,
            "best_rate": min((s["base_rate"] for s in scored if s["base_rate"]), default=None),
            "timestamp": datetime.utcnow().isoformat(),
        }

    # ------------------------------------------------------------------ #
    #  OUTREACH GENERATION (Claude API)                                   #
    # ------------------------------------------------------------------ #

    def generate_lender_outreach(self, lender: dict, deal: dict, score_result: dict) -> dict:
        """Generate personalized lender outreach email via Claude API."""
        if ask_claude is None:
            return {"error": "Claude API not available", "outreach": None}

        prompt = f"""You are LenderScout, NEST's automated lender outreach agent.
Write a concise, professional outreach email to a lender for a potential deal.

Lender: {lender.get('name')}
Lender Type: {lender.get('type')}
Match Score: {score_result.get('composite_score')}/100

Deal Details:
- Amount: ${deal.get('amount', 0):,.0f}
- Sector: {deal.get('sector', 'services')}
- LTV: {deal.get('ltv', 0.70):.0%}
- DSCR: {deal.get('dscr', 1.25):.2f}x
- Geography: {deal.get('geography', 'TX')}

Write a 150-word email that:
1. References the lender's strengths relevant to this deal
2. Highlights the deal's key metrics
3. Proposes a brief introductory call
4. Is professional but not stuffy

Sign as "NEST Capital | Acquisition Finance"
"""
        try:
            response = ask_claude(prompt, system="You write concise, professional lender outreach. No fluff.")
            return {"outreach": response, "generated_at": datetime.utcnow().isoformat()}
        except Exception as e:
            return {"error": str(e), "outreach": None}

    # ------------------------------------------------------------------ #
    #  FULL PIPELINE                                                      #
    # ------------------------------------------------------------------ #

    def run(self, deal: dict, generate_outreach: bool = False) -> dict:
        """
        Full lender-match pipeline:
        1. Search & score lenders
        2. Run game theory (Bertrand competition)
        3. Record matches on chain
        4. Optionally generate outreach
        """
        result = {
            "deal": deal,
            "pipeline_started": datetime.utcnow().isoformat(),
        }

        # Step 1: Search
        search = self.search_lenders(deal, top_n=5)
        result["search_results"] = search

        # Step 2: Game theory — Bertrand competition among top lenders
        if game_engine is not None and search["top_matches"]:
            gt_lenders = []
            for match in search["top_matches"][:4]:
                lender_full = next(
                    (l for l in self.lender_db if l["id"] == match["lender_id"]), {}
                )
                gt_lenders.append({
                    "id": match["lender_id"],
                    "name": match["lender_name"],
                    "base_rate": match["base_rate"],
                    "cost_of_funds": lender_full.get("cost_of_funds", 0.04),
                    "risk_appetite": lender_full.get("risk_appetite", 0.5),
                })

            gt_result = game_engine.run_full_analysis(
                analysis_type="lending",
                primary_data=deal,
                secondary_data={"lenders": gt_lenders, "primary_lender": gt_lenders[0] if gt_lenders else {}},
            )
            result["game_theory"] = gt_result
        else:
            result["game_theory"] = {"note": "game theory engine not available"}

        # Step 3: Record on chain
        if chain is not None:
            for match in search["top_matches"][:3]:
                try:
                    nash_score = result.get("game_theory", {}).get("synthesis", {}).get("composite_score", 0)
                    chain.record_lender_match(
                        deal_id=deal.get("deal_id", "unknown"),
                        lender_id=match["lender_id"],
                        match_score=match["composite_score"],
                        nash_result={"composite": nash_score},
                    )
                except Exception:
                    pass

        # Step 4: Outreach
        if generate_outreach and search["top_matches"]:
            best_match = search["top_matches"][0]
            best_lender = next(
                (l for l in self.lender_db if l["id"] == best_match["lender_id"]), {}
            )
            outreach = self.generate_lender_outreach(best_lender, deal, best_match)
            result["outreach"] = outreach

        # Record history
        for match in search["top_matches"]:
            self.match_history.append({
                "lender_id": match["lender_id"],
                "deal_id": deal.get("deal_id"),
                "score": match["composite_score"],
                "timestamp": datetime.utcnow().isoformat(),
            })

        result["pipeline_completed"] = datetime.utcnow().isoformat()
        return result


lender_scout = LenderScoutAgent()

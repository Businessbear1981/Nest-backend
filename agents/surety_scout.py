"""SuretyScout — Insurance Surety Platform.

Identifies best insurance/surety partners, calculates surety premium costs,
and generates outreach packages to providers.

NEST's surety structure is the core credit enhancement that enables investment-grade
ratings on construction-phase bonds. This agent automates the surety sourcing process.
"""
from datetime import datetime

try:
    from agents._claude import complete, ClaudeUnavailable
    from services.jimmy_lee import JIMMY_LEE_SYSTEM_PROMPT
except ImportError:
    complete = None
    JIMMY_LEE_SYSTEM_PROMPT = ""
    ClaudeUnavailable = Exception


# ── Surety Provider Database ────────────────────────────────────

SURETY_PROVIDERS = [
    {
        "id": "hylant",
        "name": "Hylant Insurance",
        "type": "surety_broker",
        "specialties": ["construction_surety", "commercial_surety", "cash_collateral_sbloc"],
        "min_bond_face_usd": 5_000_000,
        "max_bond_face_usd": 500_000_000,
        "typical_premium_bps": 100,  # 1.0% of face
        "asset_types": ["senior_living", "mixed_use", "industrial", "multifamily", "office"],
        "states": ["FL", "TX", "CA", "NY", "WA", "OR", "GA", "NC", "SC", "OH", "PA"],
        "products": ["performance_bond", "payment_bond", "bid_bond", "maintenance_bond", "cash_surety_sbloc"],
        "rating_minimum": "BBB_minus",
        "turnaround_days": 21,
        "relationship_status": "partner",
        "contact": {"name": "Hylant Surety Team", "email": "surety@hylant.com"},
        "strengths": ["NEST's primary surety partner", "Deep construction expertise", "Cash collateral SBLOC specialist"],
    },
    {
        "id": "alliant",
        "name": "Alliant Insurance Services",
        "type": "insurance_broker",
        "specialties": ["insurable_risk_assessment", "builders_risk", "environmental_liability"],
        "min_bond_face_usd": 10_000_000,
        "max_bond_face_usd": 1_000_000_000,
        "typical_premium_bps": 125,
        "asset_types": ["senior_living", "mixed_use", "industrial", "multifamily"],
        "states": ["FL", "TX", "CA", "NY", "WA", "OR"],
        "products": ["insurable_risk_report", "builders_risk", "general_liability", "environmental", "d_and_o"],
        "rating_minimum": "BBB_minus",
        "turnaround_days": 30,
        "relationship_status": "target",
        "contact": {"name": "Alliant Construction Practice", "email": "construction@alliant.com"},
        "strengths": ["Tier 1 broker", "Comprehensive risk assessment", "Large-scale project expertise"],
    },
    {
        "id": "marsh",
        "name": "Marsh McLennan",
        "type": "insurance_broker",
        "specialties": ["insurable_risk_assessment", "surety", "catastrophic_risk"],
        "min_bond_face_usd": 25_000_000,
        "max_bond_face_usd": 5_000_000_000,
        "typical_premium_bps": 115,
        "asset_types": ["senior_living", "mixed_use", "industrial", "office", "retail"],
        "states": ["FL", "TX", "CA", "NY", "WA", "IL", "GA"],
        "products": ["surety_bond", "builders_risk", "professional_liability", "cyber", "political_risk"],
        "rating_minimum": "A",
        "turnaround_days": 28,
        "relationship_status": "cold",
        "contact": {"name": "Marsh Construction Group"},
        "strengths": ["Global scale", "Capital markets expertise", "Parametric insurance"],
    },
    {
        "id": "aon",
        "name": "Aon Risk Solutions",
        "type": "insurance_broker",
        "specialties": ["construction_risk", "surety", "credit_risk_transfer"],
        "min_bond_face_usd": 20_000_000,
        "max_bond_face_usd": 2_000_000_000,
        "typical_premium_bps": 120,
        "asset_types": ["senior_living", "industrial", "multifamily", "office"],
        "states": ["FL", "TX", "CA", "NY", "WA", "OR", "CO"],
        "products": ["surety_bond", "credit_default_swap", "residual_value_insurance", "builders_risk"],
        "rating_minimum": "BBB",
        "turnaround_days": 25,
        "relationship_status": "cold",
        "contact": {"name": "Aon Construction Services"},
        "strengths": ["CDS structuring capability", "Residual value insurance", "Analytics-driven pricing"],
    },
    {
        "id": "zurich",
        "name": "Zurich North America (Surety)",
        "type": "surety_underwriter",
        "specialties": ["contract_surety", "commercial_surety"],
        "min_bond_face_usd": 10_000_000,
        "max_bond_face_usd": 750_000_000,
        "typical_premium_bps": 90,
        "asset_types": ["senior_living", "industrial", "multifamily"],
        "states": ["FL", "TX", "CA", "NY", "WA"],
        "products": ["performance_bond", "payment_bond", "supply_bond"],
        "rating_minimum": "BBB",
        "turnaround_days": 21,
        "relationship_status": "cold",
        "contact": {"name": "Zurich Surety"},
        "strengths": ["Direct underwriter", "Competitive pricing", "Fast turnaround"],
    },
    {
        "id": "swiss_re",
        "name": "Swiss Re Corporate Solutions",
        "type": "reinsurer",
        "specialties": ["credit_enhancement", "parametric_insurance", "catastrophic_risk"],
        "min_bond_face_usd": 50_000_000,
        "max_bond_face_usd": 10_000_000_000,
        "typical_premium_bps": 75,
        "asset_types": ["senior_living", "industrial", "multifamily", "office"],
        "states": ["FL", "TX", "CA", "NY"],
        "products": ["credit_wrap", "parametric_hurricane", "residual_value_guarantee", "excess_of_loss"],
        "rating_minimum": "A",
        "turnaround_days": 45,
        "relationship_status": "cold",
        "contact": {"name": "Swiss Re Capital Markets"},
        "strengths": ["Reinsurance-backed capacity", "Parametric products", "Investment grade wrap specialist"],
    },
]

# ── Surety Premium Calculation ──────────────────────────────────

# Base premium rates by rating target and product
PREMIUM_RATES = {
    "cash_surety_sbloc": {
        "AAA": 50, "AA": 65, "A": 85, "BBB_plus": 100, "BBB": 120, "BBB_minus": 150,
    },
    "performance_bond": {
        "A": 100, "BBB_plus": 125, "BBB": 150, "BBB_minus": 200,
    },
    "lc": {
        "A": 75, "BBB_plus": 100, "BBB": 125, "BBB_minus": 175,
    },
    "parametric": {
        "A": 60, "BBB_plus": 80, "BBB": 100, "BBB_minus": 130,
    },
}

# Risk adjustments by asset type
ASSET_RISK_ADJUSTMENTS = {
    "senior_living": 1.15,     # Higher — operational complexity
    "multifamily": 1.0,        # Baseline
    "industrial": 0.90,        # Lower — simpler operations
    "mixed_use": 1.10,         # Slightly higher
    "office": 1.05,
    "retail": 1.20,            # Higher — market risk
}

# State risk adjustments (hurricane, regulatory)
STATE_RISK_ADJUSTMENTS = {
    "FL": 1.25,  # Hurricane + wind
    "TX": 1.10,  # Hurricane coast
    "CA": 1.15,  # Earthquake + wildfire
    "WA": 0.95,  # Low natural hazard
    "OR": 0.95,
    "NY": 1.05,
    "GA": 1.05,
    "NC": 1.10,
}


class SuretyScoutAgent:
    """Finds, scores, and costs surety providers for NEST deals."""

    def calculate_premium(self, deal: dict) -> dict:
        """Calculate surety premium cost for a deal.

        Returns detailed premium breakdown with multiple product options.
        """
        bond_face = deal.get("bond_face_usd", 100_000_000)
        rating_target = deal.get("rating_target", "BBB")
        asset_type = deal.get("asset_type", "senior_living")
        state = deal.get("state", "FL")
        duration_years = deal.get("duration_years", 5)
        dscr = deal.get("dscr", 1.5)
        ltv = deal.get("ltv_pct", 65)

        asset_adj = ASSET_RISK_ADJUSTMENTS.get(asset_type, 1.0)
        state_adj = STATE_RISK_ADJUSTMENTS.get(state, 1.0)

        # Credit quality adjustment
        credit_adj = 1.0
        if dscr >= 2.0 and ltv <= 55:
            credit_adj = 0.85  # strong credit = lower premium
        elif dscr < 1.5 or ltv > 70:
            credit_adj = 1.25  # weak credit = higher premium

        # Duration adjustment (longer = more expensive per year)
        duration_adj = 1.0 + (duration_years - 3) * 0.03

        options = {}
        for product, rates in PREMIUM_RATES.items():
            base_bps = rates.get(rating_target, rates.get("BBB", 120))
            adjusted_bps = base_bps * asset_adj * state_adj * credit_adj * duration_adj
            annual_premium = bond_face * adjusted_bps / 10000
            total_premium = annual_premium * duration_years

            options[product] = {
                "product": product,
                "base_rate_bps": base_bps,
                "adjusted_rate_bps": round(adjusted_bps),
                "annual_premium_usd": round(annual_premium),
                "total_premium_usd": round(total_premium),
                "pct_of_face": round(adjusted_bps / 100, 3),
                "adjustments": {
                    "asset_type": f"{asset_adj:.2f}x ({asset_type})",
                    "state": f"{state_adj:.2f}x ({state})",
                    "credit_quality": f"{credit_adj:.2f}x (DSCR={dscr}, LTV={ltv}%)",
                    "duration": f"{duration_adj:.2f}x ({duration_years}yr)",
                },
            }

        # Recommend best option
        cheapest = min(options.values(), key=lambda x: x["total_premium_usd"])
        recommended = "cash_surety_sbloc" if rating_target in ("A", "BBB_plus") else "performance_bond"

        return {
            "bond_face_usd": bond_face,
            "rating_target": rating_target,
            "options": options,
            "recommended_product": recommended,
            "recommended_premium": options.get(recommended, cheapest),
            "cheapest_option": cheapest["product"],
            "lc_phase_savings": self._lc_phase_projection(bond_face, options),
        }

    def _lc_phase_projection(self, bond_face: float, options: dict) -> dict:
        """Project savings when NEST transitions from surety to LC-dominant."""
        surety_annual = options.get("cash_surety_sbloc", {}).get("annual_premium_usd", 0)
        lc_annual = options.get("lc", {}).get("annual_premium_usd", 0)
        savings = surety_annual - lc_annual
        return {
            "current_surety_annual": surety_annual,
            "lc_phase_annual": lc_annual,
            "annual_savings": savings,
            "note": "LC phase reached when AUM >$40M — surety premium drops significantly",
        }

    def match_providers(self, deal: dict) -> list:
        """Score and rank surety providers for a deal."""
        bond_face = deal.get("bond_face_usd", 100_000_000)
        asset_type = deal.get("asset_type", "senior_living")
        state = deal.get("state", "FL")
        rating = deal.get("rating_target", "BBB")

        scored = []
        for provider in SURETY_PROVIDERS:
            score = 0

            # Size fit (0-25)
            if provider["min_bond_face_usd"] <= bond_face <= provider["max_bond_face_usd"]:
                score += 25
            elif bond_face < provider["min_bond_face_usd"]:
                score += 5

            # Asset type match (0-20)
            if asset_type in provider["asset_types"]:
                score += 20

            # Geography (0-15)
            if state in provider["states"]:
                score += 15

            # Relationship (0-20)
            rel_scores = {"partner": 20, "existing": 15, "warm": 10, "target": 8, "cold": 3}
            score += rel_scores.get(provider["relationship_status"], 3)

            # Premium competitiveness (0-10)
            premium = provider["typical_premium_bps"]
            if premium <= 90:
                score += 10
            elif premium <= 110:
                score += 7
            elif premium <= 130:
                score += 4
            else:
                score += 2

            # Speed (0-10)
            if provider["turnaround_days"] <= 21:
                score += 10
            elif provider["turnaround_days"] <= 30:
                score += 6
            else:
                score += 3

            scored.append({
                "provider_id": provider["id"],
                "provider_name": provider["name"],
                "type": provider["type"],
                "match_score": score,
                "typical_premium_bps": provider["typical_premium_bps"],
                "turnaround_days": provider["turnaround_days"],
                "relationship": provider["relationship_status"],
                "products": provider["products"],
                "strengths": provider["strengths"],
                "contact": provider.get("contact", {}),
            })

        scored.sort(key=lambda x: x["match_score"], reverse=True)
        return scored

    def generate_outreach(self, provider: dict, deal: dict, premium: dict) -> dict:
        """Generate provider outreach package via Morgan."""
        provider_name = provider.get("provider_name", "Provider")
        deal_name = deal.get("name", "Project")
        bond_face = deal.get("bond_face_usd", 100_000_000)
        rec = premium.get("recommended_premium", {})

        subject = f"Surety Indication Request | {deal_name} | ${bond_face/1e6:.0f}M | {deal.get('asset_type', 'CRE').replace('_', ' ').title()}"

        prompt = (
            f"Write a surety indication request letter from NEST Advisors to {provider_name}.\n\n"
            f"DEAL: {deal_name}\n"
            f"Location: {deal.get('city', '')}, {deal.get('state', '')}\n"
            f"Asset type: {deal.get('asset_type', '')}\n"
            f"Bond face: ${bond_face:,.0f}\n"
            f"Rating target: {deal.get('rating_target', 'BBB')}\n"
            f"DSCR: {deal.get('dscr', 1.5):.2f}x\n"
            f"LTV: {deal.get('ltv_pct', 65)}%\n"
            f"Estimated premium: {rec.get('adjusted_rate_bps', 120)}bps\n"
            f"Product needed: {rec.get('product', 'cash_surety_sbloc')}\n\n"
            f"Request: (1) Premium indication. (2) Capacity confirmation. "
            f"(3) Required documentation checklist. (4) Timeline to bind.\n"
            f"Tone: professional, direct. Reference NEST Advisors' Jacaranda Trace model."
        )

        try:
            letter = complete(JIMMY_LEE_SYSTEM_PROMPT, prompt, max_tokens=800)
        except (ClaudeUnavailable, Exception):
            letter = (
                f"Re: Surety Indication — {deal_name}\n\n"
                f"NEST Advisors requests a surety indication for the above-referenced project. "
                f"Bond face ${bond_face:,.0f}. {deal.get('asset_type', 'CRE').replace('_', ' ').title()} "
                f"in {deal.get('state', '')}. Rating target {deal.get('rating_target', 'BBB')}.\n\n"
                f"Please provide: premium indication, capacity confirmation, doc checklist, timeline.\n\n"
                f"— NEST Advisors"
            )

        return {
            "subject": subject,
            "letter": letter,
            "provider": provider_name,
            "deal": deal_name,
            "generated_at": datetime.utcnow().isoformat(),
        }

    def run(self, deal_id: str, deal_data: dict = None) -> dict:
        """Full SuretyScout run: calculate premium, match providers, recommend."""
        deal = deal_data or {
            "bond_face_usd": 173_000_000,
            "rating_target": "A",
            "asset_type": "senior_living",
            "state": "FL",
            "duration_years": 5,
            "dscr": 1.7,
            "ltv_pct": 65,
            "name": "Sample Deal",
        }

        premium = self.calculate_premium(deal)
        providers = self.match_providers(deal)

        return {
            "deal_id": deal_id,
            "premium_analysis": premium,
            "provider_matches": providers,
            "top_provider": providers[0] if providers else None,
            "recommended_product": premium["recommended_product"],
            "estimated_annual_cost": premium["recommended_premium"]["annual_premium_usd"],
            "lc_phase_savings": premium["lc_phase_savings"],
            "timestamp": datetime.utcnow().isoformat(),
        }


# Singleton
surety_scout = SuretyScoutAgent()

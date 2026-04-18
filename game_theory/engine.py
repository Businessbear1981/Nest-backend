"""
Game Theory Engine — 3-level analysis for NEST M&A and lending decisions.

Level 1: Nash Equilibrium (auction theory / Bertrand competition)
Level 2: Bayesian Nash (signal extraction, type estimation)
Level 3: Dynamic Game (repeated interaction, Folk Theorem, signaling)

Pure Python — no numpy, scipy, or nashpy.
"""
import random
import math
from datetime import datetime


class GameTheoryEngine:
    """Three-level game theory engine for deal analysis."""

    # ------------------------------------------------------------------ #
    #  LEVEL 1 — Nash Equilibrium                                         #
    # ------------------------------------------------------------------ #

    def level1_acquisition_nash(self, target: dict, nest_params: dict, competitors: list) -> dict:
        """
        Compute Nash bid using first-price sealed-bid auction theory.

        target:      {name, ev_usd, ebitda, revenue, sector}
        nest_params: {max_multiple, synergy_pct, cost_of_capital}
        competitors: [{name, estimated_multiple, aggression}]
        """
        ev = target.get("ev_usd", 0)
        ebitda = target.get("ebitda", 1)
        base_multiple = ev / ebitda if ebitda else 6.0

        # Estimate competitor bids via second-price intuition
        comp_bids = []
        for c in competitors:
            est_mult = c.get("estimated_multiple", base_multiple)
            aggression = c.get("aggression", 0.5)
            noise = random.gauss(0, 0.3)
            bid_mult = est_mult * (1 + aggression * 0.15 + noise * 0.05)
            comp_bids.append({"name": c["name"], "bid_multiple": round(bid_mult, 2)})

        # Nash: shade bid below valuation by 1/N rule (N = total bidders)
        n_bidders = len(competitors) + 1
        synergy_value = ev * nest_params.get("synergy_pct", 0.10)
        max_mult = nest_params.get("max_multiple", 8.0)
        true_value_mult = min(base_multiple + (synergy_value / ebitda if ebitda else 0), max_mult)

        # Optimal shading: bid = value * (N-1)/N
        shade_factor = (n_bidders - 1) / n_bidders if n_bidders > 1 else 0.85
        nash_bid_mult = true_value_mult * shade_factor

        # Win probability estimate
        if comp_bids:
            max_comp = max(b["bid_multiple"] for b in comp_bids)
            win_prob = 1.0 / (1.0 + math.exp(-(nash_bid_mult - max_comp) * 2.0))
        else:
            win_prob = 0.90

        nash_bid_usd = nash_bid_mult * ebitda

        return {
            "nash_bid_multiple": round(nash_bid_mult, 2),
            "nash_bid_usd": round(nash_bid_usd, 2),
            "true_value_multiple": round(true_value_mult, 2),
            "shade_factor": round(shade_factor, 3),
            "win_probability": round(win_prob, 3),
            "competitor_bids": comp_bids,
            "n_bidders": n_bidders,
            "recommendation": "BID" if win_prob > 0.40 else "PASS",
        }

    def level1_lender_nash(self, deal: dict, lenders: list) -> dict:
        """
        Bertrand competition among lenders — price converges to marginal cost.

        deal:    {amount, ltv, dscr, term_months, sector}
        lenders: [{id, name, base_rate, cost_of_funds, risk_appetite}]
        """
        if not lenders:
            return {"error": "no_lenders", "rates": []}

        lender_rates = []
        for lender in lenders:
            cof = lender.get("cost_of_funds", 0.04)
            risk_app = lender.get("risk_appetite", 0.5)
            ltv = deal.get("ltv", 0.70)
            dscr = deal.get("dscr", 1.25)

            # Risk premium based on deal metrics
            ltv_premium = max(0, (ltv - 0.65) * 0.08)
            dscr_discount = max(0, (dscr - 1.20) * 0.02)

            # Bertrand: lender prices at cost + minimal margin
            margin = 0.015 + (1 - risk_app) * 0.01
            rate = cof + margin + ltv_premium - dscr_discount
            rate = max(rate, cof + 0.005)  # floor at cost + 50bps

            # Add noise for private information
            rate += random.gauss(0, 0.002)
            rate = round(rate, 4)

            lender_rates.append({
                "lender_id": lender["id"],
                "lender_name": lender.get("name", lender["id"]),
                "offered_rate": rate,
                "cost_of_funds": cof,
                "spread": round(rate - cof, 4),
            })

        lender_rates.sort(key=lambda x: x["offered_rate"])
        best = lender_rates[0]
        second_best = lender_rates[1] if len(lender_rates) > 1 else best

        return {
            "equilibrium_rate": best["offered_rate"],
            "best_lender": best["lender_id"],
            "second_best_rate": second_best["offered_rate"],
            "spread_compression": round(second_best["offered_rate"] - best["offered_rate"], 4),
            "all_rates": lender_rates,
            "market_competitive": len(lenders) >= 3,
        }

    # ------------------------------------------------------------------ #
    #  LEVEL 2 — Bayesian Nash                                            #
    # ------------------------------------------------------------------ #

    def level2_seller_bayesian(self, target: dict, market_data: dict) -> dict:
        """
        Estimate seller type from observable signals.

        Signals: owner_age, years_in_business, revenue_trend, succession_plan, litigation
        Types:  motivated, distressed, not_urgent
        """
        signals = market_data.get("signals", {})
        owner_age = signals.get("owner_age", 55)
        years_biz = signals.get("years_in_business", 15)
        rev_trend = signals.get("revenue_trend", 0.0)   # -1 to +1
        succession = signals.get("succession_plan", False)
        litigation = signals.get("litigation", False)

        # Prior probabilities
        p_motivated = 0.33
        p_distressed = 0.33
        p_not_urgent = 0.34

        # Likelihood updates (simplified Bayesian)
        # Owner age > 60 => more likely motivated
        if owner_age > 60:
            p_motivated *= 1.5
            p_not_urgent *= 0.7
        elif owner_age < 45:
            p_not_urgent *= 1.4
            p_motivated *= 0.8

        # Revenue declining => distressed
        if rev_trend < -0.2:
            p_distressed *= 2.0
            p_not_urgent *= 0.5
        elif rev_trend > 0.15:
            p_not_urgent *= 1.6
            p_distressed *= 0.4

        # No succession plan + old owner => motivated
        if not succession and owner_age > 55:
            p_motivated *= 1.8

        # Litigation => distressed
        if litigation:
            p_distressed *= 2.5
            p_not_urgent *= 0.3

        # Long tenure + stable => not urgent
        if years_biz > 20 and rev_trend > -0.05:
            p_not_urgent *= 1.3

        # Normalize
        total = p_motivated + p_distressed + p_not_urgent
        p_motivated /= total
        p_distressed /= total
        p_not_urgent /= total

        types_ranked = sorted([
            ("motivated", p_motivated),
            ("distressed", p_distressed),
            ("not_urgent", p_not_urgent),
        ], key=lambda x: -x[1])

        primary_type = types_ranked[0][0]

        # Pricing implications
        discount_map = {"distressed": 0.25, "motivated": 0.12, "not_urgent": 0.03}
        suggested_discount = discount_map[primary_type]

        return {
            "primary_type": primary_type,
            "confidence": round(types_ranked[0][1], 3),
            "type_probabilities": {t: round(p, 3) for t, p in types_ranked},
            "signals_used": signals,
            "suggested_discount": suggested_discount,
            "negotiation_leverage": "HIGH" if p_distressed > 0.45 else "MEDIUM" if p_motivated > 0.40 else "LOW",
        }

    def level2_lender_bayesian(self, deal: dict, lender: dict) -> dict:
        """
        Estimate a lender's true cost floor from observable behavior.
        """
        posted_rate = lender.get("base_rate", 0.065)
        hist_rates = lender.get("historical_rates", [])
        volume = lender.get("deal_volume_ytd", 10)
        portfolio_stress = lender.get("portfolio_stress", 0.0)

        # Estimate true cost of funds
        if hist_rates:
            avg_hist = sum(hist_rates) / len(hist_rates)
            est_cof = avg_hist - 0.02  # typical spread is ~200bps
        else:
            est_cof = posted_rate - 0.025

        # Volume hunger signal
        if volume < 5:
            hunger_factor = 0.15  # hungry, will cut spread
        elif volume > 20:
            hunger_factor = -0.05  # full, premium pricing
        else:
            hunger_factor = 0.0

        # Stress signal
        stress_adj = portfolio_stress * 0.01

        est_floor = est_cof + 0.005 + stress_adj - hunger_factor * 0.01
        est_ceiling = posted_rate

        return {
            "estimated_cost_floor": round(est_floor, 4),
            "posted_rate": posted_rate,
            "estimated_spread": round(posted_rate - est_floor, 4),
            "negotiation_room_bps": round((est_ceiling - est_floor) * 10000, 1),
            "hunger_signal": "HIGH" if hunger_factor > 0.10 else "MEDIUM" if hunger_factor >= 0 else "LOW",
            "recommended_opening_bid": round(est_floor + (est_ceiling - est_floor) * 0.3, 4),
        }

    # ------------------------------------------------------------------ #
    #  LEVEL 3 — Dynamic Game                                             #
    # ------------------------------------------------------------------ #

    def level3_relationship_dynamics(self, entity_type: str, entity_id: str,
                                     history: list, current_deal: dict) -> dict:
        """
        Repeated-game analysis with discount factor, reputation, Folk Theorem.

        entity_type: 'seller' | 'lender' | 'partner'
        history:     [{deal_id, outcome, cooperated, timestamp}]
        """
        delta = 0.92  # discount factor — patient player

        # Reputation score from history
        if history:
            coop_count = sum(1 for h in history if h.get("cooperated", False))
            total = len(history)
            reputation = coop_count / total
        else:
            reputation = 0.5  # uninformative prior

        # Folk Theorem check: can cooperation be sustained?
        # Cooperation sustainable if delta >= (deviation_gain) / (deviation_gain + punishment_cost)
        deviation_gain = current_deal.get("deviation_gain", 0.1)
        punishment_cost = current_deal.get("punishment_cost", 0.15)
        folk_threshold = deviation_gain / (deviation_gain + punishment_cost) if (deviation_gain + punishment_cost) > 0 else 0.5
        cooperation_sustainable = delta >= folk_threshold

        # Grim trigger strategy assessment
        if reputation > 0.75 and cooperation_sustainable:
            strategy = "COOPERATIVE"
            trust_level = "HIGH"
        elif reputation > 0.50:
            strategy = "CAUTIOUS_COOPERATION"
            trust_level = "MEDIUM"
        elif reputation > 0.25:
            strategy = "TIT_FOR_TAT"
            trust_level = "LOW"
        else:
            strategy = "DEFENSIVE"
            trust_level = "MINIMAL"

        # Signaling strategy
        if entity_type == "seller":
            signal = "Show competing bids to signal value" if reputation < 0.5 else "Share financials openly to build trust"
        elif entity_type == "lender":
            signal = "Offer rate lock to signal commitment" if reputation > 0.6 else "Request enhanced covenants"
        else:
            signal = "Propose milestone-based partnership terms"

        return {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "discount_factor": delta,
            "reputation_score": round(reputation, 3),
            "folk_theorem": {
                "threshold": round(folk_threshold, 3),
                "cooperation_sustainable": cooperation_sustainable,
            },
            "recommended_strategy": strategy,
            "trust_level": trust_level,
            "signaling_strategy": signal,
            "interaction_count": len(history),
        }

    # ------------------------------------------------------------------ #
    #  ORCHESTRATOR                                                       #
    # ------------------------------------------------------------------ #

    def run_full_analysis(self, analysis_type: str, primary_data: dict,
                          secondary_data: dict = None, history: list = None) -> dict:
        """
        Run all 3 levels and produce weighted synthesis.

        analysis_type: 'acquisition' | 'lending' | 'partnership'
        Weights: 40% L1 + 40% L2 + 20% L3
        """
        secondary_data = secondary_data or {}
        history = history or []
        results = {"analysis_type": analysis_type, "timestamp": datetime.utcnow().isoformat()}

        # --- Level 1 ---
        if analysis_type == "acquisition":
            competitors = secondary_data.get("competitors", [
                {"name": "PE_Fund_A", "estimated_multiple": 6.5, "aggression": 0.6},
                {"name": "Strategic_B", "estimated_multiple": 7.0, "aggression": 0.4},
            ])
            nest_params = secondary_data.get("nest_params", {
                "max_multiple": 8.0, "synergy_pct": 0.12, "cost_of_capital": 0.10
            })
            l1 = self.level1_acquisition_nash(primary_data, nest_params, competitors)
        elif analysis_type == "lending":
            lenders = secondary_data.get("lenders", [])
            l1 = self.level1_lender_nash(primary_data, lenders)
        else:
            l1 = {"note": "Level 1 not applicable for partnership analysis"}

        results["level1_nash"] = l1

        # --- Level 2 ---
        if analysis_type == "acquisition":
            market_data = secondary_data.get("market_data", {"signals": {}})
            l2 = self.level2_seller_bayesian(primary_data, market_data)
        elif analysis_type == "lending":
            lender = secondary_data.get("primary_lender", {})
            l2 = self.level2_lender_bayesian(primary_data, lender)
        else:
            l2 = {"note": "Level 2 defaults for partnership"}

        results["level2_bayesian"] = l2

        # --- Level 3 ---
        entity_type = "seller" if analysis_type == "acquisition" else "lender" if analysis_type == "lending" else "partner"
        entity_id = primary_data.get("name", primary_data.get("deal_id", "unknown"))
        l3 = self.level3_relationship_dynamics(entity_type, entity_id, history, secondary_data.get("dynamic_params", {}))
        results["level3_dynamic"] = l3

        # --- Weighted Synthesis ---
        w1, w2, w3 = 0.40, 0.40, 0.20

        # Composite confidence
        l1_conf = l1.get("win_probability", 0.5)
        l2_conf = l2.get("confidence", 0.5)
        l3_conf = l3.get("reputation_score", 0.5)
        composite = w1 * l1_conf + w2 * l2_conf + w3 * l3_conf

        # Overall recommendation
        if composite > 0.65:
            recommendation = "STRONG_PROCEED"
        elif composite > 0.45:
            recommendation = "PROCEED_WITH_CAUTION"
        elif composite > 0.30:
            recommendation = "REVIEW_REQUIRED"
        else:
            recommendation = "PASS"

        results["synthesis"] = {
            "weights": {"level1": w1, "level2": w2, "level3": w3},
            "composite_score": round(composite, 3),
            "recommendation": recommendation,
            "confidence_inputs": {
                "l1_signal": round(l1_conf, 3),
                "l2_signal": round(l2_conf, 3),
                "l3_signal": round(l3_conf, 3),
            },
        }

        return results


game_engine = GameTheoryEngine()

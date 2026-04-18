"""Bond Optimizer — real-time bond optimization agent.

Monitors market conditions and recommends optimal calls, puts, and new issuances.
Maximizes par value, optimizes rates and terms, calculates savings.
Handles new bond issuance fee calculations.
"""
from datetime import datetime, timedelta


class BondOptimizerAgent:
    """Optimizes bond lifecycle — calls, puts, new issuance, rate management."""

    # ── Fee Schedule ────────────────────────────────────────────
    FEE_SCHEDULE = {
        "arrangement_fee_pct": 2.5,       # NEST fee on total issuance
        "placement_fee_pct": 1.0,         # Placement agent fee
        "rating_agency_flat": 150_000,    # S&P rating fee (flat)
        "trustee_annual": 25_000,         # Computershare annual fee
        "legal_opinion_flat": 75_000,     # Bond counsel
        "surety_premium_bps": 100,        # Varies — use surety_scout for exact
        "coupon_reserve_pct": 2.5,        # Pre-funded from proceeds
        "maturity_reserve_pct": 2.5,      # Escrowed at close
    }

    def optimize(self, deal_data: dict, bond_data: dict,
                 market_signals: dict) -> dict:
        """Full optimization analysis — should we call, put, hold, or restructure?"""

        current_rate = bond_data.get("coupon_rate_pct", 7.0)
        face = bond_data.get("face_amount_usd", 100_000_000)
        months_outstanding = bond_data.get("months_outstanding", 24)
        remaining_term_months = bond_data.get("remaining_term_months", 36)

        # Market conditions
        treasury_10yr = market_signals.get("treasury_10yr_pct", 4.25)
        treasury_change = market_signals.get("treasury_change_bps", 0)
        credit_spread = market_signals.get("credit_spread_ig_bps", 125)
        refi_access = market_signals.get("refi_market_access", "open_favorable")

        # Current market rate for equivalent bond
        market_rate = treasury_10yr + (credit_spread / 100)

        # Rate differential
        rate_diff_bps = (current_rate - market_rate) * 100

        # Decision matrix
        actions = []

        # CALL analysis — is calling the bond beneficial?
        if rate_diff_bps > 25 and refi_access in ("open_favorable", "open_neutral"):
            annual_savings = face * rate_diff_bps / 10000
            call_cost = face * 0.01  # 1% call premium
            breakeven_months = (call_cost / (annual_savings / 12)) if annual_savings > 0 else 999
            payback_viable = breakeven_months < remaining_term_months

            actions.append({
                "action": "EXECUTE_CALL",
                "priority": "high" if rate_diff_bps > 50 else "medium",
                "rationale": f"Market rate {market_rate:.2f}% vs current {current_rate:.2f}% — {rate_diff_bps:.0f}bps savings available",
                "annual_savings_usd": round(annual_savings),
                "call_cost_usd": round(call_cost),
                "breakeven_months": round(breakeven_months, 1),
                "payback_viable": payback_viable,
                "new_rate_target": round(market_rate, 3),
                "total_savings_over_remaining": round(annual_savings * remaining_term_months / 12),
            })

        # PUT analysis — is the bond at risk of put?
        deal_dscr = deal_data.get("dscr", 1.5)
        if deal_dscr < 1.25 or treasury_change > 75:
            actions.append({
                "action": "PUT_ALERT",
                "priority": "high",
                "rationale": f"DSCR {deal_dscr:.2f}x below put threshold" if deal_dscr < 1.25 else f"Rates spiked {treasury_change}bps — put risk elevated",
                "recommended_response": "Activate Apex hedging" if treasury_change > 75 else "Accelerate NOI improvement plan",
            })

        # HOLD — no action warranted
        if not actions:
            actions.append({
                "action": "HOLD",
                "priority": "low",
                "rationale": f"Rate diff {rate_diff_bps:.0f}bps insufficient for call. Market stable.",
            })

        # Par value optimization
        par_optimization = self._optimize_par_value(face, current_rate, market_rate, remaining_term_months)

        return {
            "deal_id": deal_data.get("id", "unknown"),
            "current_rate": current_rate,
            "market_rate": round(market_rate, 3),
            "rate_differential_bps": round(rate_diff_bps),
            "recommended_actions": actions,
            "par_value_analysis": par_optimization,
            "market_conditions": {
                "treasury_10yr": treasury_10yr,
                "credit_spread_bps": credit_spread,
                "refi_market": refi_access,
                "environment": "favorable" if rate_diff_bps > 25 and refi_access == "open_favorable" else "neutral" if rate_diff_bps > 0 else "unfavorable",
            },
            "analyzed_at": datetime.utcnow().isoformat(),
        }

    def analyze_call_opportunity(self, bond_data: dict, market_signals: dict,
                                  project_schedule: dict = None) -> dict:
        """Detailed call opportunity analysis tied to project schedule."""
        face = bond_data.get("face_amount_usd", 100_000_000)
        current_rate = bond_data.get("coupon_rate_pct", 7.0)
        remaining_months = bond_data.get("remaining_term_months", 36)

        treasury = market_signals.get("treasury_10yr_pct", 4.25)
        spread = market_signals.get("credit_spread_ig_bps", 125)
        market_rate = treasury + (spread / 100)

        schedule = project_schedule or {}
        stabilization_month = schedule.get("stabilization_month", 36)
        construction_complete = schedule.get("construction_complete", False)

        # Timing analysis
        if construction_complete and market_rate < current_rate:
            timing = "OPTIMAL — construction complete, rates favorable"
            timing_score = 95
        elif construction_complete:
            timing = "GOOD — construction complete, rates neutral"
            timing_score = 70
        elif stabilization_month <= 12:
            timing = "APPROACHING — near stabilization, monitor rates"
            timing_score = 50
        else:
            timing = "EARLY — hold until construction milestones met"
            timing_score = 25

        # Savings scenarios
        scenarios = {}
        for rate_scenario, rate_adj in [("current", 0), ("rates_drop_25bps", -0.25), ("rates_drop_50bps", -0.50), ("rates_rise_25bps", 0.25)]:
            new_rate = market_rate + rate_adj
            diff_bps = (current_rate - new_rate) * 100
            annual_saving = face * max(0, diff_bps) / 10000

            scenarios[rate_scenario] = {
                "new_rate": round(new_rate, 3),
                "savings_bps": round(diff_bps),
                "annual_savings": round(annual_saving),
                "total_savings": round(annual_saving * remaining_months / 12),
                "call_recommended": diff_bps > 25,
            }

        # Payoff analysis — can we access additional funds?
        current_debt_service = face * current_rate / 100
        new_debt_service = face * market_rate / 100
        freed_cash_flow = max(0, current_debt_service - new_debt_service)
        additional_capacity = freed_cash_flow / (market_rate / 100) if market_rate > 0 else 0

        return {
            "timing": timing,
            "timing_score": timing_score,
            "current_rate": current_rate,
            "market_rate": round(market_rate, 3),
            "scenarios": scenarios,
            "freed_cash_flow_annual": round(freed_cash_flow),
            "additional_borrowing_capacity": round(additional_capacity),
            "recommendation": (
                "EXECUTE CALL NOW" if timing_score >= 80 and scenarios["current"]["call_recommended"] else
                "PREPARE FOR CALL — monitor for rate improvement" if timing_score >= 50 else
                "HOLD — timing not optimal"
            ),
        }

    def calculate_new_issuance(self, params: dict) -> dict:
        """Calculate complete new bond issuance with fee schedule.

        Returns total raise, fee breakdown, net proceeds to project.
        """
        project_cost = params.get("total_project_cost_usd", 100_000_000)
        a_ltc = params.get("a_ltc_pct", 75) / 100
        b_addon = params.get("b_addon_pct", 7) / 100
        a_coupon = params.get("a_coupon_pct", 7.0)
        b_coupon = params.get("b_coupon_pct", 12.0)
        duration = params.get("duration_years", 5)
        surety_type = params.get("surety_type", "cash_surety_sbloc")

        a_face = project_cost * a_ltc
        b_face = project_cost * b_addon
        total_par = a_face + b_face

        # Fee calculations
        arrangement_fee = total_par * (self.FEE_SCHEDULE["arrangement_fee_pct"] / 100)
        placement_fee = total_par * (self.FEE_SCHEDULE["placement_fee_pct"] / 100)
        rating_fee = self.FEE_SCHEDULE["rating_agency_flat"]
        trustee_total = self.FEE_SCHEDULE["trustee_annual"] * duration
        legal_fee = self.FEE_SCHEDULE["legal_opinion_flat"]
        surety_premium = a_face * (self.FEE_SCHEDULE["surety_premium_bps"] / 10000) * duration
        coupon_reserve = total_par * (self.FEE_SCHEDULE["coupon_reserve_pct"] / 100)
        maturity_reserve = total_par * (self.FEE_SCHEDULE["maturity_reserve_pct"] / 100)
        io_prefund = a_face * (a_coupon / 100) * min(2, duration)

        total_fees = arrangement_fee + placement_fee + rating_fee + trustee_total + legal_fee
        total_reserves = coupon_reserve + maturity_reserve + io_prefund + surety_premium
        total_raise = total_par + total_fees + total_reserves
        net_to_project = total_par - total_fees

        # NEST economics
        nest_arrangement = arrangement_fee
        nest_per_refi = total_par * 0.025  # 2.5% per refi cycle
        nest_total_lifecycle = nest_arrangement + (nest_per_refi * 10)  # 10 cycles

        return {
            "issuance_summary": {
                "total_project_cost": round(project_cost),
                "series_a_face": round(a_face),
                "series_a_ltc": a_ltc * 100,
                "series_a_coupon": a_coupon,
                "series_b_face": round(b_face),
                "series_b_addon": b_addon * 100,
                "series_b_coupon": b_coupon,
                "total_par_value": round(total_par),
                "total_raise": round(total_raise),
                "net_to_project": round(net_to_project),
            },
            "fee_schedule": {
                "arrangement_fee": round(arrangement_fee),
                "placement_fee": round(placement_fee),
                "rating_agency": rating_fee,
                "trustee_total": trustee_total,
                "legal_opinion": legal_fee,
                "total_fees": round(total_fees),
            },
            "reserves": {
                "coupon_reserve": round(coupon_reserve),
                "maturity_reserve": round(maturity_reserve),
                "io_prefund": round(io_prefund),
                "surety_premium_total": round(surety_premium),
                "total_reserves": round(total_reserves),
            },
            "nest_economics": {
                "arrangement_fee": round(nest_arrangement),
                "per_refi_cycle": round(nest_per_refi),
                "estimated_refi_cycles": 10,
                "total_lifecycle_fees": round(nest_total_lifecycle),
                "fee_as_pct_of_par": round(nest_total_lifecycle / total_par * 100, 2),
            },
            "equity_requirement": {
                "amount": round(project_cost - total_par),
                "pct_of_tpc": round((1 - a_ltc - b_addon) * 100, 1),
            },
        }

    def calculate_savings(self, current_bond: dict, proposed_terms: dict) -> dict:
        """Calculate savings from call/refi action."""
        face = current_bond.get("face_amount_usd", 100_000_000)
        current_rate = current_bond.get("coupon_rate_pct", 7.0)
        remaining_months = current_bond.get("remaining_term_months", 36)

        new_rate = proposed_terms.get("new_coupon_rate_pct", 6.5)
        call_premium_pct = proposed_terms.get("call_premium_pct", 1.0)

        rate_savings_bps = (current_rate - new_rate) * 100
        annual_savings = face * rate_savings_bps / 10000
        call_cost = face * (call_premium_pct / 100)
        reissuance_cost = face * 0.025  # NEST arrangement fee
        total_cost = call_cost + reissuance_cost

        remaining_years = remaining_months / 12
        total_savings = annual_savings * remaining_years
        net_savings = total_savings - total_cost
        breakeven_months = (total_cost / (annual_savings / 12)) if annual_savings > 0 else 999

        return {
            "current_rate": current_rate,
            "new_rate": new_rate,
            "rate_savings_bps": round(rate_savings_bps),
            "annual_savings_usd": round(annual_savings),
            "total_savings_usd": round(total_savings),
            "call_cost_usd": round(call_cost),
            "reissuance_cost_usd": round(reissuance_cost),
            "total_cost_usd": round(total_cost),
            "net_savings_usd": round(net_savings),
            "breakeven_months": round(breakeven_months, 1),
            "roi_pct": round(net_savings / total_cost * 100, 1) if total_cost > 0 else 0,
            "recommendation": (
                "EXECUTE — strong positive economics" if net_savings > 0 and breakeven_months < 12 else
                "CONSIDER — positive but longer payback" if net_savings > 0 else
                "DECLINE — negative economics at current rates"
            ),
        }

    def _optimize_par_value(self, face, current_rate, market_rate, remaining_months):
        """Calculate optimal par value given rate environment."""
        current_ds = face * current_rate / 100
        if market_rate > 0:
            optimal_face_at_market = current_ds / (market_rate / 100)
        else:
            optimal_face_at_market = face

        additional_capacity = optimal_face_at_market - face

        return {
            "current_par": round(face),
            "optimal_par_at_market_rate": round(optimal_face_at_market),
            "additional_capacity_usd": round(max(0, additional_capacity)),
            "can_access_additional_funds": additional_capacity > 0,
            "note": f"At {market_rate:.2f}%, same debt service supports ${max(0, additional_capacity):,.0f} more in proceeds" if additional_capacity > 0 else "No additional capacity at current rates",
        }


# Singleton
bond_optimizer = BondOptimizerAgent()

"""
Vector — NEST's call/put timing agent. Monitors 14 market signals on
15-minute intervals and recommends when to execute bond calls, puts,
or shorts across the capital structure.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional


class VectorAgent:
    """Scores 14 market & deal signals to generate call/put recommendations."""

    SIGNALS = [
        'treasury_10yr', 'treasury_change_bps', 'sofr',
        'credit_spread_ig', 'credit_spread_hy', 'vix',
        'refi_market_access', 'deal_dscr', 'deal_occupancy',
        'covenant_status', 'months_since_origination',
        'hft_return_ytd', 'b_tranche_coverage', 'lc_capacity_ratio',
    ]

    WEIGHTS = {
        'treasury_change_bps': 0.25,
        'deal_dscr':           0.20,
        'credit_spread_change': 0.15,
        'refi_market_access':  0.15,
        'deal_occupancy':      0.10,
        'months_since_origination': 0.10,
        'hft_return_ytd':      0.05,
    }

    # Thresholds for recommendation buckets
    EXECUTE_CALL_FLOOR   = 82
    CALL_ELIGIBLE_FLOOR  = 65
    MONITOR_FLOOR        = 45
    HOLD_FLOOR           = 25
    # Below HOLD_FLOOR -> PUT_ALERT

    def __init__(self) -> None:
        self._last_run: Optional[datetime] = None
        self._history: list[dict] = []

    # ------------------------------------------------------------------
    # Signal normalizers — each returns 0-3
    # ------------------------------------------------------------------

    @staticmethod
    def _norm_treasury_change(bps: float) -> float:
        """Negative change = rates dropping = favorable for call.
        -50bps or more -> 3, +50bps or more -> 0."""
        if bps <= -50:
            return 3.0
        if bps >= 50:
            return 0.0
        return 3.0 * (50 - bps) / 100.0

    @staticmethod
    def _norm_dscr(dscr: float) -> float:
        """DSCR > 2.0 -> 3, < 1.25 -> 0. Linear between."""
        if dscr >= 2.0:
            return 3.0
        if dscr <= 1.25:
            return 0.0
        return 3.0 * (dscr - 1.25) / 0.75

    @staticmethod
    def _norm_credit_spread_change(spread_bps: float) -> float:
        """Tightening spreads favor a call. -30bps -> 3, +30bps -> 0."""
        if spread_bps <= -30:
            return 3.0
        if spread_bps >= 30:
            return 0.0
        return 3.0 * (30 - spread_bps) / 60.0

    @staticmethod
    def _norm_refi_access(score: float) -> float:
        """0-100 scale where 100 = wide open refi market. Map to 0-3."""
        clamped = max(0.0, min(100.0, score))
        return 3.0 * clamped / 100.0

    @staticmethod
    def _norm_occupancy(pct: float) -> float:
        """95%+ -> 3, <80% -> 0."""
        if pct >= 95:
            return 3.0
        if pct <= 80:
            return 0.0
        return 3.0 * (pct - 80) / 15.0

    @staticmethod
    def _norm_months_since_origination(months: float) -> float:
        """Older deals are more call-ready. 24mo+ -> 3, <6mo -> 0."""
        if months >= 24:
            return 3.0
        if months <= 6:
            return 0.0
        return 3.0 * (months - 6) / 18.0

    @staticmethod
    def _norm_hft_return(ytd_pct: float) -> float:
        """Strong HFT returns support call economics. 20%+ -> 3, <5% -> 0."""
        if ytd_pct >= 20:
            return 3.0
        if ytd_pct <= 5:
            return 0.0
        return 3.0 * (ytd_pct - 5) / 15.0

    # ------------------------------------------------------------------
    # Core scoring
    # ------------------------------------------------------------------

    def score_signals(self, signals: dict) -> float:
        """Return composite score 0-100. Each signal normalized 0-3,
        weighted, summed, then scaled to 0-100."""
        normalized = {
            'treasury_change_bps':      self._norm_treasury_change(signals.get('treasury_change_bps', 0)),
            'deal_dscr':                self._norm_dscr(signals.get('deal_dscr', 1.5)),
            'credit_spread_change':     self._norm_credit_spread_change(
                                            signals.get('credit_spread_ig', 0) - signals.get('credit_spread_hy', 0)
                                            if 'credit_spread_ig' in signals and 'credit_spread_hy' in signals
                                            else signals.get('credit_spread_change', 0)),
            'refi_market_access':       self._norm_refi_access(signals.get('refi_market_access', 50)),
            'deal_occupancy':           self._norm_occupancy(signals.get('deal_occupancy', 90)),
            'months_since_origination': self._norm_months_since_origination(signals.get('months_since_origination', 12)),
            'hft_return_ytd':           self._norm_hft_return(signals.get('hft_return_ytd', 10)),
        }

        weighted_sum = 0.0
        max_possible = 0.0
        for key, weight in self.WEIGHTS.items():
            weighted_sum += normalized.get(key, 0.0) * weight
            max_possible += 3.0 * weight

        if max_possible == 0:
            return 0.0
        return round((weighted_sum / max_possible) * 100, 2)

    # ------------------------------------------------------------------
    # Recommendation engine
    # ------------------------------------------------------------------

    def recommend(self, signals: dict, deal_data: dict) -> dict:
        """Generate a structured recommendation based on current signals
        and deal-level data.

        Returns dict with keys:
            recommendation: EXECUTE_CALL | CALL_ELIGIBLE | MONITOR | HOLD | PUT_ALERT
            confidence: 0-100
            reasoning: list[str]
            apex_action: None | ACTIVATE_SHORT | CLOSE_SHORT
            estimated_savings_usd: float
        """
        score = self.score_signals(signals)
        reasoning: list[str] = []
        apex_action: Optional[str] = None

        # --- Determine recommendation bucket ---
        if score >= self.EXECUTE_CALL_FLOOR:
            rec = 'EXECUTE_CALL'
            reasoning.append(f'Composite score {score} exceeds execute threshold ({self.EXECUTE_CALL_FLOOR}).')
            apex_action = 'CLOSE_SHORT'  # close hedges when calling
        elif score >= self.CALL_ELIGIBLE_FLOOR:
            rec = 'CALL_ELIGIBLE'
            reasoning.append(f'Score {score} in call-eligible range ({self.CALL_ELIGIBLE_FLOOR}-{self.EXECUTE_CALL_FLOOR}).')
        elif score >= self.MONITOR_FLOOR:
            rec = 'MONITOR'
            reasoning.append(f'Score {score} in monitor range ({self.MONITOR_FLOOR}-{self.CALL_ELIGIBLE_FLOOR}).')
        elif score >= self.HOLD_FLOOR:
            rec = 'HOLD'
            reasoning.append(f'Score {score} in hold range ({self.HOLD_FLOOR}-{self.MONITOR_FLOOR}).')
        else:
            rec = 'PUT_ALERT'
            reasoning.append(f'Score {score} below hold floor ({self.HOLD_FLOOR}). Put risk elevated.')
            apex_action = 'ACTIVATE_SHORT'

        # --- Signal-specific reasoning ---
        treasury_chg = signals.get('treasury_change_bps', 0)
        if treasury_chg <= -25:
            reasoning.append(f'Treasury move {treasury_chg:+.0f}bps — strong tailwind for refinancing.')
        elif treasury_chg >= 25:
            reasoning.append(f'Treasury move {treasury_chg:+.0f}bps — headwind. Rate lock recommended.')

        dscr = signals.get('deal_dscr', 1.5)
        if dscr >= 2.0:
            reasoning.append(f'DSCR {dscr:.2f}x — A-grade. Call economics attractive.')
        elif dscr < 1.25:
            reasoning.append(f'DSCR {dscr:.2f}x — sub-IG territory. Covenant review needed.')

        vix = signals.get('vix', 20)
        if vix > 30:
            reasoning.append(f'VIX at {vix:.1f} — elevated volatility. Execution risk higher.')
        elif vix < 15:
            reasoning.append(f'VIX at {vix:.1f} — calm markets. Favorable execution window.')

        occupancy = signals.get('deal_occupancy', 90)
        if occupancy < 85:
            reasoning.append(f'Occupancy {occupancy:.0f}% — below stabilization target. Delays refi timeline.')

        # --- Estimated savings ---
        bond_face = deal_data.get('bond_face_value', 0)
        current_coupon = deal_data.get('current_coupon_pct', 7.0)
        refi_rate_est = signals.get('treasury_10yr', 4.5) + 1.5  # spread over treasury
        coupon_delta = current_coupon - refi_rate_est
        years_remaining = deal_data.get('years_to_maturity', 10)

        if coupon_delta > 0 and bond_face > 0:
            annual_savings = bond_face * (coupon_delta / 100.0)
            estimated_savings = round(annual_savings * years_remaining, 2)
        else:
            estimated_savings = 0.0

        if estimated_savings > 0:
            reasoning.append(
                f'Estimated savings: ${estimated_savings:,.0f} over {years_remaining}yr '
                f'({coupon_delta:+.2f}% coupon reduction).'
            )

        # --- Confidence ---
        # Base confidence from score proximity to thresholds
        if rec == 'EXECUTE_CALL':
            confidence = min(99, 70 + int((score - self.EXECUTE_CALL_FLOOR) * 1.5))
        elif rec == 'PUT_ALERT':
            confidence = min(99, 70 + int((self.HOLD_FLOOR - score) * 2))
        else:
            confidence = min(95, 40 + int(score * 0.5))

        # Penalize confidence when VIX is high
        if vix > 25:
            confidence = max(10, confidence - int((vix - 25) * 0.8))

        return {
            'recommendation': rec,
            'confidence': confidence,
            'reasoning': reasoning,
            'apex_action': apex_action,
            'estimated_savings_usd': estimated_savings,
            'composite_score': score,
            'timestamp': datetime.utcnow().isoformat(),
        }

    # ------------------------------------------------------------------
    # Put risk analysis
    # ------------------------------------------------------------------

    def check_put_risk(self, signals: dict, deal_data: dict) -> dict:
        """Evaluate the risk of a mandatory or investor-triggered put.

        Returns dict with keys:
            put_risk_level: LOW | MEDIUM | HIGH | CRITICAL
            trigger_conditions: list[str]
            days_to_cure_window: int
        """
        triggers: list[str] = []

        dscr = signals.get('deal_dscr', 1.5)
        if dscr < 1.25:
            triggers.append(f'DSCR {dscr:.2f}x breaches 1.25x covenant minimum.')
        elif dscr < 1.5:
            triggers.append(f'DSCR {dscr:.2f}x approaching covenant floor.')

        occupancy = signals.get('deal_occupancy', 90)
        if occupancy < 80:
            triggers.append(f'Occupancy {occupancy:.0f}% below 80% put trigger.')

        covenant = signals.get('covenant_status', 'compliant')
        if covenant == 'breached':
            triggers.append('Active covenant breach reported.')
        elif covenant == 'watch':
            triggers.append('Covenant on watch list — cure period may apply.')

        b_coverage = signals.get('b_tranche_coverage', 1.0)
        if b_coverage < 0.8:
            triggers.append(f'B-tranche coverage {b_coverage:.2f}x — subordination at risk.')

        lc_ratio = signals.get('lc_capacity_ratio', 1.0)
        if lc_ratio < 0.5:
            triggers.append(f'LC capacity ratio {lc_ratio:.2f} — collateral shortfall risk.')

        treasury_chg = signals.get('treasury_change_bps', 0)
        if treasury_chg > 75:
            triggers.append(f'Treasury spike {treasury_chg:+.0f}bps — refunding cost prohibitive.')

        # --- Determine risk level ---
        critical_count = sum(1 for t in triggers if 'breach' in t.lower() or 'below' in t.lower())
        total_triggers = len(triggers)

        if critical_count >= 2 or total_triggers >= 4:
            level = 'CRITICAL'
            cure_days = 15
        elif critical_count >= 1 or total_triggers >= 3:
            level = 'HIGH'
            cure_days = 30
        elif total_triggers >= 2:
            level = 'MEDIUM'
            cure_days = 60
        else:
            level = 'LOW'
            cure_days = 90

        # Shorten cure window based on deal age
        months = signals.get('months_since_origination', 12)
        if months < 12:
            cure_days = max(10, cure_days - 15)  # newer deals get shorter rope

        return {
            'put_risk_level': level,
            'trigger_conditions': triggers if triggers else ['No active triggers detected.'],
            'days_to_cure_window': cure_days,
            'timestamp': datetime.utcnow().isoformat(),
        }

    # ------------------------------------------------------------------
    # Full agent run
    # ------------------------------------------------------------------

    def _default_signals(self) -> dict:
        """Simulated market snapshot when live feed is unavailable."""
        return {
            'treasury_10yr': 4.35,
            'treasury_change_bps': -8,
            'sofr': 5.31,
            'credit_spread_ig': 95,
            'credit_spread_hy': 340,
            'vix': 18.5,
            'refi_market_access': 72,
            'deal_dscr': 1.85,
            'deal_occupancy': 93,
            'covenant_status': 'compliant',
            'months_since_origination': 14,
            'hft_return_ytd': 21.3,
            'b_tranche_coverage': 1.15,
            'lc_capacity_ratio': 0.85,
        }

    def _default_deal_data(self, deal_id: str) -> dict:
        """Stub deal data keyed off Jacaranda Trace PLOM parameters."""
        return {
            'deal_id': deal_id,
            'bond_face_value': 231_000_000,
            'current_coupon_pct': 7.0,
            'years_to_maturity': 10,
            'series': 'A',
            'issuer': 'Jacaranda Trace LGFC',
        }

    def run(self, deal_id: str, signals: dict = None, deal_data: dict = None) -> dict:
        """Full agent cycle: gather signals, score, recommend, assess put risk."""
        if signals is None:
            signals = self._default_signals()
        if deal_data is None:
            deal_data = self._default_deal_data(deal_id)

        score = self.score_signals(signals)
        recommendation = self.recommend(signals, deal_data)
        put_risk = self.check_put_risk(signals, deal_data)

        result = {
            'agent': 'Vector',
            'deal_id': deal_id,
            'composite_score': score,
            'recommendation': recommendation,
            'put_risk': put_risk,
            'signals_used': list(signals.keys()),
            'timestamp': datetime.utcnow().isoformat(),
        }

        self._last_run = datetime.utcnow()
        self._history.append(result)
        # Keep last 500 runs in memory
        if len(self._history) > 500:
            self._history = self._history[-500:]

        return result


# Singleton instance
vector = VectorAgent()

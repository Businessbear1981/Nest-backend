"""
Apex — NEST's short position manager. Manages TLT puts, T-note futures,
interest rate swaps, and SOFR futures as hedges against rising rates
across the bond portfolio.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional


class ApexAgent:
    """Evaluates, activates, and manages short / hedge positions to
    protect the NEST capital structure from adverse rate moves."""

    INSTRUMENTS = ['TLT_PUT', 'ZN_FUTURE', 'IRS_PAYER', 'SOFR_FUTURE']

    # Instrument-level parameters
    INSTRUMENT_PARAMS = {
        'TLT_PUT': {
            'description': 'iShares 20+ Year Treasury Bond ETF put option',
            'notional_multiplier': 100,
            'typical_cost_bps': 35,
            'duration_factor': 17.5,  # TLT effective duration ~17.5yr
        },
        'ZN_FUTURE': {
            'description': '10-Year T-Note futures (CBOT)',
            'notional_multiplier': 100_000,
            'typical_cost_bps': 5,
            'duration_factor': 7.0,
        },
        'IRS_PAYER': {
            'description': 'Interest rate swap — payer (pay fixed, receive float)',
            'notional_multiplier': 1,
            'typical_cost_bps': 12,
            'duration_factor': 1.0,  # matched to swap tenor
        },
        'SOFR_FUTURE': {
            'description': 'CME SOFR futures contract',
            'notional_multiplier': 2_500,  # $25 per bp per contract
            'typical_cost_bps': 3,
            'duration_factor': 0.25,
        },
    }

    # Rate move thresholds for action
    ACTIVATE_THRESHOLD_BPS = 25   # rising rates trigger
    CLOSE_THRESHOLD_BPS = -15     # falling rates close trigger
    INCREASE_THRESHOLD_BPS = 50   # severe move warrants increase

    def __init__(self) -> None:
        self._positions: dict[str, dict] = {}  # deal_id -> position
        self._trade_log: list[dict] = []
        self._last_run: Optional[datetime] = None

    # ------------------------------------------------------------------
    # Instrument selection
    # ------------------------------------------------------------------

    def _select_instrument(self, market_signals: dict, bond_duration: float) -> str:
        """Pick the best hedge instrument based on market conditions and
        portfolio duration."""
        vix = market_signals.get('vix', 20)
        treasury_chg = market_signals.get('treasury_change_bps', 0)
        sofr = market_signals.get('sofr', 5.3)

        # High vol + big rate move -> TLT puts (convexity benefit)
        if vix > 25 and treasury_chg > 30:
            return 'TLT_PUT'

        # Long duration exposure -> ZN futures (direct offset)
        if bond_duration > 8:
            return 'ZN_FUTURE'

        # Floating rate exposure or SOFR-indexed debt -> SOFR futures
        if sofr > 5.5:
            return 'SOFR_FUTURE'

        # Default: payer swap for general rate protection
        return 'IRS_PAYER'

    # ------------------------------------------------------------------
    # Evaluate opportunity
    # ------------------------------------------------------------------

    def evaluate_short_opportunity(self, market_signals: dict, vector_recommendation: str) -> dict:
        """Determine whether to activate a short / hedge position.

        Args:
            market_signals: dict of current market data
            vector_recommendation: recommendation string from VectorAgent

        Returns dict with keys:
            should_activate: bool
            instrument: str
            notional_usd: float
            direction: str
            rationale: str
        """
        treasury_chg = market_signals.get('treasury_change_bps', 0)
        vix = market_signals.get('vix', 20)
        bond_duration = market_signals.get('bond_duration', 7.0)
        bond_face = market_signals.get('bond_face_value', 231_000_000)

        should_activate = False
        rationale_parts: list[str] = []

        # Activate on PUT_ALERT from Vector
        if vector_recommendation == 'PUT_ALERT':
            should_activate = True
            rationale_parts.append('Vector issued PUT_ALERT — hedging required.')

        # Activate on significant rate increase
        if treasury_chg >= self.ACTIVATE_THRESHOLD_BPS:
            should_activate = True
            rationale_parts.append(
                f'Treasury change {treasury_chg:+.0f}bps exceeds '
                f'{self.ACTIVATE_THRESHOLD_BPS}bps threshold.'
            )

        # Activate on extreme volatility
        if vix > 35:
            should_activate = True
            rationale_parts.append(f'VIX {vix:.1f} — extreme volatility warrants protection.')

        instrument = self._select_instrument(market_signals, bond_duration)

        # Size the hedge: DV01-based notional
        hedge_info = self.calculate_hedge_ratio(bond_face, bond_duration, treasury_chg)
        notional = hedge_info['hedge_notional']

        if not should_activate:
            rationale_parts.append('No activation triggers met. Monitoring.')

        return {
            'should_activate': should_activate,
            'instrument': instrument,
            'notional_usd': round(notional, 2),
            'direction': 'SHORT' if should_activate else 'NONE',
            'rationale': ' '.join(rationale_parts) if rationale_parts else 'Market conditions stable.',
            'timestamp': datetime.utcnow().isoformat(),
        }

    # ------------------------------------------------------------------
    # Position management
    # ------------------------------------------------------------------

    def manage_position(self, position: dict, current_signals: dict) -> dict:
        """Given an existing position and current signals, decide next action.

        Args:
            position: dict with keys instrument, notional, entry_rate, entry_date, deal_id
            current_signals: current market data

        Returns dict with keys:
            action: HOLD | CLOSE | INCREASE | DECREASE
            rationale: str
            unrealized_pl_estimate: float
        """
        instrument = position.get('instrument', 'ZN_FUTURE')
        entry_rate = position.get('entry_rate', 4.5)
        notional = position.get('notional', 0)
        current_rate = current_signals.get('treasury_10yr', 4.5)
        treasury_chg = current_signals.get('treasury_change_bps', 0)

        # --- Simulated P&L based on rate move ---
        # DV01 approximation: P&L = notional * duration * delta_rate / 100
        # For a short, we profit when rates rise
        params = self.INSTRUMENT_PARAMS.get(instrument, self.INSTRUMENT_PARAMS['ZN_FUTURE'])
        duration = params['duration_factor']
        rate_delta = current_rate - entry_rate
        # Short position: positive P&L when rates rise (rate_delta > 0)
        unrealized_pl = round(notional * duration * rate_delta / 100.0, 2)

        rationale_parts: list[str] = []

        # --- Decision logic ---
        if treasury_chg >= self.INCREASE_THRESHOLD_BPS:
            action = 'INCREASE'
            rationale_parts.append(
                f'Rates surging {treasury_chg:+.0f}bps — increase hedge notional by 25%.'
            )
        elif treasury_chg <= self.CLOSE_THRESHOLD_BPS:
            action = 'CLOSE'
            rationale_parts.append(
                f'Rates declining {treasury_chg:+.0f}bps — close hedge to lock in gains.'
            )
        elif unrealized_pl > notional * 0.03:
            # Take profit at 3% of notional
            action = 'DECREASE'
            rationale_parts.append(
                f'Unrealized P&L ${unrealized_pl:,.0f} exceeds 3% target — reduce by 50%.'
            )
        elif unrealized_pl < -(notional * 0.02):
            # Stop loss at -2% of notional
            action = 'CLOSE'
            rationale_parts.append(
                f'Unrealized loss ${unrealized_pl:,.0f} hit -2% stop — closing position.'
            )
        else:
            action = 'HOLD'
            rationale_parts.append(
                f'Position within bands. Rate delta {rate_delta:+.2f}%, '
                f'unrealized P&L ${unrealized_pl:,.0f}.'
            )

        # Age-based review
        entry_date = position.get('entry_date')
        if entry_date:
            if isinstance(entry_date, str):
                try:
                    entry_dt = datetime.fromisoformat(entry_date)
                except ValueError:
                    entry_dt = datetime.utcnow()
            else:
                entry_dt = entry_date
            days_held = (datetime.utcnow() - entry_dt).days
            if days_held > 90 and action == 'HOLD':
                rationale_parts.append(
                    f'Position aged {days_held} days — review for roll or close.'
                )

        return {
            'action': action,
            'rationale': ' '.join(rationale_parts),
            'unrealized_pl_estimate': unrealized_pl,
            'instrument': instrument,
            'current_rate': current_rate,
            'entry_rate': entry_rate,
            'timestamp': datetime.utcnow().isoformat(),
        }

    # ------------------------------------------------------------------
    # Hedge ratio (DV01-based)
    # ------------------------------------------------------------------

    def calculate_hedge_ratio(self, bond_face: float, duration: float,
                              rate_sensitivity_bps: float) -> dict:
        """Calculate the hedge notional using DV01 approximation.

        DV01 of bond = face * duration * 0.0001
        Hedge notional = bond_dv01 / hedge_instrument_dv01 * hedge_face

        Args:
            bond_face: face value of the bond being hedged
            duration: modified duration of the bond
            rate_sensitivity_bps: current rate move in bps (for instrument selection)

        Returns dict with keys:
            hedge_notional: float (USD)
            instrument: str
            hedge_ratio: float
            cost_estimate: float
        """
        # Bond DV01 = face * duration * 0.0001
        bond_dv01 = bond_face * duration * 0.0001

        # Select instrument based on a simple heuristic
        if abs(rate_sensitivity_bps) >= 50:
            instrument = 'TLT_PUT'
        elif duration > 8:
            instrument = 'ZN_FUTURE'
        elif duration < 3:
            instrument = 'SOFR_FUTURE'
        else:
            instrument = 'IRS_PAYER'

        params = self.INSTRUMENT_PARAMS[instrument]
        inst_duration = params['duration_factor']

        # Hedge instrument DV01 per $1 notional = duration * 0.0001
        if inst_duration > 0:
            inst_dv01_per_dollar = inst_duration * 0.0001
            hedge_notional = bond_dv01 / inst_dv01_per_dollar
        else:
            hedge_notional = bond_face  # fallback: dollar-for-dollar

        # Hedge ratio = hedge_notional / bond_face
        hedge_ratio = round(hedge_notional / bond_face, 4) if bond_face > 0 else 0.0

        # Estimated cost = notional * cost_bps / 10000
        cost_bps = params['typical_cost_bps']
        cost_estimate = round(hedge_notional * cost_bps / 10_000, 2)

        return {
            'hedge_notional': round(hedge_notional, 2),
            'instrument': instrument,
            'hedge_ratio': hedge_ratio,
            'cost_estimate': cost_estimate,
            'bond_dv01': round(bond_dv01, 2),
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
            'vix': 18.5,
            'bond_duration': 7.0,
            'bond_face_value': 231_000_000,
            'credit_spread_ig': 95,
            'credit_spread_hy': 340,
        }

    def run(self, deal_id: str, signals: dict = None,
            vector_recommendation: str = 'MONITOR') -> dict:
        """Full agent cycle: evaluate opportunity, manage existing position
        if any, return consolidated status.

        Args:
            deal_id: identifier for the deal being hedged
            signals: market data dict (uses defaults if None)
            vector_recommendation: latest recommendation from VectorAgent
        """
        if signals is None:
            signals = self._default_signals()

        # Evaluate whether to open a new position
        evaluation = self.evaluate_short_opportunity(signals, vector_recommendation)

        # Check for existing position
        existing = self._positions.get(deal_id)
        position_action = None

        if existing:
            position_action = self.manage_position(existing, signals)

            # Execute the action
            if position_action['action'] == 'CLOSE':
                closed = self._positions.pop(deal_id, None)
                self._trade_log.append({
                    'deal_id': deal_id,
                    'action': 'CLOSE',
                    'instrument': existing['instrument'],
                    'notional': existing['notional'],
                    'pl_estimate': position_action['unrealized_pl_estimate'],
                    'timestamp': datetime.utcnow().isoformat(),
                })
            elif position_action['action'] == 'INCREASE':
                self._positions[deal_id]['notional'] = round(
                    existing['notional'] * 1.25, 2
                )
                self._trade_log.append({
                    'deal_id': deal_id,
                    'action': 'INCREASE',
                    'instrument': existing['instrument'],
                    'old_notional': existing['notional'],
                    'new_notional': self._positions[deal_id]['notional'],
                    'timestamp': datetime.utcnow().isoformat(),
                })
            elif position_action['action'] == 'DECREASE':
                self._positions[deal_id]['notional'] = round(
                    existing['notional'] * 0.50, 2
                )
                self._trade_log.append({
                    'deal_id': deal_id,
                    'action': 'DECREASE',
                    'instrument': existing['instrument'],
                    'old_notional': existing['notional'],
                    'new_notional': self._positions[deal_id]['notional'],
                    'timestamp': datetime.utcnow().isoformat(),
                })

        elif evaluation['should_activate']:
            # Open new position
            new_position = {
                'deal_id': deal_id,
                'instrument': evaluation['instrument'],
                'notional': evaluation['notional_usd'],
                'entry_rate': signals.get('treasury_10yr', 4.5),
                'entry_date': datetime.utcnow().isoformat(),
                'direction': 'SHORT',
            }
            self._positions[deal_id] = new_position
            self._trade_log.append({
                'deal_id': deal_id,
                'action': 'OPEN',
                'instrument': evaluation['instrument'],
                'notional': evaluation['notional_usd'],
                'entry_rate': signals.get('treasury_10yr', 4.5),
                'timestamp': datetime.utcnow().isoformat(),
            })

        # Hedge ratio for reporting
        bond_face = signals.get('bond_face_value', 231_000_000)
        bond_duration = signals.get('bond_duration', 7.0)
        rate_sens = signals.get('treasury_change_bps', 0)
        hedge_info = self.calculate_hedge_ratio(bond_face, bond_duration, rate_sens)

        self._last_run = datetime.utcnow()

        return {
            'agent': 'Apex',
            'deal_id': deal_id,
            'evaluation': evaluation,
            'existing_position': self._positions.get(deal_id),
            'position_action': position_action,
            'hedge_ratio': hedge_info,
            'active_positions_count': len(self._positions),
            'trade_log_length': len(self._trade_log),
            'timestamp': datetime.utcnow().isoformat(),
        }


# Singleton instance
apex = ApexAgent()

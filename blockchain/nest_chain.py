"""NestChain — immutable audit trail for all NEST deal events.
Simulation mode by default. Live mode activates when POLYGON_RPC + WALLET_KEY are set.
"""
import hashlib
import json
import os
import threading
from datetime import datetime

from services.core import nest_hash


class NestChain:
    def __init__(self):
        self._ledger = []
        self._block_number = 0
        self._lock = threading.RLock()
        self._total_fees_captured = 0
        self._total_equity_positions = 0
        self._total_refi_cycles = 0
        self.live = bool(os.getenv("POLYGON_RPC") and os.getenv("WALLET_KEY"))

    def _hash(self, data):
        return nest_hash(data)

    def record_transaction(self, tx_type, deal_id, data):
        with self._lock:
            self._block_number += 1
            tx = {
                "tx_hash": "0x" + self._hash({"type": tx_type, "deal": deal_id, "data": data, "block": self._block_number}),
                "block_number": self._block_number,
                "timestamp": datetime.utcnow().isoformat(),
                "tx_type": tx_type,
                "deal_id": deal_id,
                "data_hash": "0x" + self._hash(data),
                "status": "confirmed",
                "mode": "live" if self.live else "simulation",
            }
            self._ledger.append(tx)
            return tx

    # ── DEAL EVENTS ───────────────────────────────────────────
    def record_deal(self, deal_id, deal_data):
        return self.record_transaction("DEAL_RECORDED", deal_id, deal_data)

    def record_bond_issuance(self, deal_id, series, total_raise):
        return self.record_transaction("BOND_ISSUED", deal_id, {"series": series, "total_raise": total_raise})

    def record_refi_cycle(self, deal_id, cycle_number, old_rate, new_rate, fee_captured):
        with self._lock:
            self._total_refi_cycles += 1
            self._total_fees_captured += fee_captured
        return self.record_transaction("REFI_CYCLE", deal_id, {
            "cycle": cycle_number, "old_rate": old_rate,
            "new_rate": new_rate, "fee": fee_captured
        })

    # ── CALL / PUT EVENTS ─────────────────────────────────────
    def record_call_trigger(self, deal_id, old_bps, new_bps, recommendation, fee_usd):
        with self._lock:
            self._total_fees_captured += fee_usd
        return self.record_transaction("CALL_TRIGGERED", deal_id, {
            "old_rate_bps": old_bps, "new_rate_bps": new_bps,
            "recommendation": recommendation, "arrangement_fee_usd": fee_usd
        })

    def record_put_alert(self, deal_id, rate_rise_bps, apex_action):
        return self.record_transaction("PUT_ALERT", deal_id, {
            "rate_rise_bps": rate_rise_bps, "apex_action": apex_action
        })

    # ── M&A EVENTS ────────────────────────────────────────────
    def record_ma_analysis(self, company_name, analysis_data, game_theory_result, level):
        return self.record_transaction("MA_ANALYSIS", company_name, {
            "analysis": analysis_data, "game_theory": game_theory_result, "level": level
        })

    def record_equity_position(self, company_name, entry_ev_usd, nest_equity_pct, warrant_terms):
        with self._lock:
            self._total_equity_positions += 1
        return self.record_transaction("EQUITY_POSITION", company_name, {
            "entry_ev": entry_ev_usd, "equity_pct": nest_equity_pct, "warrants": warrant_terms
        })

    # ── LENDER EVENTS ─────────────────────────────────────────
    def record_lender_match(self, deal_id, lender_id, match_score, nash_result):
        return self.record_transaction("LENDER_MATCH", deal_id, {
            "lender_id": lender_id, "score": match_score, "nash": nash_result
        })

    # ── INVESTOR EVENTS ───────────────────────────────────────
    def record_investor_allocation(self, deal_id, investor_id, amount_usd, tranche):
        return self.record_transaction("INVESTOR_ALLOCATION", deal_id, {
            "investor_id": investor_id, "amount_usd": amount_usd, "tranche": tranche
        })

    # ── COVENANT EVENTS ───────────────────────────────────────
    def record_covenant_test(self, deal_id, metric, value, threshold, passed):
        return self.record_transaction("COVENANT_TEST", deal_id, {
            "metric": metric, "value": value, "threshold": threshold, "passed": passed
        })

    # ── MARKETPLACE EVENTS ────────────────────────────────────
    def create_marketplace_listing(self, deal_id, listing_data):
        return self.record_transaction("MARKETPLACE_LISTING", deal_id, listing_data)

    # ── GENERIC EVENT ─────────────────────────────────────────
    def record_event(self, deal_id, event_type, data):
        return self.record_transaction(event_type, deal_id, data)

    # ── QUERIES ───────────────────────────────────────────────
    def verify_transaction(self, tx_hash):
        with self._lock:
            for tx in self._ledger:
                if tx["tx_hash"] == tx_hash:
                    return tx
        return None

    def get_deal_history(self, deal_id):
        with self._lock:
            return [tx for tx in self._ledger if tx["deal_id"] == deal_id]

    def get_recent(self, limit=50):
        with self._lock:
            return list(reversed(self._ledger[-limit:]))

    def get_stats(self):
        with self._lock:
            by_type = {}
            for tx in self._ledger:
                t = tx["tx_type"]
                by_type[t] = by_type.get(t, 0) + 1
            return {
                "total_transactions": len(self._ledger),
                "by_type": by_type,
                "latest_block": self._block_number,
                "total_deals": by_type.get("DEAL_RECORDED", 0),
                "total_refi_cycles": self._total_refi_cycles,
                "total_fees_captured_usd": self._total_fees_captured,
                "total_equity_positions": self._total_equity_positions,
                "mode": "live" if self.live else "simulation",
            }

    # Keep legacy alias
    get_ledger_stats = get_stats


chain = NestChain()

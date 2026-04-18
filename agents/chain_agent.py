"""
Chain Agent - Blockchain transaction logging (simulation layer).

Records all deal events, refi cycles, and equity positions as immutable
audit trail entries. Generates deterministic SHA-256 hashes and stores
transaction logs in memory. No real blockchain dependency.
"""

import hashlib
import json
import uuid
from datetime import datetime, timezone

TX_TYPES = {
    "BOND_ISSUED",
    "REFI_CYCLE",
    "CALL_NOTICE",
    "PUT_NOTICE",
    "EQUITY_POSITION",
    "LENDER_MATCH",
}


class ChainAgent:
    def __init__(self):
        self._ledger: list[dict] = []
        self._block_counter: int = 0

    # ------------------------------------------------------------------
    # Core
    # ------------------------------------------------------------------

    def record_transaction(self, tx_type: str, deal_id: str, data: dict) -> dict:
        """Record an arbitrary transaction to the in-memory ledger.

        Parameters
        ----------
        tx_type : str
            One of TX_TYPES (BOND_ISSUED, REFI_CYCLE, etc.).
        deal_id : str
            Unique deal identifier.
        data : dict
            Payload specific to the transaction type.

        Returns
        -------
        dict with tx_hash, block_number, timestamp, tx_type, deal_id,
        data_hash, and status.
        """
        if tx_type not in TX_TYPES:
            raise ValueError(
                f"Unknown tx_type '{tx_type}'. Must be one of {sorted(TX_TYPES)}"
            )

        self._block_counter += 1
        timestamp = datetime.now(timezone.utc).isoformat()

        # Deterministic data hash from the payload
        data_canonical = json.dumps(data, sort_keys=True, default=str)
        data_hash = hashlib.sha256(data_canonical.encode()).hexdigest()

        # Transaction hash combines type + deal + data + timestamp
        tx_seed = f"{tx_type}|{deal_id}|{data_hash}|{timestamp}"
        tx_hash = hashlib.sha256(tx_seed.encode()).hexdigest()

        record = {
            "tx_hash": tx_hash,
            "block_number": self._block_counter,
            "timestamp": timestamp,
            "tx_type": tx_type,
            "deal_id": deal_id,
            "data": data,
            "data_hash": data_hash,
            "status": "confirmed",
        }

        self._ledger.append(record)
        return record

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    def record_refi_cycle(
        self,
        deal_id: str,
        cycle_number: int,
        old_rate: float,
        new_rate: float,
        fee_captured: float,
    ) -> dict:
        """Record a refinance cycle event."""
        data = {
            "cycle_number": cycle_number,
            "old_rate": old_rate,
            "new_rate": new_rate,
            "spread_reduction_bps": round((old_rate - new_rate) * 10_000),
            "fee_captured": fee_captured,
        }
        return self.record_transaction("REFI_CYCLE", deal_id, data)

    def record_bond_issuance(
        self, deal_id: str, series: list, total_raise: float
    ) -> dict:
        """Record a bond issuance event."""
        data = {
            "series": series,
            "total_raise": total_raise,
            "num_tranches": len(series),
        }
        return self.record_transaction("BOND_ISSUED", deal_id, data)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def verify_transaction(self, tx_hash: str) -> dict | None:
        """Look up a transaction by its hash. Returns the full record or None."""
        for record in self._ledger:
            if record["tx_hash"] == tx_hash:
                return record
        return None

    def get_deal_history(self, deal_id: str) -> list[dict]:
        """Return all transactions for a deal, sorted by timestamp."""
        return sorted(
            [r for r in self._ledger if r["deal_id"] == deal_id],
            key=lambda r: r["timestamp"],
        )

    def get_ledger_stats(self) -> dict:
        """Summary stats for the entire ledger."""
        by_type: dict[str, int] = {}
        for record in self._ledger:
            by_type[record["tx_type"]] = by_type.get(record["tx_type"], 0) + 1

        return {
            "total_transactions": len(self._ledger),
            "by_type": by_type,
            "latest_block_number": self._block_counter,
        }


# Module-level singleton
chain = ChainAgent()

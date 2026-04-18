"""Refi cycle model per nest_platform_schema.json."""
import uuid
from datetime import datetime

REFI_STATUSES = [
    "pending", "vector_triggered", "notice_issued",
    "book_building", "settled", "cancelled"
]
TRIGGER_TYPES = ["vector_agent", "manual", "scheduled"]


def new_refi_cycle(deal_id: str, bond_structure_id: str,
                   cycle_number: int) -> dict:
    now = datetime.utcnow().isoformat()
    return {
        "id": str(uuid.uuid4()),
        "deal_id": deal_id,
        "bond_structure_id": bond_structure_id,
        "cycle_number": cycle_number,
        "status": "pending",
        "trigger": {
            "triggered_by": "manual",
            "trigger_date": now,
            "rate_at_origination_pct": 0,
            "rate_at_trigger_pct": 0,
            "rate_improvement_bps": 0,
            "dscr_at_trigger": 0,
            "occupancy_at_trigger": 0,
            "credit_spread_change_bps": 0,
            "vector_composite_score": 0,
        },
        "execution": {
            "call_notice_date": None,
            "call_notice_blockchain_hash": None,
            "old_bonds_burned_hash": None,
            "new_bonds_minted_hash": None,
            "settlement_date": None,
            "settlement_hours": 0,
            "new_coupon_rate_pct": 0,
            "new_face_amount_usd": 0,
        },
        "economics": {
            "arrangement_fee_usd": 0,
            "arrangement_fee_pct": 0,
            "client_annual_savings_usd": 0,
            "cumulative_rate_reduction_bps": 0,
            "short_position_pl_usd": 0,
        },
        "blockchain": {
            "network": "polygon",
            "smart_contract_address": None,
            "transactions": [],
        },
        "created_at": now,
    }

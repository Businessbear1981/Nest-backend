"""Bond structure model per nest_platform_schema.json."""
import uuid
from datetime import datetime


STRUCTURE_TYPES = ["single_tranche", "dual_tranche", "multi_series"]
SERIES_LABELS = ["A", "B", "C"]
CLASSIFICATIONS = ["senior", "subordinated", "mezzanine"]
TAX_TREATMENTS = ["tax_exempt", "taxable"]
INVESTOR_TYPES = ["QIB_144A", "reg_d_506c", "accredited", "institutional"]
RATING_TARGETS = [
    "AAA", "AA", "A", "BBB_plus", "BBB", "BBB_minus",
    "BB_plus", "BB", "B", "unrated"
]
SURETY_TYPES = ["cash_surety_sbloc", "performance_bond", "lc", "parametric", "none"]
CALL_TYPES = ["optional", "make_whole", "extraordinary", "mandatory_sinking"]
PUT_TYPES = ["investor_put", "change_of_control", "performance"]


def new_bond_structure(deal_id: str, structure_type: str = "dual_tranche",
                       series: list = None) -> dict:
    now = datetime.utcnow().isoformat()
    return {
        "id": str(uuid.uuid4()),
        "deal_id": deal_id,
        "structure_type": structure_type,
        "governing_law": "Florida",
        "issuing_authority": "Florida LGFC",
        "bond_counsel": None,
        "trustee": None,
        "series": series or [],
        "b_tranche_overlay": {
            "proceeds_to_bank_aum": True,
            "bank_custodian": None,
            "hft_fund_allocation_pct": 100,
            "maturity_reserve_pct": 2.5,
            "client_balance_sheet_asset": True,
            "io_funded_from_proceeds": True,
            "bank_net_exposure_usd": 0,
        },
        "capital_stack": {
            "total_raise_usd": 0,
            "project_proceeds_usd": 0,
            "coupon_reserve_usd": 0,
            "surety_premium_usd": 0,
            "arrangement_fee_usd": 0,
            "contingency_usd": 0,
            "io_impound_usd": 0,
        },
        "created_at": now,
    }


def new_series(label: str = "A", face_amount: float = 0,
               ltc_pct: float = 75, coupon_rate: float = 7.0,
               duration_years: int = 5) -> dict:
    return {
        "series_id": str(uuid.uuid4()),
        "label": label,
        "classification": "senior" if label == "A" else "subordinated",
        "face_amount_usd": face_amount,
        "ltc_pct": ltc_pct,
        "cltv_pct": ltc_pct,
        "coupon_rate_pct": coupon_rate,
        "tax_treatment": "tax_exempt" if label == "A" else "taxable",
        "duration_years": duration_years,
        "investor_type": "QIB_144A",
        "rating_target": "A" if label == "A" else "BBB_minus",
        "surety_provider": "Hylant",
        "surety_type": "cash_surety_sbloc",
        "call_schedule": [],
        "put_schedule": [],
        "io_impound_months": 24,
        "maturity_reserve_pct": 2.5,
        "created_at": datetime.utcnow().isoformat(),
    }

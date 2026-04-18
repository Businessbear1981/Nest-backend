"""Deal model with full schema fields per nest_platform_schema.json."""
import uuid
from datetime import datetime


DEAL_STATUSES = [
    "intake", "underwriting", "structured", "placed",
    "active", "refi_cycle", "bridge", "closed"
]

ASSET_TYPES = [
    "senior_living", "mixed_use", "industrial",
    "multifamily", "office", "retail", "other"
]

PROJECT_TYPES = ["greenfield", "value_add", "stabilized", "shovel_ready"]

DEFAULT_CHECKLIST = {
    "phase_i_environmental": "not_started",
    "mai_appraisal": "not_started",
    "gmp_contract": "not_started",
    "operator_agreement": "none",
    "ahca_license": "not_started",
    "kpmg_feasibility": "not_engaged",
    "bond_counsel_engaged": False,
    "hylant_submission_ready": False,
}


def new_deal(name: str, project: dict = None, sponsor: dict = None) -> dict:
    now = datetime.utcnow().isoformat()
    deal_id = str(uuid.uuid4())
    return {
        "id": deal_id,
        "name": name,
        "slug": name.lower().replace(" ", "-"),
        "status": "intake",
        "created_at": now,
        "updated_at": now,
        "project": project or {},
        "sponsor": sponsor or {},
        "readiness_score": 0,
        "readiness_checklist": dict(DEFAULT_CHECKLIST),
        "team": {
            "lead_banker": None,
            "bond_counsel": None,
            "bank_partner": None,
            "hylant_contact": None,
            "baker_tilly_contact": None,
            "kpmg_contact": None,
        },
    }


def compute_readiness_score(checklist: dict) -> int:
    """Score 0-100 based on checklist completion."""
    weights = {
        "phase_i_environmental": 15,
        "mai_appraisal": 15,
        "gmp_contract": 15,
        "operator_agreement": 10,
        "ahca_license": 10,
        "kpmg_feasibility": 15,
        "bond_counsel_engaged": 10,
        "hylant_submission_ready": 10,
    }
    score = 0
    for key, weight in weights.items():
        val = checklist.get(key)
        if isinstance(val, bool):
            score += weight if val else 0
        elif val in ("approved", "executed", "delivered"):
            score += weight
        elif val in ("received", "in_progress", "negotiating", "applied", "sow_review"):
            score += int(weight * 0.5)
        elif val in ("ordered", "loi", "not_engaged", "not_started", "none"):
            score += 0
    return min(100, score)

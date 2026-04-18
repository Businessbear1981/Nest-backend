"""Full deal lifecycle routes — CRUD, bond structure, refi, covenants, checklist, memo."""
import threading
from flask import Blueprint, jsonify, request, current_app
from datetime import datetime
from models.deal import new_deal, compute_readiness_score, DEAL_STATUSES
from models.bond import new_bond_structure, new_series
from models.refi import new_refi_cycle

deals_bp = Blueprint("deals", __name__)

# In-memory stores (swap for Supabase later)
_lock = threading.RLock()
_deals = {}
_bonds = {}       # deal_id -> bond_structure
_refis = {}       # deal_id -> [refi_cycle, ...]
_covenants = {}   # deal_id -> [covenant, ...]


def _ts():
    return datetime.utcnow().isoformat()


def _ok(data, code=200):
    return jsonify({"success": True, "data": data, "error": None, "timestamp": _ts()}), code


def _err(msg, code=400):
    return jsonify({"success": False, "data": None, "error": msg, "timestamp": _ts()}), code


# ── Seed deals ──────────────────────────────────────────────────
def _seed():
    seeds = [
        {
            "name": "Life Star Pointe Loop",
            "project": {
                "name": "Life Star Pointe Loop",
                "address": "426 Pointe Loop Blvd",
                "city": "Kissimmee", "state": "FL", "zip": "34747",
                "asset_type": "senior_living", "project_type": "greenfield",
                "total_project_cost_usd": 231_000_000,
                "units": 364, "description": "364-unit IL/AL/MC campus"
            },
            "sponsor": {
                "entity_name": "Life Star Senior Living LLC",
                "contact_name": "Development Team", "track_record_projects": 8,
            },
        },
        {
            "name": "Meridian Cove",
            "project": {
                "name": "Meridian Cove Mixed-Use",
                "city": "Tampa", "state": "FL",
                "asset_type": "mixed_use", "project_type": "greenfield",
                "total_project_cost_usd": 142_000_000,
                "units": 280, "description": "280 units + 45K SF retail"
            },
            "sponsor": {"entity_name": "Meridian Development Group"},
        },
        {
            "name": "Palmetto Ridge",
            "project": {
                "name": "Palmetto Ridge Industrial",
                "city": "Lakeland", "state": "FL",
                "asset_type": "industrial", "project_type": "shovel_ready",
                "total_project_cost_usd": 78_000_000,
                "square_footage": 425_000,
                "description": "425K SF Class A industrial / cold storage"
            },
            "sponsor": {"entity_name": "Palmetto Industrial Partners"},
        },
    ]
    with _lock:
        for s in seeds:
            d = new_deal(s["name"], s.get("project"), s.get("sponsor"))
            d["status"] = "underwriting"
            _deals[d["id"]] = d


_seed()


# ── Deal CRUD ───────────────────────────────────────────────────

@deals_bp.route("", methods=["POST"])
def create_deal():
    body = request.get_json() or {}
    name = body.get("name")
    if not name:
        return _err("name is required")
    d = new_deal(name, body.get("project"), body.get("sponsor"))
    with _lock:
        _deals[d["id"]] = d
    return _ok(d, 201)


@deals_bp.route("", methods=["GET"])
def list_deals():
    status = request.args.get("status")
    with _lock:
        result = list(_deals.values())
    if status:
        result = [d for d in result if d["status"] == status]
    result.sort(key=lambda d: d["created_at"], reverse=True)
    return _ok(result)


@deals_bp.route("/<deal_id>", methods=["GET"])
def get_deal(deal_id):
    with _lock:
        d = _deals.get(deal_id)
    if not d:
        return _err("Deal not found", 404)
    return _ok(d)


@deals_bp.route("/<deal_id>", methods=["PATCH"])
def update_deal(deal_id):
    body = request.get_json() or {}
    with _lock:
        d = _deals.get(deal_id)
        if not d:
            return _err("Deal not found", 404)
        if "status" in body and body["status"] in DEAL_STATUSES:
            d["status"] = body["status"]
        if "project" in body:
            d["project"].update(body["project"])
        if "sponsor" in body:
            d["sponsor"].update(body["sponsor"])
        if "team" in body:
            d["team"].update(body["team"])
        d["updated_at"] = _ts()
    return _ok(d)


# ── Bond Structure ──────────────────────────────────────────────

@deals_bp.route("/<deal_id>/bond", methods=["POST"])
def create_bond(deal_id):
    with _lock:
        if deal_id not in _deals:
            return _err("Deal not found", 404)
    body = request.get_json() or {}
    structure_type = body.get("structure_type", "dual_tranche")

    series_input = body.get("series", [])
    series_list = []
    if not series_input:
        tpc = _deals[deal_id]["project"].get("total_project_cost_usd", 100_000_000)
        a_face = tpc * 0.75
        b_face = tpc * 0.07
        series_list.append(new_series("A", a_face, 75, 7.0, 5))
        series_list.append(new_series("B", b_face, 82, 12.0, 5))
    else:
        for s in series_input:
            series_list.append(new_series(
                s.get("label", "A"),
                s.get("face_amount_usd", 0),
                s.get("ltc_pct", 75),
                s.get("coupon_rate_pct", 7.0),
                s.get("duration_years", 5),
            ))

    bond = new_bond_structure(deal_id, structure_type, series_list)
    total_face = sum(s["face_amount_usd"] for s in series_list)
    bond["capital_stack"] = {
        "total_raise_usd": total_face * 1.065,
        "project_proceeds_usd": total_face,
        "coupon_reserve_usd": total_face * 0.025,
        "surety_premium_usd": total_face * 0.015,
        "arrangement_fee_usd": total_face * 0.025,
        "contingency_usd": total_face * 0.005,
        "io_impound_usd": total_face * 0.02,
    }

    with _lock:
        _bonds[deal_id] = bond
    return _ok(bond, 201)


@deals_bp.route("/<deal_id>/bond", methods=["GET"])
def get_bond(deal_id):
    with _lock:
        bond = _bonds.get(deal_id)
    if not bond:
        return _err("No bond structure for this deal", 404)
    return _ok(bond)


# ── Refi Cycles ─────────────────────────────────────────────────

@deals_bp.route("/<deal_id>/refi", methods=["POST"])
def trigger_refi(deal_id):
    with _lock:
        if deal_id not in _deals:
            return _err("Deal not found", 404)
        bond = _bonds.get(deal_id)
        if not bond:
            return _err("No bond structure — create bond first", 400)
        existing = _refis.get(deal_id, [])
        cycle_num = len(existing) + 1
        refi = new_refi_cycle(deal_id, bond["id"], cycle_num)
        body = request.get_json() or {}
        if "trigger" in body:
            refi["trigger"].update(body["trigger"])
        existing.append(refi)
        _refis[deal_id] = existing
    return _ok(refi, 201)


@deals_bp.route("/<deal_id>/refis", methods=["GET"])
def list_refis(deal_id):
    with _lock:
        refis = _refis.get(deal_id, [])
    return _ok(refis)


# ── Covenants ───────────────────────────────────────────────────

@deals_bp.route("/<deal_id>/covenants", methods=["GET"])
def get_covenants(deal_id):
    with _lock:
        covs = _covenants.get(deal_id, [])
    return _ok(covs)


@deals_bp.route("/<deal_id>/covenants/test", methods=["POST"])
def test_covenants(deal_id):
    import uuid as _uuid
    with _lock:
        covs = _covenants.get(deal_id, [])
        if not covs:
            bond = _bonds.get(deal_id)
            if bond:
                covs = _default_covenants(deal_id, bond["id"])
                _covenants[deal_id] = covs

    body = request.get_json() or {}
    metrics = body.get("metrics", {})
    results = []
    now = _ts()
    for cov in covs:
        metric_val = metrics.get(cov["metric"], cov.get("last_test_value"))
        if metric_val is None:
            metric_val = 0
        threshold = cov["threshold_value"]
        if cov["threshold_type"] == "minimum":
            passed = metric_val >= threshold
        else:
            passed = metric_val <= threshold
        cov["last_test_date"] = now
        cov["last_test_value"] = metric_val
        cov["status"] = "green" if passed else "red"
        results.append({
            "covenant_id": cov["id"],
            "metric": cov["metric"],
            "value": metric_val,
            "threshold": threshold,
            "threshold_type": cov["threshold_type"],
            "passed": passed,
            "status": cov["status"],
        })
    return _ok(results)


def _default_covenants(deal_id, bond_id):
    import uuid as _uuid
    defaults = [
        ("dscr", "minimum", 1.5, "quarterly"),
        ("ltv", "maximum", 75, "quarterly"),
        ("cash_flow_leverage", "maximum", 2.0, "quarterly"),
        ("balance_sheet_leverage", "maximum", 2.5, "quarterly"),
        ("debt_to_ebitda", "maximum", 6.5, "quarterly"),
        ("interest_coverage_ratio", "minimum", 2.25, "quarterly"),
        ("occupancy_pct", "minimum", 60, "monthly"),
    ]
    covs = []
    for metric, thresh_type, thresh_val, freq in defaults:
        covs.append({
            "id": str(_uuid.uuid4()),
            "deal_id": deal_id,
            "bond_structure_id": bond_id,
            "covenant_type": "financial_maintenance",
            "metric": metric,
            "threshold_type": thresh_type,
            "threshold_value": thresh_val,
            "test_frequency": freq,
            "last_test_date": None,
            "last_test_value": None,
            "status": "green",
            "cure_period_days": 30,
            "cure_deadline": None,
            "breach_history": [],
        })
    return covs


# ── Readiness Checklist ─────────────────────────────────────────

@deals_bp.route("/<deal_id>/checklist", methods=["GET"])
def get_checklist(deal_id):
    with _lock:
        d = _deals.get(deal_id)
    if not d:
        return _err("Deal not found", 404)
    return _ok({
        "checklist": d["readiness_checklist"],
        "readiness_score": d["readiness_score"],
    })


@deals_bp.route("/<deal_id>/checklist", methods=["PATCH"])
def update_checklist(deal_id):
    body = request.get_json() or {}
    with _lock:
        d = _deals.get(deal_id)
        if not d:
            return _err("Deal not found", 404)
        for key, val in body.items():
            if key in d["readiness_checklist"]:
                d["readiness_checklist"][key] = val
        d["readiness_score"] = compute_readiness_score(d["readiness_checklist"])
        d["updated_at"] = _ts()
    return _ok({
        "checklist": d["readiness_checklist"],
        "readiness_score": d["readiness_score"],
    })


# ── Memo Generation ─────────────────────────────────────────────

@deals_bp.route("/<deal_id>/memo", methods=["POST"])
def generate_memo(deal_id):
    with _lock:
        d = _deals.get(deal_id)
    if not d:
        return _err("Deal not found", 404)
    body = request.get_json() or {}
    memo_type = body.get("memo_type", "executive_summary")
    morgan = current_app.config.get("MORGAN")
    if not morgan:
        return _err("Morgan agent not initialized", 500)
    valid_types = [
        "credit_memo", "executive_summary", "investor_teaser",
        "refi_notice", "term_sheet_cover"
    ]
    content_type = memo_type if memo_type in valid_types else "executive_summary"
    context = {
        "deal": d,
        "bond": _bonds.get(deal_id),
        "memo_type": memo_type,
    }
    result = morgan.generate(content_type, context)
    return _ok(result)


# ── Pipeline Metrics ────────────────────────────────────────────

@deals_bp.route("/pipeline", methods=["GET"])
def pipeline():
    with _lock:
        deals_list = list(_deals.values())
    active = [d for d in deals_list if d["status"] != "closed"]
    total_usd = sum(
        d.get("project", {}).get("total_project_cost_usd", 0) for d in active
    )
    by_status = {}
    for d in deals_list:
        s = d.get("status", "unknown")
        by_status[s] = by_status.get(s, 0) + 1
    return _ok({
        "total_pipeline_usd": total_usd,
        "deal_count": len(active),
        "by_status": by_status,
    })

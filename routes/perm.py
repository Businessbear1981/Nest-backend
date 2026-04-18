"""Perm debt rolloff routes — Bridge agent interface."""
import threading
import uuid
from flask import Blueprint, jsonify, request
from datetime import datetime

perm_bp = Blueprint("perm", __name__)

_lock = threading.RLock()
_rolloffs = {}  # deal_id -> perm_debt_rolloff


def _ts():
    return datetime.utcnow().isoformat()


def _ok(data, code=200):
    return jsonify({"success": True, "data": data, "error": None, "timestamp": _ts()}), code


def _err(msg, code=400):
    return jsonify({"success": False, "data": None, "error": msg, "timestamp": _ts()}), code


PERM_STATUSES = [
    "pre_qual_initiated", "term_sheet_issued", "in_underwriting",
    "committed", "closed"
]


@perm_bp.route("/<deal_id>/initiate", methods=["POST"])
def initiate_perm(deal_id):
    body = request.get_json() or {}
    rolloff = {
        "id": str(uuid.uuid4()),
        "deal_id": deal_id,
        "status": "pre_qual_initiated",
        "bank_partner": body.get("bank_partner"),
        "bank_contact": body.get("bank_contact"),
        "months_before_stabilization": body.get("months_before_stabilization", 18),
        "pre_qual_date": _ts(),
        "term_sheet_date": None,
        "term_sheet_rate": None,
        "term_sheet_spread_bps": None,
        "loan_amount_usd": body.get("loan_amount_usd", 0),
        "loan_term_years": body.get("loan_term_years", 25),
        "ae_placement_fee_pct": 0.5,
        "ae_placement_fee_usd": 0,
        "close_date": None,
    }
    with _lock:
        _rolloffs[deal_id] = rolloff
    return _ok(rolloff, 201)


@perm_bp.route("/<deal_id>/status", methods=["GET"])
def perm_status(deal_id):
    with _lock:
        rolloff = _rolloffs.get(deal_id)
    if not rolloff:
        return _err("No perm debt process for this deal", 404)
    return _ok(rolloff)

"""Direct lender sourcing routes — LenderScout agent interface."""
from flask import Blueprint, jsonify, request
from datetime import datetime

lenders_api_bp = Blueprint("lenders_api", __name__)


def _ts():
    return datetime.utcnow().isoformat()


def _ok(data, code=200):
    return jsonify({"success": True, "data": data, "error": None, "timestamp": _ts()}), code


def _err(msg, code=400):
    return jsonify({"success": False, "data": None, "error": msg, "timestamp": _ts()}), code


@lenders_api_bp.route("", methods=["GET"])
def get_lenders():
    """Get all lenders in database + seed data."""
    try:
        from agents.lender_scout import lender_scout
        return _ok(lender_scout.SEED_LENDERS)
    except Exception as e:
        return _err(str(e), 500)


@lenders_api_bp.route("", methods=["POST"])
def add_lender():
    """Add a lender manually."""
    body = request.get_json() or {}
    if not body.get("name"):
        return _err("name required")
    return _ok(body, 201)


@lenders_api_bp.route("/search", methods=["POST"])
def search_lenders_for_deal():
    """Run LenderScout to find matching lenders for a deal."""
    body = request.get_json() or {}
    deal_id = body.get("deal_id", "unknown")
    try:
        from agents.lender_scout import lender_scout
        result = lender_scout.run(deal_id=deal_id, deal_data=body.get("deal", {}))
        return _ok(result)
    except Exception as e:
        return _err(str(e), 500)


@lenders_api_bp.route("/pipeline", methods=["GET"])
def get_pipeline():
    """Get all active lender pipelines."""
    stages = ["TARGETED", "OUTREACH_SENT", "RESPONDED", "TERM_SHEET_RECEIVED", "COMMITTED", "CLOSED", "PASSED"]
    return _ok({stage: [] for stage in stages})

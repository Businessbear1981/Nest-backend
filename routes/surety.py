"""Insurance surety platform routes — provider matching, premium calculation, outreach."""
from flask import Blueprint, jsonify, request
from datetime import datetime

surety_bp = Blueprint("surety", __name__)


def _ts():
    return datetime.utcnow().isoformat()


def _ok(data, code=200):
    return jsonify({"success": True, "data": data, "error": None, "timestamp": _ts()}), code


def _err(msg, code=400):
    return jsonify({"success": False, "data": None, "error": msg, "timestamp": _ts()}), code


@surety_bp.route("/providers", methods=["GET"])
def list_providers():
    """List all surety/insurance providers."""
    from agents.surety_scout import SURETY_PROVIDERS
    return _ok(SURETY_PROVIDERS)


@surety_bp.route("/premium", methods=["POST"])
def calculate_premium():
    """Calculate surety premium for a deal."""
    body = request.get_json() or {}
    from agents.surety_scout import surety_scout
    result = surety_scout.calculate_premium(body)
    return _ok(result)


@surety_bp.route("/match", methods=["POST"])
def match_providers():
    """Score and rank providers for a deal."""
    body = request.get_json() or {}
    from agents.surety_scout import surety_scout
    result = surety_scout.match_providers(body)
    return _ok(result)


@surety_bp.route("/outreach", methods=["POST"])
def generate_outreach():
    """Generate outreach letter to a surety provider."""
    body = request.get_json() or {}
    provider = body.get("provider", {})
    deal = body.get("deal", {})
    from agents.surety_scout import surety_scout
    premium = surety_scout.calculate_premium(deal)
    result = surety_scout.generate_outreach(provider, deal, premium)
    return _ok(result)


@surety_bp.route("/run/<deal_id>", methods=["POST"])
def full_run(deal_id):
    """Full SuretyScout run for a deal."""
    body = request.get_json() or {}
    from agents.surety_scout import surety_scout
    result = surety_scout.run(deal_id, body)
    return _ok(result)

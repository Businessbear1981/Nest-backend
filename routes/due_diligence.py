"""Sparrow Capital Due Diligence routes — 8-phase checklist, shovel-ready, timeline."""
from flask import Blueprint, jsonify, request
from datetime import datetime
from services.due_diligence import dd_engine

dd_bp = Blueprint("due_diligence", __name__)


def _ts():
    return datetime.utcnow().isoformat()


def _ok(data, code=200):
    return jsonify({"success": True, "data": data, "error": None, "timestamp": _ts()}), code


def _err(msg, code=400):
    return jsonify({"success": False, "data": None, "error": msg, "timestamp": _ts()}), code


@dd_bp.route("/<deal_id>/init", methods=["POST"])
def init_checklist(deal_id):
    """Initialize full DD checklist for a deal."""
    body = request.get_json() or {}
    result = dd_engine.initialize_checklist(deal_id, body.get("start_date"))
    return _ok(result, 201)


@dd_bp.route("/<deal_id>/checklist", methods=["GET"])
def get_checklist(deal_id):
    """Get DD checklist summary."""
    result = dd_engine.get_checklist_summary(deal_id)
    if "error" in result:
        return _err(result["error"], 404)
    return _ok(result)


@dd_bp.route("/<deal_id>/checklist/<item_id>", methods=["PATCH"])
def update_item(deal_id, item_id):
    """Update a single checklist item."""
    body = request.get_json() or {}
    result = dd_engine.update_item(
        deal_id, item_id,
        status=body.get("status", "in_progress"),
        document_id=body.get("document_id"),
        notes=body.get("notes"),
    )
    if "error" in result:
        return _err(result["error"], 404)
    return _ok(result)


@dd_bp.route("/<deal_id>/shovel-ready", methods=["GET"])
def shovel_ready(deal_id):
    """Assess shovel-ready status (10 criteria)."""
    result = dd_engine.shovel_ready_assessment(deal_id)
    return _ok(result)


@dd_bp.route("/<deal_id>/timeline", methods=["GET"])
def timeline(deal_id):
    """Get 180-day milestone timeline."""
    start_date = request.args.get("start_date")
    result = dd_engine.get_timeline(deal_id, start_date)
    return _ok(result)


@dd_bp.route("/phases", methods=["GET"])
def list_phases():
    """List all DD phases and their items."""
    from services.due_diligence import DD_PHASES
    return _ok(DD_PHASES)


@dd_bp.route("/third-parties", methods=["GET"])
def list_third_parties():
    """List required third-party engagements."""
    from services.due_diligence import THIRD_PARTY_FIRMS
    return _ok(THIRD_PARTY_FIRMS)

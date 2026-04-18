from flask import Blueprint, current_app, jsonify, request

from agents.morgan import CONTENT_TYPES
from services.auth import require_auth

marketing_bp = Blueprint("marketing", __name__)


def _morgan():
    return current_app.config["MORGAN"]


def _aria():
    return current_app.config["ARIA"]


def _sterling():
    return current_app.config["STERLING"]


# ---------- Morgan (content) ----------

@marketing_bp.get("/content-types")
def content_types():
    return jsonify([
        {"value": k, "label": v["label"]} for k, v in CONTENT_TYPES.items()
    ])


@marketing_bp.post("/generate")
@require_auth("admin")
def generate():
    body = request.get_json(silent=True) or {}
    content_type = body.get("content_type")
    context = body.get("context") or {}
    if not content_type:
        return jsonify({"error": "content_type required"}), 400
    try:
        record = _morgan().generate(content_type, context)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(record)


@marketing_bp.post("/batch")
@require_auth("admin")
def batch():
    body = request.get_json(silent=True) or {}
    deal_id = body.get("deal_id")
    context = body.get("context") or {}
    if not deal_id:
        return jsonify({"error": "deal_id required"}), 400
    return jsonify(_morgan().generate_batch(deal_id, context))


@marketing_bp.get("/history")
@require_auth("admin")
def history():
    limit = int(request.args.get("limit", 50))
    return jsonify(_morgan().history(limit=limit))


@marketing_bp.get("/history/<gen_id>")
@require_auth("admin")
def history_one(gen_id: str):
    rec = _morgan().get(gen_id)
    if rec is None:
        return jsonify({"error": "not_found"}), 404
    return jsonify(rec)


# ---------- Aria (outreach) ----------

@marketing_bp.post("/outreach")
@require_auth("admin")
def outreach():
    """Aria-backed: draft and (symbolically) send an outreach email."""
    body = request.get_json(silent=True) or {}
    lead_id = body.get("lead_id")
    attempt = int(body.get("attempt", 1))
    if not lead_id:
        return jsonify({"error": "lead_id required"}), 400
    try:
        draft = _aria().generate_follow_up(lead_id, attempt)
    except KeyError:
        return jsonify({"error": "lead_not_found"}), 404
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    draft["sent"] = bool(body.get("send", False))
    return jsonify(draft)


@marketing_bp.post("/proposal")
@require_auth("admin")
def proposal():
    body = request.get_json(silent=True) or {}
    lead_id = body.get("lead_id")
    concept = body.get("deal_concept")
    if not lead_id:
        return jsonify({"error": "lead_id required"}), 400
    try:
        return jsonify(_aria().draft_proposal(lead_id, concept))
    except KeyError:
        return jsonify({"error": "lead_not_found"}), 404


@marketing_bp.post("/inbound/classify")
@require_auth("admin")
def classify_inbound():
    body = request.get_json(silent=True) or {}
    msg = body.get("message", "")
    sender = body.get("sender")
    return jsonify(_aria().classify_inbound(msg, sender))


@marketing_bp.post("/intake")
def intake():
    body = request.get_json(silent=True) or {}
    try:
        return jsonify(_aria().intake(body))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@marketing_bp.get("/leads")
@require_auth("admin")
def leads():
    return jsonify(_aria().leads())


# ---------- Sterling (IR) ----------

@marketing_bp.get("/investors")
@require_auth("admin")
def investors():
    return jsonify(_sterling().investors())


@marketing_bp.post("/investors/match")
@require_auth("admin")
def match_investors():
    body = request.get_json(silent=True) or {}
    return jsonify(_sterling().match_investors(body.get("deal") or body))


@marketing_bp.post("/investors/update")
@require_auth("admin")
def investor_update():
    body = request.get_json(silent=True) or {}
    investor_id = body.get("investor_id")
    deal_id = body.get("deal_id")
    if not investor_id or not deal_id:
        return jsonify({"error": "investor_id and deal_id required"}), 400
    try:
        return jsonify(_sterling().generate_investor_update(investor_id, deal_id, body.get("deal")))
    except KeyError:
        return jsonify({"error": "investor_not_found"}), 404


@marketing_bp.post("/book/indication")
@require_auth("admin")
def book_indication():
    body = request.get_json(silent=True) or {}
    return jsonify(_sterling().add_indication(
        body.get("deal_id"), body.get("investor_id"), body.get("amount", 0)
    ))


@marketing_bp.post("/book/build")
@require_auth("admin")
def book_build():
    body = request.get_json(silent=True) or {}
    return jsonify(_sterling().manage_book_building(
        body.get("deal_id"), body.get("target_raise")
    ))

"""Bond grading, project audit, and bond optimization routes."""
from flask import Blueprint, jsonify, request
from datetime import datetime

bond_tools_bp = Blueprint("bond_tools", __name__)


def _ts():
    return datetime.utcnow().isoformat()


def _ok(data, code=200):
    return jsonify({"success": True, "data": data, "error": None, "timestamp": _ts()}), code


def _err(msg, code=400):
    return jsonify({"success": False, "data": None, "error": msg, "timestamp": _ts()}), code


# ── Bond Grading ────────────────────────────────────────────────

@bond_tools_bp.route("/grade", methods=["POST"])
def grade_bond():
    """Grade a bond structure and identify rating."""
    body = request.get_json() or {}
    from services.bond_grader import bond_grader
    result = bond_grader.grade_bond(
        deal_data=body.get("deal", {}),
        bond_data=body.get("bond", {}),
        credit_metrics=body.get("credit_metrics", {}),
    )
    return _ok(result)


@bond_tools_bp.route("/grade/criteria", methods=["GET"])
def rating_criteria():
    """List S&P-aligned rating criteria."""
    from services.bond_grader import RATING_CRITERIA
    return _ok(RATING_CRITERIA)


@bond_tools_bp.route("/grade/enhancements", methods=["GET"])
def structural_enhancements():
    """List available structural enhancements and their impact."""
    from services.bond_grader import STRUCTURAL_ENHANCEMENTS
    return _ok(STRUCTURAL_ENHANCEMENTS)


# ── Project Audit ───────────────────────────────────────────────

@bond_tools_bp.route("/audit", methods=["POST"])
def audit_deal():
    """Run full project audit."""
    body = request.get_json() or {}
    from agents.auditor import auditor
    result = auditor.audit_deal(
        deal=body.get("deal", {}),
        bond=body.get("bond"),
        checklist=body.get("checklist"),
        credit_metrics=body.get("credit_metrics"),
    )
    return _ok(result)


@bond_tools_bp.route("/audit/report", methods=["POST"])
def audit_report():
    """Generate formatted audit report."""
    body = request.get_json() or {}
    from agents.auditor import auditor
    audit_result = body.get("audit_result", {})
    report = auditor.generate_audit_report(audit_result)
    return _ok({"report": report})


# ── Bond Optimization ──────────────────────────────────────────

@bond_tools_bp.route("/optimize", methods=["POST"])
def optimize_bond():
    """Run bond optimization analysis."""
    body = request.get_json() or {}
    from agents.bond_optimizer import bond_optimizer
    result = bond_optimizer.optimize(
        deal_data=body.get("deal", {}),
        bond_data=body.get("bond", {}),
        market_signals=body.get("market_signals", {}),
    )
    return _ok(result)


@bond_tools_bp.route("/optimize/call-analysis", methods=["POST"])
def call_analysis():
    """Analyze whether to execute a bond call."""
    body = request.get_json() or {}
    from agents.bond_optimizer import bond_optimizer
    result = bond_optimizer.analyze_call_opportunity(
        bond_data=body.get("bond", {}),
        market_signals=body.get("market_signals", {}),
        project_schedule=body.get("project_schedule", {}),
    )
    return _ok(result)


@bond_tools_bp.route("/optimize/new-issuance", methods=["POST"])
def new_issuance():
    """Calculate new bond issuance with fee schedule."""
    body = request.get_json() or {}
    from agents.bond_optimizer import bond_optimizer
    result = bond_optimizer.calculate_new_issuance(body)
    return _ok(result)


@bond_tools_bp.route("/optimize/savings", methods=["POST"])
def savings_analysis():
    """Calculate savings from a call/refi action."""
    body = request.get_json() or {}
    from agents.bond_optimizer import bond_optimizer
    result = bond_optimizer.calculate_savings(
        current_bond=body.get("current_bond", {}),
        proposed_terms=body.get("proposed_terms", {}),
    )
    return _ok(result)

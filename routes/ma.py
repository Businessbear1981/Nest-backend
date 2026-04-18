"""M&A Intelligence routes — Merlin agent interface."""
from flask import Blueprint, jsonify, request
from datetime import datetime

ma_bp = Blueprint("ma", __name__)


def _ts():
    return datetime.utcnow().isoformat()


def _ok(data, code=200):
    return jsonify({"success": True, "data": data, "error": None, "timestamp": _ts()}), code


def _err(msg, code=400):
    return jsonify({"success": False, "data": None, "error": msg, "timestamp": _ts()}), code


@ma_bp.route("/targets", methods=["GET"])
def get_targets():
    """List all M&A targets."""
    return _ok([])  # Will be populated once Supabase is connected


@ma_bp.route("/analyze", methods=["POST"])
def analyze_company():
    """Run full Merlin analysis on a company."""
    body = request.get_json() or {}
    company_name = body.get("company_name")
    if not company_name:
        return _err("company_name required")
    try:
        from agents.merlin import merlin
        result = merlin.run_full_analysis(
            company_name=company_name,
            naics_code=body.get("naics_code"),
            company_data=body.get("company_data"),
        )
        return _ok(result)
    except Exception as e:
        return _err(str(e), 500)


@ma_bp.route("/game-theory", methods=["POST"])
def run_game_theory():
    """Run 3-level game theory analysis."""
    body = request.get_json() or {}
    try:
        from game_theory.engine import game_engine
        result = game_engine.run_full_analysis(
            analysis_type=body.get("analysis_type", "ma_acquisition"),
            primary_data=body.get("primary_data", {}),
            secondary_data=body.get("secondary_data", {}),
            history=body.get("history", []),
        )
        return _ok(result)
    except Exception as e:
        return _err(str(e), 500)


@ma_bp.route("/irr", methods=["POST"])
def compute_irr():
    """Compute IRR model for acquisition."""
    body = request.get_json() or {}
    try:
        from agents.merlin import merlin
        result = merlin.model_irr(
            ebitda=body.get("ebitda_usd", 3_000_000),
            entry_multiple=body.get("entry_multiple", 6.5),
            exit_multiple=body.get("exit_multiple", 8.5),
            hold_years=body.get("hold_years", 5),
            growth_rate=body.get("growth_rate_pct", 15) / 100,
            debt_pct=body.get("debt_pct", 0.50),
        )
        return _ok(result)
    except Exception as e:
        return _err(str(e), 500)


@ma_bp.route("/pipeline", methods=["GET"])
def get_pipeline():
    """Get M&A pipeline by stage."""
    return _ok({
        "identified": [], "analyzing": [], "outreach": [], "loi": [],
        "dd": [], "committed": [], "closed": [], "passed": [],
    })


@ma_bp.route("/digest", methods=["GET"])
def get_digest():
    """Get today's Merlin morning digest."""
    return _ok({"digest": "Good morning. No scans run today. Use POST /api/ma/analyze to analyze a target."})

"""Market signals routes — ingest data, Vector scoring."""
import threading
from flask import Blueprint, jsonify, request
from datetime import datetime

market_bp = Blueprint("market", __name__)

_lock = threading.RLock()
_signals = []  # list of signal snapshots


def _ts():
    return datetime.utcnow().isoformat()


def _ok(data, code=200):
    return jsonify({"success": True, "data": data, "error": None, "timestamp": _ts()}), code


def _err(msg, code=400):
    return jsonify({"success": False, "data": None, "error": msg, "timestamp": _ts()}), code


# Default market state
DEFAULT_SIGNALS = {
    "treasury_10yr_pct": 4.25,
    "treasury_10yr_change_bps": -5,
    "sofr_pct": 4.30,
    "credit_spread_ig_bps": 125,
    "credit_spread_hy_bps": 375,
    "tlt_price": 92.50,
    "vix": 18.5,
    "refi_market_access": "open_favorable",
}


@market_bp.route("/signals", methods=["POST"])
def ingest_signals():
    body = request.get_json() or {}
    signals = body.get("signals", DEFAULT_SIGNALS)

    # Simple Vector score computation (placeholder until Vector agent built)
    score = _compute_vector_score(signals)
    recommendation = _vector_recommendation(score)

    entry = {
        "id": len(_signals) + 1,
        "captured_at": _ts(),
        "signals": signals,
        "vector_score": score,
        "vector_recommendation": recommendation,
        "apex_short_active": False,
        "apex_position": None,
    }

    with _lock:
        _signals.append(entry)
        if len(_signals) > 1000:
            _signals.pop(0)

    return _ok(entry, 201)


@market_bp.route("/signals/latest", methods=["GET"])
def latest_signals():
    with _lock:
        if _signals:
            return _ok(_signals[-1])
    # Return defaults if no signals ingested yet
    score = _compute_vector_score(DEFAULT_SIGNALS)
    return _ok({
        "captured_at": _ts(),
        "signals": DEFAULT_SIGNALS,
        "vector_score": score,
        "vector_recommendation": _vector_recommendation(score),
        "apex_short_active": False,
        "apex_position": None,
    })


def _compute_vector_score(signals: dict) -> int:
    """Simplified Vector scoring — 0-100 composite."""
    score = 50  # neutral start

    # Treasury change: negative = favorable for calls
    t_change = signals.get("treasury_10yr_change_bps", 0)
    if t_change < -25:
        score += 20
    elif t_change < -10:
        score += 10
    elif t_change > 25:
        score -= 15
    elif t_change > 10:
        score -= 8

    # VIX: low = stable
    vix = signals.get("vix", 20)
    if vix < 15:
        score += 10
    elif vix > 25:
        score -= 10
    elif vix > 35:
        score -= 20

    # Credit spreads: tighter = better
    ig_spread = signals.get("credit_spread_ig_bps", 150)
    if ig_spread < 100:
        score += 10
    elif ig_spread > 200:
        score -= 10

    # Market access
    access = signals.get("refi_market_access", "open_neutral")
    if access == "open_favorable":
        score += 10
    elif access == "restricted":
        score -= 15
    elif access == "closed":
        score -= 25

    return max(0, min(100, score))


def _vector_recommendation(score: int) -> str:
    if score >= 85:
        return "execute_call"
    elif score >= 70:
        return "call_eligible"
    elif score >= 50:
        return "monitor"
    elif score >= 30:
        return "hold"
    else:
        return "put_alert"

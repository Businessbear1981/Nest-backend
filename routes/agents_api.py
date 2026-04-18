"""Agent management routes — run agents, check status."""
import threading
from flask import Blueprint, jsonify, request, current_app
from datetime import datetime

agents_bp = Blueprint("agents_api", __name__)

_lock = threading.RLock()
_agent_status = {}


def _ts():
    return datetime.utcnow().isoformat()


def _ok(data, code=200):
    return jsonify({"success": True, "data": data, "error": None, "timestamp": _ts()}), code


def _err(msg, code=400):
    return jsonify({"success": False, "data": None, "error": msg, "timestamp": _ts()}), code


AGENT_REGISTRY = {
    "vector": {"name": "Vector", "status": "standby", "description": "Call/put timing agent"},
    "apex": {"name": "Apex", "status": "standby", "description": "Short position manager"},
    "chain": {"name": "Chain", "status": "standby", "description": "Blockchain execution"},
    "atlas": {"name": "Atlas", "status": "standby", "description": "Financial modeling"},
    "morgan": {"name": "Morgan", "status": "active", "description": "Memo + content writer"},
    "sterling": {"name": "Sterling", "status": "active", "description": "Investor placement"},
    "bridge": {"name": "Bridge", "status": "standby", "description": "Perm debt monitoring"},
    "quantum": {"name": "Quantum", "status": "standby", "description": "HFT fund optimizer"},
    "maxwell": {"name": "Maxwell", "status": "standby", "description": "Credit analyst"},
    "aria": {"name": "Aria", "status": "active", "description": "Client + BD outreach"},
    "merlin": {"name": "Merlin", "status": "standby", "description": "M&A intelligence"},
    "lender_scout": {"name": "LenderScout", "status": "standby", "description": "Direct lender sourcing"},
    "prometheus": {"name": "Prometheus", "status": "standby", "description": "Financial modeling engine"},
    "sentinel": {"name": "Sentinel", "status": "standby", "description": "Risk assessment engine"},
    "blaze": {"name": "Blaze", "status": "standby", "description": "Elite marketing engine"},
}


@agents_bp.route("/status", methods=["GET"])
def all_status():
    with _lock:
        agents = []
        for key, info in AGENT_REGISTRY.items():
            status = _agent_status.get(key, {})
            agents.append({
                "id": key,
                "name": info["name"],
                "status": status.get("status", info["status"]),
                "description": info["description"],
                "last_run": status.get("last_run"),
                "deals_monitored": status.get("deals_monitored", []),
            })
    return _ok(agents)


@agents_bp.route("/<name>/run", methods=["POST"])
def run_agent(name):
    name_lower = name.lower()
    if name_lower not in AGENT_REGISTRY:
        return _err(f"Unknown agent: {name}", 404)

    body = request.get_json() or {}
    deal_id = body.get("deal_id")

    # Try to get the agent instance from app config
    agent_map = {
        "morgan": "MORGAN",
        "aria": "ARIA",
        "sterling": "STERLING",
    }

    config_key = agent_map.get(name_lower)
    if config_key and config_key in current_app.config:
        agent = current_app.config[config_key]
        with _lock:
            _agent_status[name_lower] = {
                "status": "active",
                "last_run": _ts(),
                "deals_monitored": [deal_id] if deal_id else [],
            }
        return _ok({
            "agent": name_lower,
            "status": "active",
            "message": f"{AGENT_REGISTRY[name_lower]['name']} is running",
            "last_run": _ts(),
        })

    # Agent not yet built — return standby status
    with _lock:
        _agent_status[name_lower] = {
            "status": "standby",
            "last_run": _ts(),
            "deals_monitored": [],
        }
    return _ok({
        "agent": name_lower,
        "status": "standby",
        "message": f"{AGENT_REGISTRY[name_lower]['name']} not yet implemented — standing by",
        "last_run": _ts(),
    })

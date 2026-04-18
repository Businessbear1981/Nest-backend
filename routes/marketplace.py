"""Public marketplace routes — deal listings for investors."""
from flask import Blueprint, jsonify, request
from datetime import datetime

marketplace_bp = Blueprint("marketplace", __name__)


def _ts():
    return datetime.utcnow().isoformat()


def _ok(data, code=200):
    return jsonify({"success": True, "data": data, "error": None, "timestamp": _ts()}), code


@marketplace_bp.route("", methods=["GET"])
def list_offerings():
    """Public deal listings — no auth required for viewing."""
    # Import deals store from deals blueprint
    from routes.deals import _deals, _bonds, _lock

    with _lock:
        listings = []
        for d in _deals.values():
            if d["status"] in ("structured", "placed", "active"):
                bond = _bonds.get(d["id"])
                project = d.get("project", {})
                listings.append({
                    "id": d["id"],
                    "name": d["name"],
                    "status": d["status"],
                    "asset_type": project.get("asset_type", "other"),
                    "city": project.get("city", ""),
                    "state": project.get("state", ""),
                    "total_project_cost_usd": project.get("total_project_cost_usd", 0),
                    "bond_face_usd": sum(
                        s["face_amount_usd"] for s in (bond or {}).get("series", [])
                    ) if bond else 0,
                    "readiness_score": d.get("readiness_score", 0),
                    "description": project.get("description", ""),
                })

    return _ok({
        "offerings": listings,
        "total_pipeline_usd": sum(l["total_project_cost_usd"] for l in listings),
        "count": len(listings),
    })

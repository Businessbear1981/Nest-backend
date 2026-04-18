"""Investor management routes."""
import threading
import uuid
from flask import Blueprint, jsonify, request
from datetime import datetime

investors_bp = Blueprint("investors", __name__)

_lock = threading.RLock()
_investors = {}


def _ts():
    return datetime.utcnow().isoformat()


def _ok(data, code=200):
    return jsonify({"success": True, "data": data, "error": None, "timestamp": _ts()}), code


def _err(msg, code=400):
    return jsonify({"success": False, "data": None, "error": msg, "timestamp": _ts()}), code


# Seed investors
def _seed():
    seeds = [
        {
            "name": "Redwood Family Office",
            "entity_type": "family_office",
            "accredited_verified": True,
            "qib_qualified": False,
            "kyc_aml_cleared": True,
            "total_committed_usd": 5_000_000,
        },
        {
            "name": "Cascadia Endowment",
            "entity_type": "institutional",
            "accredited_verified": True,
            "qib_qualified": True,
            "kyc_aml_cleared": True,
            "total_committed_usd": 15_000_000,
        },
        {
            "name": "Mariner Credit Partners",
            "entity_type": "institutional",
            "accredited_verified": True,
            "qib_qualified": True,
            "kyc_aml_cleared": True,
            "total_committed_usd": 8_000_000,
        },
    ]
    with _lock:
        for s in seeds:
            inv_id = str(uuid.uuid4())
            _investors[inv_id] = {
                "id": inv_id,
                "positions": [],
                "fund_positions": [],
                "created_at": _ts(),
                **s,
            }


_seed()


@investors_bp.route("", methods=["GET"])
def list_investors():
    with _lock:
        return _ok(list(_investors.values()))


@investors_bp.route("", methods=["POST"])
def add_investor():
    body = request.get_json() or {}
    if not body.get("name"):
        return _err("name is required")
    inv_id = str(uuid.uuid4())
    investor = {
        "id": inv_id,
        "name": body["name"],
        "entity_type": body.get("entity_type", "hnwi"),
        "accredited_verified": body.get("accredited_verified", False),
        "qib_qualified": body.get("qib_qualified", False),
        "kyc_aml_cleared": body.get("kyc_aml_cleared", False),
        "total_committed_usd": body.get("total_committed_usd", 0),
        "positions": [],
        "fund_positions": [],
        "created_at": _ts(),
    }
    with _lock:
        _investors[inv_id] = investor
    return _ok(investor, 201)

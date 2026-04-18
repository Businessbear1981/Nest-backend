from flask import Blueprint, current_app, jsonify, request

from services.auth import current_user, require_auth

activity_bp = Blueprint("activity", __name__)


def _feed():
    return current_app.config["ACTIVITY"]


@activity_bp.get("")
@require_auth()
def list_activity():
    limit = int(request.args.get("limit", 25))
    user = current_user()
    if user is None:
        return jsonify([])
    return jsonify(_feed().for_user(user.id, role=user.role, client_id=user.client_id, limit=limit))

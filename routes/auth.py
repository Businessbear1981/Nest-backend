from flask import Blueprint, current_app, jsonify, request

from services.auth import AuthError, require_auth, current_user

auth_bp = Blueprint("auth", __name__)


def _service():
    return current_app.config["AUTH"]


@auth_bp.post("/login")
def login():
    body = request.get_json(silent=True) or {}
    email = body.get("email", "")
    password = body.get("password", "")
    try:
        user = _service().authenticate(email, password)
    except AuthError as e:
        return jsonify({"error": str(e)}), e.status
    return jsonify(_service().issue_token(user))


@auth_bp.post("/register")
def register():
    body = request.get_json(silent=True) or {}
    try:
        user = _service().register(
            email=body.get("email", ""),
            password=body.get("password", ""),
            name=body.get("name", ""),
            role="client",
            client_id=body.get("client_id"),
        )
    except AuthError as e:
        return jsonify({"error": str(e)}), e.status
    return jsonify(_service().issue_token(user)), 201


@auth_bp.get("/me")
@require_auth()
def me():
    user = current_user()
    return jsonify(user.public() if user else {})


@auth_bp.post("/password")
@require_auth()
def change_password():
    body = request.get_json(silent=True) or {}
    user = current_user()
    if user is None:
        return jsonify({"error": "no user"}), 401
    try:
        _service().change_password(user, body.get("current_password", ""), body.get("new_password", ""))
    except AuthError as e:
        return jsonify({"error": str(e)}), e.status
    return jsonify({"ok": True})

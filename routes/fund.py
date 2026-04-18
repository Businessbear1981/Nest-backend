from flask import Blueprint, current_app, jsonify, request
from flask_socketio import disconnect, join_room, leave_room

from services.auth import AuthError, current_user, require_auth

fund_bp = Blueprint("fund", __name__)


def _engine():
    return current_app.config["FUND_ENGINE"]


def _resolve_client_id(explicit: str | None) -> str:
    """
    Clients see their own bound id. Admins see anything they ask for.
    Investors fall back to 'demo' for now (no per-investor portfolio yet).
    """
    user = current_user()
    if user is None:
        return explicit or "demo"
    if user.role == "admin":
        return explicit or user.client_id or "demo"
    if user.role == "client":
        return user.client_id or "demo"
    return explicit or "demo"


@fund_bp.get("/position")
@require_auth()
def position():
    client_id = _resolve_client_id(request.args.get("client_id"))
    try:
        return jsonify(_engine().get_position(client_id))
    except KeyError:
        return jsonify({"error": "client_not_found"}), 404


@fund_bp.get("/yield")
@require_auth()
def yield_breakdown():
    client_id = _resolve_client_id(request.args.get("client_id"))
    try:
        pos = _engine().get_position(client_id)
        return jsonify(_engine().calculate_yield(pos))
    except KeyError:
        return jsonify({"error": "client_not_found"}), 404


@fund_bp.get("/distributions")
@require_auth()
def distributions():
    client_id = _resolve_client_id(request.args.get("client_id"))
    try:
        return jsonify(_engine().get_distributions(client_id))
    except KeyError:
        return jsonify({"error": "client_not_found"}), 404


@fund_bp.get("/wc/eligibility")
@require_auth()
def wc_eligibility():
    client_id = _resolve_client_id(request.args.get("client_id"))
    try:
        return jsonify(_engine().working_capital_eligibility(client_id))
    except KeyError:
        return jsonify({"error": "client_not_found"}), 404


@fund_bp.post("/wc/request")
@require_auth("client", "admin")
def wc_request():
    body = request.get_json(silent=True) or {}
    client_id = _resolve_client_id(body.get("client_id"))
    amount = float(body.get("amount", 0))
    try:
        return jsonify(_engine().request_working_capital(client_id, amount))
    except KeyError:
        return jsonify({"error": "client_not_found"}), 404


@fund_bp.get("/benchmark")
@require_auth()
def benchmark():
    return jsonify(_engine().benchmark())


@fund_bp.get("/snapshot")
def snapshot():
    from services.core import hft, ok
    sim = hft.simulate(32_400_000, 12)
    return ok(sim)


@fund_bp.get("/hft/war-chest")
def war_chest():
    from services.core import hft, ok
    sim = hft.simulate(32_400_000, 12)
    return ok({
        "aum_usd": sim["aum_current"],
        "ytd_return_pct": sim["ytd_return_pct"],
        "war_chest_usd": sim["war_chest_surplus_usd"],
        "lc_capacity_usd": sim["lc_capacity_usd"],
        "lc_phase": sim["lc_phase"],
        "ma_deployment_usd": sim["ma_deployment_available"],
        "strategies": sim["strategies"],
    })


def register_fund_socket_events(socketio, engine, auth):
    """
    WebSocket auth: socket.io-client passes `auth: { token }` on connect;
    we verify and stash on the connection's session via flask.g would not
    persist across events, so we keep it simple — verify on each event that
    needs gating.
    """
    def _verify(data):
        token = (data or {}).get("token") or ""
        try:
            return auth.verify_token(token)
        except AuthError:
            return None

    @socketio.on("connect")
    def on_connect(auth_payload=None):
        # Flask-SocketIO passes the handshake auth dict here.
        token = (auth_payload or {}).get("token") if isinstance(auth_payload, dict) else None
        if not token:
            return  # allow anonymous connect; gated events still verify
        try:
            auth.verify_token(token)
        except AuthError:
            disconnect()
            return False

    @socketio.on("subscribe_client")
    def on_subscribe(data):
        user = _verify(data)
        if user is None:
            return  # silently ignore unauthenticated subscribe
        requested = (data or {}).get("client_id")
        if user.role == "admin":
            client_id = requested or user.client_id or "demo"
        elif user.role == "client":
            client_id = user.client_id or "demo"
        else:
            client_id = requested or "demo"
        join_room(f"client:{client_id}")
        try:
            socketio.emit("fund_update", engine.get_position(client_id), to=f"client:{client_id}")
        except KeyError:
            socketio.emit("fund_error", {"error": "client_not_found"}, to=f"client:{client_id}")

    @socketio.on("unsubscribe_client")
    def on_unsubscribe(data):
        client_id = (data or {}).get("client_id", "demo")
        leave_room(f"client:{client_id}")

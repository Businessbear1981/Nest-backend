"""Webhooks — inbound webhook receiver + outbound event triggers."""
from flask import Blueprint, request
from services.core import ok, err, ts
from blockchain.nest_chain import chain

webhooks_bp = Blueprint("webhooks", __name__)

_webhook_log = []


@webhooks_bp.post("/inbound")
def inbound():
    data = request.get_json(force=True)
    source = data.get("source", "unknown")
    event_type = data.get("event_type", "generic")
    payload = data.get("payload", {})
    entry = {
        "source": source, "event_type": event_type,
        "payload": payload, "received_at": ts(),
    }
    _webhook_log.append(entry)
    chain.record_event(f"webhook_{source}", event_type, payload)
    return ok(entry)


@webhooks_bp.get("/log")
def webhook_log():
    limit = request.args.get("limit", 50, type=int)
    return ok(_webhook_log[-limit:])

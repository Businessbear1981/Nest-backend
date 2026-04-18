"""Blockchain routes — chain stats, event log, record endpoints."""
from flask import Blueprint, request
from services.core import ok, err
from blockchain.nest_chain import chain

blockchain_bp = Blueprint("blockchain", __name__)


@blockchain_bp.get("/stats")
def stats():
    return ok(chain.get_stats())


@blockchain_bp.get("/events")
def events():
    limit = request.args.get("limit", 50, type=int)
    return ok(chain.get_recent(limit))


@blockchain_bp.get("/events/<deal_id>")
def deal_events(deal_id):
    return ok(chain.get_deal_history(deal_id))


@blockchain_bp.get("/verify/<tx_hash>")
def verify(tx_hash):
    tx = chain.verify_transaction(tx_hash)
    if not tx:
        return err("Transaction not found", 404)
    return ok(tx)


@blockchain_bp.post("/record")
def record_event():
    data = request.get_json(force=True)
    deal_id = data.get("deal_id")
    event_type = data.get("event_type")
    event_data = data.get("data", {})
    if not deal_id or not event_type:
        return err("deal_id and event_type required")
    tx = chain.record_event(deal_id, event_type, event_data)
    return ok(tx)

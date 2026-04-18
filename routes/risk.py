"""Risk assessment routes — sentinel.score_deal + risk reports + covenant tests."""
from flask import Blueprint, request
from services.core import risk, credit, ok, err

risk_bp = Blueprint("risk", __name__)


@risk_bp.get("/score/<deal_id>")
def score_deal(deal_id):
    from routes.deals import _deals, _lock
    with _lock:
        deal = _deals.get(deal_id)
    if not deal:
        return err("Deal not found", 404)
    project = deal.get("project", {})
    metrics = credit.compute(project)
    result = risk.score_deal(project, metrics)
    result["deal_id"] = deal_id
    return ok(result)


@risk_bp.get("/portfolio")
def portfolio_risk():
    from routes.deals import _deals, _lock
    with _lock:
        deals = dict(_deals)
    results = []
    for did, deal in deals.items():
        project = deal.get("project", {})
        metrics = credit.compute(project)
        r = risk.score_deal(project, metrics)
        r["deal_id"] = did
        r["deal_name"] = deal.get("name", did)
        results.append(r)
    results.sort(key=lambda x: x["composite_score"])
    alerts = [r for r in results if r["risk_level"] in ("red", "critical")]
    return ok({"deals": results, "alerts": alerts, "total": len(results)})


@risk_bp.post("/covenant-test")
def covenant_test():
    data = request.get_json(force=True)
    deal_id = data.get("deal_id")
    metric = data.get("metric")
    value = data.get("value")
    threshold = data.get("threshold")
    if not all([deal_id, metric, value is not None, threshold is not None]):
        return err("deal_id, metric, value, threshold required")
    passed = value >= threshold if metric in ("dscr", "icr") else value <= threshold
    from blockchain.nest_chain import chain
    tx = chain.record_covenant_test(deal_id, metric, value, threshold, passed)
    return ok({"deal_id": deal_id, "metric": metric, "value": value,
               "threshold": threshold, "passed": passed, "tx": tx})

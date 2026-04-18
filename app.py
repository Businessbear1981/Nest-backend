import sys
import os
import threading
import time
from flask import Flask, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO

# Ensure backend dir is on path for model imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config
from routes.fund import fund_bp, register_fund_socket_events
from routes.marketing import marketing_bp
from routes.deals import deals_bp
from routes.auth import auth_bp
from routes.documents import documents_bp
from routes.activity import activity_bp
from routes.agents_api import agents_bp
from routes.market import market_bp
from routes.marketplace import marketplace_bp
from routes.investors import investors_bp
from routes.perm import perm_bp
from routes.ma import ma_bp
from routes.lenders_api import lenders_api_bp
from routes.surety import surety_bp
from routes.due_diligence import dd_bp
from routes.bond_tools import bond_tools_bp
from routes.risk import risk_bp
from routes.blockchain import blockchain_bp
from routes.webhooks import webhooks_bp
from services.fund_engine import FundEngine
from services.deals import DealsRegistry
from services.auth import AuthService
from services.documents import DocumentRegistry
from services.activity import ActivityFeed
from agents.morgan import MorganAgent
from agents.aria import AriaAgent
from agents.sterling import SterlingAgent


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    CORS(app, resources={r"/api/*": {"origins": Config.FRONTEND_ORIGIN}})

    engine = FundEngine()
    app.config["FUND_ENGINE"] = engine
    app.config["DEALS"] = DealsRegistry()
    app.config["MORGAN"] = MorganAgent()
    app.config["ARIA"] = AriaAgent()
    app.config["STERLING"] = SterlingAgent()
    auth = AuthService()
    app.config["AUTH"] = auth
    app.config["DOCS"] = DocumentRegistry()
    app.config["ACTIVITY"] = ActivityFeed()

    # Core blueprints
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(fund_bp, url_prefix="/api/fund")
    app.register_blueprint(marketing_bp, url_prefix="/api/marketing")
    app.register_blueprint(deals_bp, url_prefix="/api/deals")
    app.register_blueprint(documents_bp, url_prefix="/api/docs")
    app.register_blueprint(activity_bp, url_prefix="/api/activity")

    # New Series 1-2 blueprints
    app.register_blueprint(agents_bp, url_prefix="/api/agents")
    app.register_blueprint(market_bp, url_prefix="/api/market")
    app.register_blueprint(marketplace_bp, url_prefix="/api/marketplace")
    app.register_blueprint(investors_bp, url_prefix="/api/investors")
    app.register_blueprint(perm_bp, url_prefix="/api/perm")
    app.register_blueprint(ma_bp, url_prefix="/api/ma")
    app.register_blueprint(lenders_api_bp, url_prefix="/api/lenders-direct")
    app.register_blueprint(surety_bp, url_prefix="/api/surety")
    app.register_blueprint(dd_bp, url_prefix="/api/dd")
    app.register_blueprint(bond_tools_bp, url_prefix="/api/bond-tools")
    app.register_blueprint(risk_bp, url_prefix="/api/risk")
    app.register_blueprint(blockchain_bp, url_prefix="/api/blockchain")
    app.register_blueprint(webhooks_bp, url_prefix="/api/webhooks")

    @app.get("/api/health")
    def health():
        return jsonify({"ok": True, "service": "nest-backend", "port": Config.PORT})

    @app.get("/api/metrics")
    def metrics():
        from routes.deals import _deals, _bonds, _lock
        with _lock:
            deal_count = len(_deals)
            active = sum(1 for d in _deals.values() if d["status"] != "closed")
            total_pipeline = sum(
                d.get("project", {}).get("total_project_cost_usd", 0)
                for d in _deals.values() if d["status"] != "closed"
            )
            bond_count = len(_bonds)
        return jsonify({
            "success": True,
            "data": {
                "total_deals": deal_count,
                "active_deals": active,
                "total_pipeline_usd": total_pipeline,
                "bond_structures": bond_count,
                "agents_active": 3,
                "agents_total": 15,
            },
            "timestamp": __import__("datetime").datetime.utcnow().isoformat(),
        })

    is_serverless = os.environ.get("VERCEL") == "1"

    if not is_serverless:
        socketio = SocketIO(
            app,
            cors_allowed_origins=Config.FRONTEND_ORIGIN,
            async_mode="threading",
        )
        register_fund_socket_events(socketio, engine, auth)
        app.config["SOCKETIO"] = socketio

        def ticker():
            while True:
                time.sleep(Config.FUND_TICK_SECONDS)
                snapshot = engine.tick_all()
                for client_id, payload in snapshot.items():
                    socketio.emit("fund_update", payload, to=f"client:{client_id}")
                socketio.emit("market_update", engine.market_snapshot())

        threading.Thread(target=ticker, daemon=True).start()
        return app, socketio
    else:
        return app, None


app, socketio = create_app()


if __name__ == "__main__":
    if socketio:
        socketio.run(app, host=Config.HOST, port=Config.PORT, debug=Config.DEBUG)
    else:
        app.run(host=Config.HOST, port=Config.PORT, debug=Config.DEBUG)

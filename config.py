import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    PORT = int(os.getenv("PORT", 8000))
    HOST = os.getenv("HOST", "0.0.0.0")
    SECRET_KEY = os.getenv("SECRET_KEY", "nest-dev-secret-change-me")
    FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "*")
    FUND_TICK_SECONDS = int(os.getenv("FUND_TICK_SECONDS", 60))
    B_TRANCHE_COUPON_PCT = float(os.getenv("B_TRANCHE_COUPON_PCT", 0.085))
    MGMT_FEE_PCT = float(os.getenv("MGMT_FEE_PCT", 0.02))
    WC_SPREAD_BPS = int(os.getenv("WC_SPREAD_BPS", 275))
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
    ANTHROPIC_MAX_TOKENS = int(os.getenv("ANTHROPIC_MAX_TOKENS", 4096))
    DEBUG = os.getenv("DEBUG", "false").lower() in ("1", "true", "yes")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "nest-dev-jwt-change-me")
    JWT_TTL_HOURS = int(os.getenv("JWT_TTL_HOURS", 24))

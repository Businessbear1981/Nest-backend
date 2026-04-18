"""
Auth service — JWT issuance + verification, in-memory user store, password
hashing (werkzeug), role gating via `require_auth` decorator.

Three roles:
  - admin    — NEST team. Full access to /api/marketing and /api/fund.
  - client   — bond/position holders. Access to their own /api/fund position.
  - investor — LPs. Access to gated marketplace endpoints (TBD when /api/marketplace lands).

In-memory store mirrors FundEngine/DealsRegistry. Swap for Supabase or Postgres later.
"""
from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Optional

import jwt
from flask import current_app, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

from config import Config


VALID_ROLES = {"admin", "client", "investor"}


@dataclass
class User:
    id: str
    email: str
    password_hash: str
    role: str
    name: str
    client_id: Optional[str] = None  # only meaningful for role=client
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def public(self) -> dict:
        return {
            "id": self.id,
            "email": self.email,
            "role": self.role,
            "name": self.name,
            "client_id": self.client_id,
            "created_at": self.created_at,
        }


class AuthError(Exception):
    def __init__(self, message: str, status: int = 401):
        super().__init__(message)
        self.status = status


class AuthService:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._users_by_id: dict[str, User] = {}
        self._users_by_email: dict[str, User] = {}
        self._seed()

    def _seed(self) -> None:
        seeds = [
            ("admin@nest.local",    "Admin123!",    "admin",    "NEST Admin",      None),
            ("client@nest.local",   "Client123!",   "client",   "Demo Client",     "demo"),
            ("investor@nest.local", "Investor123!", "investor", "Redwood Family",  None),
        ]
        for email, pw, role, name, client_id in seeds:
            self._create(email=email, password=pw, role=role, name=name, client_id=client_id)

    # ---------- core ----------

    def _create(self, *, email: str, password: str, role: str, name: str, client_id: Optional[str]) -> User:
        email = email.strip().lower()
        if role not in VALID_ROLES:
            raise AuthError(f"invalid role: {role}", status=400)
        if not email or "@" not in email:
            raise AuthError("invalid email", status=400)
        if len(password) < 8:
            raise AuthError("password must be at least 8 characters", status=400)
        with self._lock:
            if email in self._users_by_email:
                raise AuthError("email already registered", status=409)
            user = User(
                id=f"usr_{uuid.uuid4().hex[:10]}",
                email=email,
                password_hash=generate_password_hash(password),
                role=role,
                name=name.strip() or email.split("@")[0],
                client_id=client_id,
            )
            self._users_by_id[user.id] = user
            self._users_by_email[user.email] = user
            return user

    def register(self, *, email: str, password: str, name: str, role: str = "client", client_id: Optional[str] = None) -> User:
        # Public registration only ever produces clients. Admin/investor seats are created out-of-band.
        if role != "client":
            raise AuthError("only client accounts can self-register", status=403)
        return self._create(email=email, password=password, role=role, name=name, client_id=client_id)

    def authenticate(self, email: str, password: str) -> User:
        email = (email or "").strip().lower()
        with self._lock:
            user = self._users_by_email.get(email)
        if user is None or not check_password_hash(user.password_hash, password or ""):
            raise AuthError("invalid email or password", status=401)
        return user

    def change_password(self, user: User, current: str, new: str) -> None:
        if not check_password_hash(user.password_hash, current or ""):
            raise AuthError("current password is incorrect", status=401)
        if len(new) < 8:
            raise AuthError("new password must be at least 8 characters", status=400)
        with self._lock:
            user.password_hash = generate_password_hash(new)

    def get_user(self, user_id: str) -> Optional[User]:
        with self._lock:
            return self._users_by_id.get(user_id)

    # ---------- JWT ----------

    def issue_token(self, user: User) -> dict:
        now = datetime.now(timezone.utc)
        exp = now + timedelta(hours=Config.JWT_TTL_HOURS)
        payload = {
            "sub": user.id,
            "email": user.email,
            "role": user.role,
            "client_id": user.client_id,
            "iat": int(now.timestamp()),
            "exp": int(exp.timestamp()),
        }
        token = jwt.encode(payload, Config.JWT_SECRET_KEY, algorithm="HS256")
        return {"token": token, "expires_at": exp.isoformat(), "user": user.public()}

    def verify_token(self, token: str) -> User:
        if not token:
            raise AuthError("missing token", status=401)
        try:
            payload = jwt.decode(token, Config.JWT_SECRET_KEY, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            raise AuthError("token expired", status=401)
        except jwt.InvalidTokenError:
            raise AuthError("invalid token", status=401)
        user = self.get_user(payload.get("sub", ""))
        if user is None:
            raise AuthError("user no longer exists", status=401)
        return user


# ---------- Flask plumbing ----------

def _service() -> AuthService:
    return current_app.config["AUTH"]


def _bearer_token() -> Optional[str]:
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return request.args.get("token")


def require_auth(*roles: str):
    """
    Decorator: enforce a valid token and (optionally) one of the given roles.

    Usage:
        @bp.get("/thing")
        @require_auth()              # any authenticated user
        def thing(): ...

        @bp.post("/admin-thing")
        @require_auth("admin")       # admin only
        def admin_thing(): ...
    """
    allowed = set(roles)

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                user = _service().verify_token(_bearer_token() or "")
            except AuthError as e:
                return jsonify({"error": str(e)}), e.status
            if allowed and user.role not in allowed:
                return jsonify({"error": "forbidden", "required_roles": sorted(allowed)}), 403
            g.current_user = user
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def current_user() -> Optional[User]:
    return getattr(g, "current_user", None)

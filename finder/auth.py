"""Authentication and request protection for the multi-user product."""

from __future__ import annotations

import datetime as dt
import re
import secrets
import uuid
from functools import wraps

from flask import abort, g, jsonify, redirect, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from . import store

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def register_user(name: str, email: str, password: str) -> tuple[dict | None, str | None]:
    name = " ".join((name or "").split())[:100]
    email = (email or "").strip().lower()[:254]
    if len(name) < 2:
        return None, "Enter your full name."
    if not EMAIL_RE.match(email):
        return None, "Enter a valid email address."
    if len(password or "") < 10:
        return None, "Use at least 10 characters for your password."
    user = {
        "id": uuid.uuid4().hex,
        "name": name,
        "email": email,
        "password_hash": generate_password_hash(password),
        "created_at": now(),
    }
    conn = store.connect()
    try:
        exists = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if exists:
            return None, "An account already exists for that email address."
        conn.execute(
            "INSERT INTO users (id,email,password_hash,name,created_at) VALUES (?,?,?,?,?)",
            (user["id"], email, user["password_hash"], name, user["created_at"]),
        )
        conn.commit()
    finally:
        conn.close()
    return {k: user[k] for k in ("id", "name", "email", "created_at")}, None


def authenticate(email: str, password: str) -> dict | None:
    conn = store.connect()
    try:
        row = conn.execute(
            "SELECT * FROM users WHERE email = ? AND is_active = 1",
            ((email or "").strip().lower(),),
        ).fetchone()
        if not row or not check_password_hash(row["password_hash"], password or ""):
            return None
        conn.execute("UPDATE users SET last_login = ? WHERE id = ?", (now(), row["id"]))
        conn.commit()
        return {k: row[k] for k in ("id", "name", "email", "created_at")}
    finally:
        conn.close()


def begin_session(user: dict) -> None:
    session.clear()
    session["user_id"] = user["id"]
    session["csrf"] = secrets.token_urlsafe(32)


def csrf_token() -> str:
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return session["csrf"]


def verify_csrf() -> None:
    supplied = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token") or ""
    expected = session.get("csrf") or ""
    if not expected or not secrets.compare_digest(supplied, expected):
        abort(400, "Invalid request token. Reload the page and try again.")


def load_user() -> None:
    g.user = None
    user_id = session.get("user_id")
    if not user_id:
        return
    conn = store.connect()
    try:
        row = conn.execute(
            "SELECT id,name,email,created_at FROM users WHERE id = ? AND is_active = 1",
            (user_id,),
        ).fetchone()
        g.user = dict(row) if row else None
    finally:
        conn.close()
    if g.user is None:
        session.clear()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not g.get("user"):
            if request.path.startswith("/api/"):
                return jsonify({"error": "authentication required"}), 401
            return redirect(url_for("login", next=request.full_path))
        return view(*args, **kwargs)
    return wrapped


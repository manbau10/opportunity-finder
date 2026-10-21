# -*- coding: utf-8 -*-
"""Account rights: export everything held about a person, and delete it all."""

from __future__ import annotations

import json
import threading
import time
from collections import defaultdict, deque

from werkzeug.security import check_password_hash

from . import store

_OWNED_TABLES = ("application_pack_files", "application_packs", "provider_configs",
                 "user_matches", "user_profiles")


def export_data(user_id: str) -> dict:
    """Everything stored about one person, as plain data (no files, no stored API keys)."""
    conn = store.connect()
    try:
        user = conn.execute("SELECT id,email,name,created_at,last_login FROM users WHERE id=?",
                            (user_id,)).fetchone()
        profiles = conn.execute(
            "SELECT kind,cv_filename,cv_text,profile_json,created_at,updated_at "
            "FROM user_profiles WHERE user_id=?", (user_id,)).fetchall()
        saved = conn.execute(
            "SELECT m.profile_kind,m.status,m.score,o.title,o.org,o.url FROM user_matches m "
            "JOIN opportunities o ON o.id=m.opportunity_id WHERE m.user_id=? "
            "AND m.status IN ('saved','applied','dismissed')", (user_id,)).fetchall()
        packs = conn.execute(
            "SELECT id,opportunity_id,profile_kind,status,created_at FROM application_packs "
            "WHERE user_id=?", (user_id,)).fetchall()
        own_jobs = conn.execute(
            "SELECT title,org,url,career_track FROM opportunities WHERE owner_user_id=?",
            (user_id,)).fetchall()
    finally:
        conn.close()
    return {
        "account": dict(user) if user else {},
        "cv_profiles": [dict(row) for row in profiles],
        "job_list": [dict(row) for row in saved],
        "application_workspaces": [dict(row) for row in packs],
        "jobs_you_added": [dict(row) for row in own_jobs],
        "note": "Stored AI and search keys are encrypted and are not exported. "
                "Generated documents can be downloaded from each workspace.",
    }


def delete_account(user_id: str, password: str) -> bool:
    """Permanently remove a person and everything they own. Needs their password."""
    conn = store.connect()
    try:
        row = conn.execute("SELECT password_hash FROM users WHERE id=?", (user_id,)).fetchone()
        if not row or not check_password_hash(row["password_hash"], password or ""):
            return False
        for table in _OWNED_TABLES:
            conn.execute(f"DELETE FROM {table} WHERE user_id=?", (user_id,))
        conn.execute("DELETE FROM opportunities WHERE owner_user_id=?", (user_id,))
        conn.execute("DELETE FROM users WHERE id=?", (user_id,))
        conn.commit()
        return True
    finally:
        conn.close()


class RateLimiter:
    """Allow `limit` hits per `window` seconds per key (per server process)."""

    def __init__(self, limit: int, window: int):
        self.limit, self.window = limit, window
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.time()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] > self.window:
                hits.popleft()
            if len(hits) >= self.limit:
                return False
            hits.append(now)
            return True

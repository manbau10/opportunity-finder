# -*- coding: utf-8 -*-
"""
Database layer.

Locally the app runs on a SQLite file. On a host such as Render the filesystem
is wiped on every restart, so it runs on Postgres instead, chosen purely by
whether DATABASE_URL is set. The rest of the code writes ordinary SQL with `?`
placeholders and never needs to know which one it is talking to.
"""

from __future__ import annotations

import os
import re
import sqlite3

from .config import DATA_DIR, DB_PATH

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
IS_POSTGRES = DATABASE_URL.startswith(("postgres://", "postgresql://"))

if IS_POSTGRES:
    # psycopg3 rejects the older "postgres://" spelling that some hosts hand out.
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = "postgresql://" + DATABASE_URL[len("postgres://"):]


def backend() -> str:
    return "postgres" if IS_POSTGRES else "sqlite"


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------
_OPPORTUNITIES = """
CREATE TABLE IF NOT EXISTS opportunities (
    id            TEXT PRIMARY KEY,
    source        TEXT,
    source_key    TEXT,
    title         TEXT,
    org           TEXT,
    department    TEXT,
    location      TEXT,
    country       TEXT,
    country_tier  TEXT,
    url           TEXT,
    description   TEXT,
    posted        TEXT,
    deadline      TEXT,
    days_left     INTEGER,
    role_key      TEXT,
    role_label    TEXT,
    score         INTEGER,
    matched_terms TEXT,
    flags         TEXT,
    positives     TEXT,
    breakdown     TEXT,
    query         TEXT,
    enriched      INTEGER DEFAULT 0,
    first_seen    TEXT,
    last_seen     TEXT,
    status        TEXT DEFAULT 'new'
    ,career_track TEXT DEFAULT 'academic'
);
CREATE INDEX IF NOT EXISTS idx_score  ON opportunities(score DESC);
CREATE INDEX IF NOT EXISTS idx_seen   ON opportunities(first_seen DESC);
CREATE INDEX IF NOT EXISTS idx_status ON opportunities(status);
"""

_PRODUCT_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            TEXT PRIMARY KEY,
    email         TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    name          TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    last_login    TEXT,
    is_active     INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS user_profiles (
    id            TEXT PRIMARY KEY,
    user_id       TEXT NOT NULL,
    kind          TEXT NOT NULL,
    cv_filename   TEXT,
    cv_mime       TEXT,
    cv_sha256     TEXT,
    cv_blob       TEXT,
    cv_text       TEXT,
    profile_json  TEXT,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL,
    UNIQUE(user_id, kind)
);
CREATE INDEX IF NOT EXISTS idx_profiles_user ON user_profiles(user_id);

CREATE TABLE IF NOT EXISTS user_matches (
    user_id       TEXT NOT NULL,
    opportunity_id TEXT NOT NULL,
    profile_kind  TEXT NOT NULL,
    score         INTEGER NOT NULL,
    matched_terms TEXT,
    breakdown     TEXT,
    status        TEXT DEFAULT 'new',
    updated_at    TEXT NOT NULL,
    PRIMARY KEY(user_id, opportunity_id, profile_kind)
);
CREATE INDEX IF NOT EXISTS idx_matches_user_score
    ON user_matches(user_id, profile_kind, score DESC);

CREATE TABLE IF NOT EXISTS provider_configs (
    id                  TEXT PRIMARY KEY,
    user_id             TEXT NOT NULL UNIQUE,
    ai_provider         TEXT,
    ai_model            TEXT,
    ai_base_url         TEXT,
    ai_key_enc          TEXT,
    search_provider     TEXT,
    search_key_enc      TEXT,
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS application_packs (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL,
    opportunity_id  TEXT NOT NULL,
    profile_kind    TEXT NOT NULL,
    status          TEXT NOT NULL,
    documents_json  TEXT,
    sources_json    TEXT,
    zip_blob        TEXT,
    error           TEXT,
    progress        INTEGER DEFAULT 0,
    current_step    TEXT DEFAULT 'research',
    step_message    TEXT,
    plan_json       TEXT,
    cancel_requested INTEGER DEFAULT 0,
    created_at      TEXT NOT NULL,
    updated_at      TEXT,
    completed_at    TEXT
);
CREATE INDEX IF NOT EXISTS idx_packs_user ON application_packs(user_id, created_at);

CREATE TABLE IF NOT EXISTS application_pack_files (
    id          TEXT PRIMARY KEY,
    pack_id     TEXT NOT NULL,
    user_id     TEXT NOT NULL,
    step_key    TEXT NOT NULL,
    filename    TEXT NOT NULL,
    mime_type   TEXT NOT NULL,
    file_blob   TEXT NOT NULL,
    size_bytes  INTEGER NOT NULL,
    sort_order  INTEGER DEFAULT 0,
    created_at  TEXT NOT NULL,
    UNIQUE(pack_id, filename)
);
CREATE INDEX IF NOT EXISTS idx_pack_files_pack
    ON application_pack_files(pack_id, user_id, sort_order, created_at);
"""

_REFRESHES_SQLITE = """
CREATE TABLE IF NOT EXISTS refreshes (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    started    TEXT,
    finished   TEXT,
    found      INTEGER,
    added      INTEGER,
    updated    INTEGER,
    log        TEXT,
    ok         INTEGER DEFAULT 1
);
"""

_REFRESHES_POSTGRES = """
CREATE TABLE IF NOT EXISTS refreshes (
    id         SERIAL PRIMARY KEY,
    started    TEXT,
    finished   TEXT,
    found      INTEGER,
    added      INTEGER,
    updated    INTEGER,
    log        TEXT,
    ok         INTEGER DEFAULT 1
);
"""


def schema() -> str:
    return (_OPPORTUNITIES +
            (_REFRESHES_POSTGRES if IS_POSTGRES else _REFRESHES_SQLITE) +
            _PRODUCT_SCHEMA)


# ---------------------------------------------------------------------------
# Connection wrapper
# ---------------------------------------------------------------------------
_PLACEHOLDER = re.compile(r"\?")


def _translate(sql: str) -> str:
    """SQLite writes `?`; psycopg wants `%s`. No SQL here contains a literal `?`."""
    return _PLACEHOLDER.sub("%s", sql) if IS_POSTGRES else sql


class Connection:
    """A thin shim so both drivers answer to the same handful of calls."""

    def __init__(self, raw):
        self._raw = raw

    def execute(self, sql: str, params=()):
        cur = self._raw.cursor()
        cur.execute(_translate(sql), tuple(params))
        return cur

    def executescript(self, sql: str) -> None:
        if IS_POSTGRES:
            with self._raw.cursor() as cur:
                cur.execute(sql)
        else:
            self._raw.executescript(sql)
        self._raw.commit()

    def cursor(self):
        return _Cursor(self._raw.cursor())

    def columns(self, table: str) -> set[str]:
        if IS_POSTGRES:
            cur = self.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_name = ?",
                (table,))
            return {r["column_name"] for r in cur.fetchall()}
        cur = self._raw.execute("PRAGMA table_info(%s)" % table)
        return {r["name"] for r in cur.fetchall()}

    def commit(self):
        self._raw.commit()

    def close(self):
        try:
            self._raw.close()
        except Exception:
            pass


class _Cursor:
    """Wraps a raw cursor so callers can keep using `?` placeholders."""

    def __init__(self, raw):
        self._raw = raw

    def execute(self, sql: str, params=()):
        self._raw.execute(_translate(sql), tuple(params))
        return self

    def executemany(self, sql: str, params_seq):
        self._raw.executemany(_translate(sql), params_seq)
        return self

    def fetchone(self):
        return self._raw.fetchone()

    def fetchall(self):
        return self._raw.fetchall()

    def __iter__(self):
        return iter(self._raw)


def connect() -> Connection:
    if IS_POSTGRES:
        import psycopg
        from psycopg.rows import dict_row
        raw = psycopg.connect(DATABASE_URL, row_factory=dict_row, connect_timeout=20)
        return Connection(raw)

    os.makedirs(DATA_DIR, exist_ok=True)
    raw = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    raw.row_factory = sqlite3.Row
    return Connection(raw)

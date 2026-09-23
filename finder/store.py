# -*- coding: utf-8 -*-
"""Persistence for opportunities and refresh history (SQLite or Postgres)."""

from __future__ import annotations

import datetime as dt
import json
import threading
from typing import Iterable

from . import db

FIELDS = ["id", "source", "source_key", "title", "org", "department", "location",
          "country", "country_tier", "url", "description", "posted", "deadline",
          "days_left", "role_key", "role_label", "score", "matched_terms",
          "flags", "positives", "breakdown", "query", "enriched", "career_track",
          "first_seen", "last_seen", "status"]

# Columns added after the first release; created on connect if missing.
LATER_COLUMNS = (("positives", "TEXT"), ("career_track", "TEXT DEFAULT 'academic'"))
PACK_LATER_COLUMNS = (
    ("progress", "INTEGER DEFAULT 0"),
    ("current_step", "TEXT DEFAULT 'research'"),
    ("step_message", "TEXT"),
    ("plan_json", "TEXT"),
    ("cancel_requested", "INTEGER DEFAULT 0"),
    ("updated_at", "TEXT"),
)


_schema_ready = False
_schema_lock = threading.Lock()


def connect() -> db.Connection:
    """
    Open a connection, creating the schema the first time in this process.

    Postgres lives across the network, so running the DDL on every request would
    add a round trip to each one for no reason. It only needs doing once.
    """
    global _schema_ready
    conn = db.connect()
    if not _schema_ready:
        with _schema_lock:
            if not _schema_ready:
                conn.executescript(db.schema())
                _migrate(conn)
                _schema_ready = True
    return conn


def _migrate(conn: db.Connection) -> None:
    have = conn.columns("opportunities")
    changed = False
    for column, ddl in LATER_COLUMNS:
        if column not in have:
            conn.execute("ALTER TABLE opportunities ADD COLUMN %s %s" % (column, ddl))
            changed = True
    if changed:
        conn.commit()
    pack_have = conn.columns("application_packs")
    pack_changed = False
    for column, ddl in PACK_LATER_COLUMNS:
        if column not in pack_have:
            conn.execute("ALTER TABLE application_packs ADD COLUMN %s %s" % (column, ddl))
            pack_changed = True
    if pack_changed:
        conn.commit()
    conn.execute("CREATE INDEX IF NOT EXISTS idx_track ON opportunities(career_track)")
    # Correct previously stored aggregator deadlines when the advert text
    # contains a more specific application closing date.
    from .enrich import explicit_deadline
    repaired = False
    rows = conn.execute(
        "SELECT id,deadline,description FROM opportunities WHERE description IS NOT NULL"
    ).fetchall()
    for row in rows:
        stated = explicit_deadline(row["description"] or "")
        if stated and stated != (row["deadline"] or ""):
            conn.execute("UPDATE opportunities SET deadline=? WHERE id=?", (stated, row["id"]))
            repaired = True
    conn.commit()
    if repaired:
        recompute_days_left(conn)


def _enc(value):
    return json.dumps(value, ensure_ascii=False) if isinstance(value, (list, dict)) else value


def _row(item: dict, now: str) -> tuple:
    values = []
    for field in FIELDS[:-3]:
        value = item.get(field)
        if field == "career_track":
            value = value or "academic"
        values.append(_enc(value))
    return tuple(values) + (now, now, item.get("status", "new"))


def upsert_many(conn: db.Connection, items: Iterable[dict]) -> tuple[int, int]:
    """Insert new postings, refresh the mutable fields of ones we already have."""
    items = list(items)
    if db.IS_POSTGRES and items:
        return _upsert_many_postgres(conn, items)

    now = dt.datetime.now().isoformat(timespec="seconds")
    added = updated = 0
    cur = conn.cursor()
    for item in items:
        cur.execute("SELECT status FROM opportunities WHERE id = ?", (item["id"],))
        if cur.fetchone() is None:
            cur.execute(
                "INSERT INTO opportunities (%s) VALUES (%s)"
                % (",".join(FIELDS), ",".join("?" * len(FIELDS))),
                _row(item, now))
            added += 1
        else:
            cur.execute(
                """UPDATE opportunities SET
                       title=?, org=?, department=?, location=?, country=?,
                       country_tier=?, description=?, posted=?, deadline=?,
                       days_left=?, role_key=?, role_label=?, score=?,
                       matched_terms=?, flags=?, positives=?, breakdown=?,
                       enriched=?, last_seen=?
                   WHERE id=?""",
                (item.get("title"), item.get("org"), item.get("department"),
                 item.get("location"), item.get("country"), item.get("country_tier"),
                 item.get("description"), item.get("posted"), item.get("deadline"),
                 item.get("days_left"), item.get("role_key"), item.get("role_label"),
                 item.get("score"),
                 _enc(item.get("matched_terms") or []),
                 _enc(item.get("flags") or []),
                 _enc(item.get("positives") or []),
                 _enc(item.get("breakdown") or {}),
                 item.get("enriched", 0), now, item["id"]))
            updated += 1
    conn.commit()
    return added, updated


def _upsert_many_postgres(conn: db.Connection, items: list[dict]) -> tuple[int, int]:
    """Bulk Postgres upsert: a few round trips instead of two per posting."""
    now = dt.datetime.now().isoformat(timespec="seconds")
    ids = [item["id"] for item in items]
    existing: set[str] = set()
    for start in range(0, len(ids), 500):
        chunk = ids[start:start + 500]
        placeholders = ",".join("?" for _ in chunk)
        rows = conn.execute(
            "SELECT id FROM opportunities WHERE id IN (%s)" % placeholders,
            chunk).fetchall()
        existing.update(row["id"] for row in rows)

    mutable = [
        "title", "org", "department", "location", "country", "country_tier",
        "description", "posted", "deadline", "days_left", "role_key",
        "role_label", "score", "matched_terms", "flags", "positives",
        "breakdown", "enriched", "last_seen",
        "career_track",
    ]
    update_sql = ",".join(f"{field}=EXCLUDED.{field}" for field in mutable)
    width = len(FIELDS)
    for start in range(0, len(items), 200):
        chunk = items[start:start + 200]
        values_sql = ",".join(
            "(" + ",".join("?" for _ in range(width)) + ")" for _ in chunk)
        params = [value for item in chunk for value in _row(item, now)]
        conn.execute(
            "INSERT INTO opportunities (%s) VALUES %s "
            "ON CONFLICT (id) DO UPDATE SET %s"
            % (",".join(FIELDS), values_sql, update_sql),
            params)
    conn.commit()
    added = sum(1 for item in items if item["id"] not in existing)
    return added, len(items) - added


def recompute_days_left(conn: db.Connection) -> None:
    """Update ISO deadlines in one database operation instead of one network trip per job."""
    if db.IS_POSTGRES:
        conn.execute(
            """UPDATE opportunities
               SET days_left = CAST(deadline AS date) - CURRENT_DATE
               WHERE deadline ~ '^\\d{4}-\\d{2}-\\d{2}$'"""
        )
    else:
        conn.execute(
            """UPDATE opportunities
               SET days_left = CAST(julianday(deadline) - julianday(date('now')) AS INTEGER)
               WHERE deadline GLOB '????-??-??'"""
        )
    conn.commit()


def log_refresh(conn, started, finished, found, added, updated, log_text, ok=True) -> None:
    conn.execute(
        "INSERT INTO refreshes (started, finished, found, added, updated, log, ok)"
        " VALUES (?,?,?,?,?,?,?)",
        (started, finished, found, added, updated, log_text, 1 if ok else 0))
    conn.commit()


def last_refresh(conn) -> dict | None:
    row = conn.execute(
        "SELECT * FROM refreshes WHERE ok = 1 ORDER BY id DESC LIMIT 1").fetchone()
    return dict(row) if row else None


def set_status(conn, opp_id: str, status: str) -> None:
    conn.execute("UPDATE opportunities SET status=? WHERE id=?", (status, opp_id))
    conn.commit()


def decode(row) -> dict:
    item = dict(row)
    for key in ("matched_terms", "flags", "positives", "breakdown"):
        raw = item.get(key)
        if isinstance(raw, (list, dict)):
            continue
        try:
            item[key] = json.loads(raw or ("{}" if key == "breakdown" else "[]"))
        except (ValueError, TypeError):
            item[key] = {} if key == "breakdown" else []
    return item

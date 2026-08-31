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
          "flags", "positives", "breakdown", "query", "enriched", "first_seen",
          "last_seen", "status"]

# Columns added after the first release; created on connect if missing.
LATER_COLUMNS = (("positives", "TEXT"),)


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


def _enc(value):
    return json.dumps(value, ensure_ascii=False) if isinstance(value, (list, dict)) else value


def _row(item: dict, now: str) -> tuple:
    return tuple(_enc(item.get(f)) for f in FIELDS[:-3]) + (now, now, item.get("status", "new"))


def upsert_many(conn: db.Connection, items: Iterable[dict]) -> tuple[int, int]:
    """Insert new postings, refresh the mutable fields of ones we already have."""
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


def recompute_days_left(conn: db.Connection) -> None:
    """days_left is relative to today, so refresh it whenever the app starts."""
    from .scoring import _parse_date
    today = dt.date.today()
    rows = conn.execute(
        "SELECT id, deadline FROM opportunities WHERE deadline IS NOT NULL AND deadline != ''"
    ).fetchall()
    for row in rows:
        d = _parse_date(row["deadline"])
        if d:
            conn.execute("UPDATE opportunities SET days_left=? WHERE id=?",
                         ((d - today).days, row["id"]))
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

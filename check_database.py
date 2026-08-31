# -*- coding: utf-8 -*-
"""
Prove the database works before deploying.

Run this once you have a Postgres connection string, with DATABASE_URL set in
your shell. It creates the tables, writes a test posting, reads it back through
every query the live app uses, then deletes it. Nothing is printed except
pass/fail lines, so the output is safe to paste back into a chat - the
connection string itself is never shown.

    PowerShell:
        $env:DATABASE_URL = "postgresql://...paste yours..."
        python check_database.py

    Git Bash:
        DATABASE_URL="postgresql://...paste yours..." python check_database.py

With no DATABASE_URL set it tests the local SQLite file instead.
"""

from __future__ import annotations

import datetime as dt
import sys
import traceback

from finder import db, store

TEST_ID = "__selftest__"

passed = 0
failed = 0


def check(label: str, fn):
    global passed, failed
    try:
        fn()
    except Exception as exc:
        failed += 1
        print("FAIL  %s" % label)
        print("      %s: %s" % (type(exc).__name__, str(exc)[:300]))
    else:
        passed += 1
        print("ok    %s" % label)


def main() -> int:
    print("Backend: %s\n" % db.backend())

    conn = None

    def _connect():
        nonlocal conn
        conn = store.connect()

    check("connect and create tables", _connect)
    if conn is None:
        print("\nCannot continue without a connection.")
        return 1

    sample = {
        "id": TEST_ID, "source": "Self test", "source_key": "selftest",
        "title": "Assistant Professor of Water Infrastructure",
        "org": "Test University", "department": "Civil Engineering",
        "location": "Leeds, United Kingdom", "country": "United Kingdom",
        "country_tier": "target", "url": "https://example.invalid/selftest",
        "description": "construction management and water distribution networks",
        "posted": dt.date.today().isoformat(),
        "deadline": (dt.date.today() + dt.timedelta(days=30)).isoformat(),
        "days_left": 30, "role_key": "assistant",
        "role_label": "Assistant Professor / Lecturer", "score": 88,
        "matched_terms": ["water infrastructure", "construction management"],
        "flags": [], "positives": ["permanent or tenure-track"],
        "breakdown": {"topic": 90, "role": 100, "country": 100, "timing": 92},
        "query": "self test", "enriched": 1, "status": "new",
    }

    check("insert a posting", lambda: store.upsert_many(conn, [sample]))
    check("update the same posting", lambda: store.upsert_many(conn, [sample]))

    def read_back():
        row = conn.execute("SELECT * FROM opportunities WHERE id = ?", (TEST_ID,)).fetchone()
        assert row is not None, "row not found after insert"
        item = store.decode(row)
        assert item["score"] == 88, "score came back as %r" % item["score"]
        assert isinstance(item["matched_terms"], list), "matched_terms is not a list"
        assert isinstance(item["breakdown"], dict), "breakdown is not a dict"
        assert item["positives"] == ["permanent or tenure-track"], "positives mismatch"

    check("read it back with JSON columns decoded", read_back)

    def filtered_query():
        rows = conn.execute(
            """SELECT * FROM opportunities
               WHERE score >= ? AND status != 'dismissed'
                 AND (days_left IS NULL OR days_left >= 0)
                 AND (lower(title) LIKE ? OR lower(org) LIKE ?)
               ORDER BY score DESC, (days_left IS NULL), days_left ASC
               LIMIT ?""",
            (10, "%water%", "%water%", 50)).fetchall()
        assert any(dict(r)["id"] == TEST_ID for r in rows), "test row missing from filtered query"

    check("the main listing query (search, sort, LIMIT)", filtered_query)

    def facets():
        for sql in (
            "SELECT country AS name, COUNT(*) AS n FROM opportunities "
            "WHERE score >= ? AND country != '' AND status != 'dismissed' "
            "GROUP BY country ORDER BY n DESC",
            "SELECT role_key AS key, role_label AS name, COUNT(*) AS n "
            "FROM opportunities WHERE score >= ? AND status != 'dismissed' "
            "GROUP BY role_key, role_label ORDER BY n DESC",
            "SELECT source_key AS key, source AS name, COUNT(*) AS n "
            "FROM opportunities WHERE score >= ? AND status != 'dismissed' "
            "GROUP BY source_key, source ORDER BY n DESC",
        ):
            conn.execute(sql, (10,)).fetchall()

    check("the sidebar counts (GROUP BY)", facets)

    def summary():
        row = conn.execute(
            """SELECT COUNT(*) AS total,
                      SUM(CASE WHEN score >= 70 THEN 1 ELSE 0 END) AS strong,
                      SUM(CASE WHEN substr(first_seen,1,10) = ? THEN 1 ELSE 0 END) AS today,
                      SUM(CASE WHEN days_left IS NOT NULL AND days_left BETWEEN 0 AND 7
                               THEN 1 ELSE 0 END) AS closing
               FROM opportunities WHERE score >= ?""",
            (dt.date.today().isoformat(), 10)).fetchone()
        assert dict(row)["total"] >= 1, "summary counted nothing"

    check("the header statistics", summary)

    check("mark as saved", lambda: store.set_status(conn, TEST_ID, "saved"))
    check("recompute days remaining", lambda: store.recompute_days_left(conn))
    check("write a refresh log entry",
          lambda: store.log_refresh(conn, "t0", "t1", 1, 1, 0, "self test", ok=True))
    check("read the last refresh back", lambda: store.last_refresh(conn))

    def cleanup():
        conn.execute("DELETE FROM opportunities WHERE id = ?", (TEST_ID,))
        conn.execute("DELETE FROM refreshes WHERE log = ?", ("self test",))
        conn.commit()

    check("clean up the test rows", cleanup)

    conn.close()

    print("\n%d passed, %d failed" % (passed, failed))
    if failed:
        print("\nSomething is wrong with the database setup. Paste the FAIL lines back.")
        return 1
    print("\nThe database is ready. Nothing was left behind.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(1)

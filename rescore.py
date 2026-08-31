# -*- coding: utf-8 -*-
"""
Re-score every stored posting against the current profile.

Run this after editing finder/profile.py when you want the change reflected
immediately instead of waiting for the next refresh. It touches no network.
"""

from __future__ import annotations

import json
import sys

from finder import store
from finder.scoring import score_opportunity


def main() -> int:
    conn = store.connect()
    rows = conn.execute("SELECT * FROM opportunities").fetchall()
    print("Re-scoring %d postings..." % len(rows))

    moved = 0
    for row in rows:
        item = store.decode(row)
        before = item["score"]
        item.update(score_opportunity(item))
        if item["score"] != before:
            moved += 1
        conn.execute(
            """UPDATE opportunities SET score=?, role_key=?, role_label=?,
                   country=?, country_tier=?, matched_terms=?, flags=?,
                   positives=?, breakdown=?, posted=?, deadline=?
               WHERE id=?""",
            (item["score"], item["role_key"], item["role_label"], item["country"],
             item["country_tier"],
             json.dumps(item["matched_terms"], ensure_ascii=False),
             json.dumps(item["flags"], ensure_ascii=False),
             json.dumps(item.get("positives") or [], ensure_ascii=False),
             json.dumps(item["breakdown"], ensure_ascii=False),
             item.get("posted") or "", item.get("deadline") or "",
             item["id"]))
    conn.commit()
    store.recompute_days_left(conn)
    conn.close()

    print("Done. %d postings changed score." % moved)
    return 0


if __name__ == "__main__":
    sys.exit(main())

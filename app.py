# -*- coding: utf-8 -*-
"""
Opportunity Finder - a daily dashboard of academic posts matched to
Ridwan A. Taiwo's CV.

    python app.py            start the server (auto-refreshes if data is stale)
    python app.py --refresh  collect once and exit (for a scheduled task)
    python app.py --no-open  start without launching a browser
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
import threading
import webbrowser

from flask import Flask, jsonify, render_template, request

from finder import db, pipeline, store
from finder.config import DISPLAY_MIN_SCORE
from finder.profile import CANDIDATE

STALE_AFTER_HOURS = int(os.environ.get("STALE_AFTER_HOURS", "10"))

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _hours_since_last_refresh() -> float | None:
    conn = store.connect()
    try:
        last = store.last_refresh(conn)
    finally:
        conn.close()
    if not last or not last.get("finished"):
        return None
    try:
        when = dt.datetime.fromisoformat(last["finished"])
    except (ValueError, TypeError):
        return None
    return (dt.datetime.now() - when).total_seconds() / 3600.0


def _summary(conn) -> dict:
    today = dt.date.today().isoformat()
    row = conn.execute(
        """SELECT
             COUNT(*)                                              AS total,
             SUM(CASE WHEN score >= 70 THEN 1 ELSE 0 END)          AS strong,
             SUM(CASE WHEN substr(first_seen,1,10) = ? THEN 1 ELSE 0 END) AS today,
             SUM(CASE WHEN status = 'saved' THEN 1 ELSE 0 END)      AS saved,
             SUM(CASE WHEN status = 'applied' THEN 1 ELSE 0 END)    AS applied,
             SUM(CASE WHEN days_left IS NOT NULL AND days_left BETWEEN 0 AND 7
                      THEN 1 ELSE 0 END)                            AS closing
           FROM opportunities WHERE score >= ?""",
        (today, DISPLAY_MIN_SCORE)).fetchone()
    last = store.last_refresh(conn)
    return {
        "total": row["total"] or 0,
        "strong": row["strong"] or 0,
        "new_today": row["today"] or 0,
        "saved": row["saved"] or 0,
        "applied": row["applied"] or 0,
        "closing_soon": row["closing"] or 0,
        "last_refresh": (last or {}).get("finished"),
        "last_added": (last or {}).get("added"),
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.before_request
def _refresh_if_stale():
    """
    Keep the hosted copy current without a scheduler.

    A free host suspends the service when nobody is using it, so a cron thread
    inside the app would not fire reliably. Instead every visit checks the age
    of the data and starts a collection in the background if it has gone stale.
    The page renders immediately from what is already stored and picks up the
    new postings as they land.
    """
    if request.path.startswith("/static") or request.path == "/api/refresh/status":
        return
    if pipeline.STATE["running"]:
        return
    age = _hours_since_last_refresh()
    if age is None or age >= STALE_AFTER_HOURS:
        pipeline.run_refresh_background()


@app.route("/")
def index():
    return render_template("index.html", candidate=CANDIDATE)


@app.route("/healthz")
def healthz():
    return jsonify({"ok": True, "backend": db.backend()})


@app.route("/api/opportunities")
def api_opportunities():
    args = request.args
    min_score = int(args.get("min_score", DISPLAY_MIN_SCORE))
    roles = [r for r in args.get("roles", "").split(",") if r]
    countries = [c for c in args.get("countries", "").split(",") if c]
    sources = [s for s in args.get("sources", "").split(",") if s]
    status = args.get("status", "open")          # open | saved | applied | dismissed | all
    search = (args.get("q") or "").strip().lower()
    window = args.get("window", "any")           # any | today | week | month
    deadline = args.get("deadline", "live")      # live | any | soon
    sort = args.get("sort", "score")             # score | deadline | newest
    limit = min(int(args.get("limit", 300)), 1000)

    where = ["score >= ?"]
    params: list = [min_score]

    if roles:
        where.append("role_key IN (%s)" % ",".join("?" * len(roles)))
        params += roles
    if countries:
        where.append("country IN (%s)" % ",".join("?" * len(countries)))
        params += countries
    if sources:
        where.append("source_key IN (%s)" % ",".join("?" * len(sources)))
        params += sources

    if status == "open":
        where.append("status != 'dismissed'")
    elif status != "all":
        where.append("status = ?")
        params.append(status)

    if window != "any":
        days = {"today": 1, "week": 7, "month": 31}.get(window, 3650)
        cutoff = (dt.date.today() - dt.timedelta(days=days - 1)).isoformat()
        where.append("substr(first_seen,1,10) >= ?")
        params.append(cutoff)

    if deadline == "live":
        where.append("(days_left IS NULL OR days_left >= 0)")
    elif deadline == "soon":
        where.append("days_left IS NOT NULL AND days_left BETWEEN 0 AND 14")

    if search:
        where.append("(lower(title) LIKE ? OR lower(org) LIKE ? OR "
                     "lower(location) LIKE ? OR lower(description) LIKE ?)")
        params += ["%%%s%%" % search] * 4

    order = {
        "score": "score DESC, (days_left IS NULL), days_left ASC",
        "deadline": "(days_left IS NULL), days_left ASC, score DESC",
        "newest": "first_seen DESC, score DESC",
    }.get(sort, "score DESC")

    conn = store.connect()
    try:
        rows = conn.execute(
            "SELECT * FROM opportunities WHERE %s ORDER BY %s LIMIT ?"
            % (" AND ".join(where), order), params + [limit]).fetchall()
        items = [store.decode(r) for r in rows]
        for item in items:
            item["description"] = (item.get("description") or "")[:600]
        facets = {
            "countries": [dict(r) for r in conn.execute(
                "SELECT country AS name, COUNT(*) AS n FROM opportunities "
                "WHERE score >= ? AND country != '' AND status != 'dismissed' "
                "GROUP BY country ORDER BY n DESC", (min_score,)).fetchall()],
            # Both non-aggregated columns must appear in GROUP BY: SQLite lets
            # a bare role_key/source_key through, Postgres rejects it.
            "roles": [dict(r) for r in conn.execute(
                "SELECT role_key AS key, role_label AS name, COUNT(*) AS n "
                "FROM opportunities WHERE score >= ? AND status != 'dismissed' "
                "GROUP BY role_key, role_label ORDER BY n DESC", (min_score,)).fetchall()],
            "sources": [dict(r) for r in conn.execute(
                "SELECT source_key AS key, source AS name, COUNT(*) AS n "
                "FROM opportunities WHERE score >= ? AND status != 'dismissed' "
                "GROUP BY source_key, source ORDER BY n DESC", (min_score,)).fetchall()],
        }
        summary = _summary(conn)
    finally:
        conn.close()

    return jsonify({"items": items, "count": len(items),
                    "facets": facets, "summary": summary})


@app.route("/api/opportunity/<opp_id>")
def api_opportunity(opp_id):
    conn = store.connect()
    try:
        row = conn.execute("SELECT * FROM opportunities WHERE id = ?", (opp_id,)).fetchone()
    finally:
        conn.close()
    if row is None:
        return jsonify({"error": "not found"}), 404
    return jsonify(store.decode(row))


@app.route("/api/status", methods=["POST"])
def api_status():
    data = request.get_json(force=True, silent=True) or {}
    opp_id, status = data.get("id"), data.get("status")
    if not opp_id or status not in ("new", "saved", "applied", "dismissed", "seen"):
        return jsonify({"error": "bad request"}), 400
    conn = store.connect()
    try:
        store.set_status(conn, opp_id, status)
        summary = _summary(conn)
    finally:
        conn.close()
    return jsonify({"ok": True, "summary": summary})


@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    if pipeline.STATE["running"]:
        return jsonify({"ok": False, "message": "already running",
                        "state": pipeline.STATE})
    pipeline.run_refresh_background()
    return jsonify({"ok": True, "state": pipeline.STATE})


@app.route("/api/refresh/status")
def api_refresh_status():
    state = dict(pipeline.STATE)
    state["lines"] = state["lines"][-40:]
    conn = store.connect()
    try:
        state["summary"] = _summary(conn)
    finally:
        conn.close()
    return jsonify(state)


@app.route("/api/profile")
def api_profile():
    return jsonify(CANDIDATE)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def _lan_address() -> str:
    """
    This machine's address on the home network, or '' if there isn't one.

    Following the default route is unreliable here: a VPN adapter captures it
    and hands back a carrier-grade NAT address (100.64.0.0/10) that no phone on
    the Wi-Fi can reach. So collect every local address and pick a real private
    LAN one, preferring the ranges home routers actually hand out.
    """
    import socket

    candidates: list[str] = []
    try:
        candidates += socket.gethostbyname_ex(socket.gethostname())[2]
    except OSError:
        pass

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))       # no packets are sent; this just picks a route
        candidates.append(s.getsockname()[0])
    except OSError:
        pass
    finally:
        s.close()

    def rank(ip: str) -> int:
        parts = ip.split(".")
        if len(parts) != 4 or not all(p.isdigit() for p in parts):
            return 99
        a, b = int(parts[0]), int(parts[1])
        if a == 192 and b == 168:
            return 0                                   # the usual home router range
        if a == 10:
            return 1
        if a == 172 and 16 <= b <= 31:
            return 2
        if a == 169 and b == 254:
            return 90                                  # link-local, not routable
        if a == 100 and 64 <= b <= 127:
            return 91                                  # CGNAT, usually a VPN adapter
        if a == 127:
            return 98
        return 50

    ranked = sorted(set(candidates), key=rank)
    return ranked[0] if ranked and rank(ranked[0]) < 50 else ""


def _maybe_auto_refresh():
    age = _hours_since_last_refresh()
    if age is None:
        print("No data yet - running the first collection in the background.")
        pipeline.run_refresh_background()
    elif age >= STALE_AFTER_HOURS:
        print("Data is %.1f h old - refreshing in the background." % age)
        pipeline.run_refresh_background()
    else:
        print("Data is %.1f h old - no refresh needed." % age)


def main() -> int:
    parser = argparse.ArgumentParser(description="Opportunity Finder")
    parser.add_argument("--refresh", action="store_true",
                        help="collect once and exit (for Task Scheduler)")
    parser.add_argument("--no-open", action="store_true",
                        help="do not open a browser window")
    parser.add_argument("--port", type=int, default=57000)
    parser.add_argument("--no-auto-refresh", action="store_true")
    parser.add_argument("--lan", action="store_true",
                        help="also serve to other devices on your home network")
    parser.add_argument("--export", action="store_true",
                        help="write the phone snapshot and exit")
    args = parser.parse_args()

    if args.export:
        from export import write_snapshot
        print("Wrote", write_snapshot())
        return 0

    if args.refresh:
        result = pipeline.run_refresh()
        print("\nFound %d, added %d, updated %d."
              % (result["found"], result["added"], result["updated"]))
        return 1 if result.get("error") else 0

    conn = store.connect()
    store.recompute_days_left(conn)
    conn.close()

    if not args.no_auto_refresh:
        _maybe_auto_refresh()

    url = "http://127.0.0.1:%d/" % args.port
    if not args.no_open:
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()

    print("\n  Opportunity Finder is running at %s" % url)
    if args.lan:
        lan = _lan_address()
        if lan:
            print("  On your phone (same Wi-Fi):  http://%s:%d/" % (lan, args.port))
        else:
            print("  Could not work out this machine's network address.")
    print("  Press Ctrl+C to stop.\n")

    app.run(host="0.0.0.0" if args.lan else "127.0.0.1",
            port=args.port, debug=False, threaded=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

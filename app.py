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
import base64
import io
import json
import sys
import threading
import webbrowser

from flask import (Flask, flash, g, jsonify, redirect, render_template, request,
                   send_file, session, url_for)

from finder import db, pipeline, store
from finder import auth, matching, profiles, providers
from finder.application_pack import (
    get_pack, get_pack_opportunity, pack_filename, start_pack,
)
from finder.config import DISPLAY_MIN_SCORE

STALE_AFTER_HOURS = int(os.environ.get("STALE_AFTER_HOURS", "10"))

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False
app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY", "local-development-key-change-before-deploy"),
    MAX_CONTENT_LENGTH=profiles.MAX_CV_BYTES + 1024 * 1024,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("RENDER", "").lower() == "true",
    PERMANENT_SESSION_LIFETIME=dt.timedelta(days=14),
)
app.jinja_env.globals["csrf_token"] = auth.csrf_token


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


def _global_summary(conn) -> dict:
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


def _user_summary(conn, user_id: str, kind: str, min_score: int) -> dict:
    today = dt.date.today().isoformat()
    row = conn.execute(
        """SELECT COUNT(*) AS total,
                  SUM(CASE WHEN m.score >= 70 THEN 1 ELSE 0 END) AS strong,
                  SUM(CASE WHEN substr(o.first_seen,1,10)=? THEN 1 ELSE 0 END) AS today,
                  SUM(CASE WHEN m.status='saved' THEN 1 ELSE 0 END) AS saved,
                  SUM(CASE WHEN m.status='applied' THEN 1 ELSE 0 END) AS applied,
                  SUM(CASE WHEN o.days_left IS NOT NULL AND o.days_left BETWEEN 0 AND 7
                           THEN 1 ELSE 0 END) AS closing
           FROM user_matches m JOIN opportunities o ON o.id=m.opportunity_id
           WHERE m.user_id=? AND m.profile_kind=? AND m.score>=?""",
        (today, user_id, kind, min_score),
    ).fetchone()
    last = store.last_refresh(conn)
    return {
        "total": row["total"] or 0, "strong": row["strong"] or 0,
        "new_today": row["today"] or 0, "saved": row["saved"] or 0,
        "applied": row["applied"] or 0, "closing_soon": row["closing"] or 0,
        "last_refresh": (last or {}).get("finished"), "last_added": (last or {}).get("added"),
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.before_request
def _load_authenticated_user():
    auth.load_user()


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
    if request.path not in ("/", "/api/opportunities"):
        return
    if pipeline.STATE["running"]:
        return
    age = _hours_since_last_refresh()
    if age is None or age >= STALE_AFTER_HOURS:
        pipeline.run_refresh_background()


@app.route("/")
@auth.login_required
def index():
    kind = request.args.get("track", "academic")
    if kind not in ("academic", "industry"):
        kind = "academic"
    profile = profiles.get_profile(g.user["id"], kind)
    return render_template("index.html", user=g.user, profile=profile, track=kind,
                           csrf=auth.csrf_token())


@app.route("/register", methods=["GET", "POST"])
def register():
    if g.user:
        return redirect(url_for("index"))
    if request.method == "POST":
        auth.verify_csrf()
        user, error = auth.register_user(request.form.get("name", ""),
                                         request.form.get("email", ""),
                                         request.form.get("password", ""))
        if error:
            flash(error, "error")
        else:
            auth.begin_session(user)
            return redirect(url_for("profile_page"))
    return render_template("auth.html", mode="register", csrf=auth.csrf_token())


@app.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(url_for("index"))
    if request.method == "POST":
        auth.verify_csrf()
        user = auth.authenticate(request.form.get("email", ""), request.form.get("password", ""))
        if not user:
            flash("Email address or password was not recognised.", "error")
        else:
            auth.begin_session(user)
            session.permanent = True
            return redirect(url_for("index"))
    return render_template("auth.html", mode="login", csrf=auth.csrf_token())


@app.route("/logout", methods=["POST"])
@auth.login_required
def logout():
    auth.verify_csrf()
    session.clear()
    return redirect(url_for("login"))


@app.route("/profile")
@auth.login_required
def profile_page():
    return render_template("profile.html", user=g.user,
                           profiles=profiles.profile_summaries(g.user["id"]),
                           csrf=auth.csrf_token())


@app.route("/settings")
@auth.login_required
def settings_page():
    return render_template("settings.html", user=g.user,
                           config=providers.get_config(g.user["id"]),
                           catalog=providers.public_catalog(), csrf=auth.csrf_token())


@app.route("/healthz")
def healthz():
    return jsonify({"ok": True, "backend": db.backend(),
                    "matcher_version": matching.MATCHER_VERSION,
                    "default_search": providers.public_catalog()["search"][0]})


@app.route("/api/opportunities")
@auth.login_required
def api_opportunities():
    args = request.args
    kind = args.get("track", "academic")
    if kind not in ("academic", "industry"):
        return jsonify({"error": "unknown career track"}), 400
    user_profile = profiles.get_profile(g.user["id"], kind)
    if not user_profile:
        return jsonify({"items": [], "count": 0,
                        "facets": {"countries": [], "roles": [], "sources": []},
                        "summary": {}, "setup_required": True})
    # Existing accounts are upgraded on their first visit after a matcher
    # release, so users do not need to upload the CV again.
    if not matching.matches_are_current(g.user["id"], kind):
        matching.rebuild_matches(g.user["id"], kind)
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

    where = ["m.user_id = ?", "m.profile_kind = ?", "m.score >= ?", "o.career_track = ?"]
    params: list = [g.user["id"], kind, min_score, kind]

    if roles:
        where.append("o.role_key IN (%s)" % ",".join("?" * len(roles)))
        params += roles
    if countries:
        where.append("o.country IN (%s)" % ",".join("?" * len(countries)))
        params += countries
    if sources:
        where.append("o.source_key IN (%s)" % ",".join("?" * len(sources)))
        params += sources

    if status == "open":
        where.append("m.status != 'dismissed'")
    elif status != "all":
        where.append("m.status = ?")
        params.append(status)

    if window != "any":
        days = {"today": 1, "week": 7, "month": 31}.get(window, 3650)
        cutoff = (dt.date.today() - dt.timedelta(days=days - 1)).isoformat()
        where.append("substr(o.first_seen,1,10) >= ?")
        params.append(cutoff)

    if deadline == "live":
        where.append("(o.days_left IS NULL OR o.days_left >= 0)")
    elif deadline == "soon":
        where.append("o.days_left IS NOT NULL AND o.days_left BETWEEN 0 AND 14")

    if search:
        where.append("(lower(o.title) LIKE ? OR lower(o.org) LIKE ? OR "
                     "lower(o.location) LIKE ? OR lower(o.description) LIKE ?)")
        params += ["%%%s%%" % search] * 4

    order = {
        "score": "m.score DESC, (o.days_left IS NULL), o.days_left ASC",
        "deadline": "(o.days_left IS NULL), o.days_left ASC, m.score DESC",
        "newest": "o.first_seen DESC, m.score DESC",
    }.get(sort, "m.score DESC")

    conn = store.connect()
    try:
        rows = conn.execute(
            """SELECT o.*,m.score AS user_score,m.matched_terms AS user_terms,
                      m.breakdown AS user_breakdown,m.status AS user_status
               FROM user_matches m JOIN opportunities o ON o.id=m.opportunity_id
               WHERE %s ORDER BY %s LIMIT ?"""
            % (" AND ".join(where), order), params + [limit]).fetchall()
        items = []
        for row in rows:
            item = store.decode(row)
            item["score"] = item.pop("user_score")
            item["status"] = item.pop("user_status")
            item["matched_terms"] = json.loads(item.pop("user_terms") or "[]")
            item["breakdown"] = json.loads(item.pop("user_breakdown") or "{}")
            items.append(item)
        for item in items:
            item["description"] = (item.get("description") or "")[:600]
        facets = {
            "countries": [dict(r) for r in conn.execute(
                """SELECT o.country AS name,COUNT(*) AS n FROM user_matches m
                   JOIN opportunities o ON o.id=m.opportunity_id
                   WHERE m.user_id=? AND m.profile_kind=? AND m.score>=?
                     AND o.country!='' AND m.status!='dismissed'
                   GROUP BY o.country ORDER BY n DESC""",
                (g.user["id"], kind, min_score)).fetchall()],
            # Both non-aggregated columns must appear in GROUP BY: SQLite lets
            # a bare role_key/source_key through, Postgres rejects it.
            "roles": [dict(r) for r in conn.execute(
                """SELECT o.role_key AS key,o.role_label AS name,COUNT(*) AS n
                   FROM user_matches m JOIN opportunities o ON o.id=m.opportunity_id
                   WHERE m.user_id=? AND m.profile_kind=? AND m.score>=? AND m.status!='dismissed'
                   GROUP BY o.role_key,o.role_label ORDER BY n DESC""",
                (g.user["id"], kind, min_score)).fetchall()],
            "sources": [dict(r) for r in conn.execute(
                """SELECT o.source_key AS key,o.source AS name,COUNT(*) AS n
                   FROM user_matches m JOIN opportunities o ON o.id=m.opportunity_id
                   WHERE m.user_id=? AND m.profile_kind=? AND m.score>=? AND m.status!='dismissed'
                   GROUP BY o.source_key,o.source ORDER BY n DESC""",
                (g.user["id"], kind, min_score)).fetchall()],
        }
        summary = _user_summary(conn, g.user["id"], kind, min_score)
    finally:
        conn.close()

    domain_label = (user_profile.get("profile") or {}).get("domain_label", "your field")
    coverage_note = (
        f"No reliable {domain_label} matches meet this score yet. The app now hides "
        "jobs from other occupations instead of showing misleading keyword matches."
        if not items else ""
    )
    return jsonify({"items": items, "count": len(items),
                    "facets": facets, "summary": summary,
                    "profile_domain": (user_profile.get("profile") or {}).get("primary_domain"),
                    "coverage_note": coverage_note})


@app.route("/api/opportunity/<opp_id>")
@auth.login_required
def api_opportunity(opp_id):
    kind = request.args.get("track", "academic")
    conn = store.connect()
    try:
        row = conn.execute(
            """SELECT o.*,m.score AS user_score,m.matched_terms AS user_terms,
                      m.breakdown AS user_breakdown,m.status AS user_status
               FROM user_matches m JOIN opportunities o ON o.id=m.opportunity_id
               WHERE o.id=? AND m.user_id=? AND m.profile_kind=?""",
            (opp_id, g.user["id"], kind)).fetchone()
    finally:
        conn.close()
    if row is None:
        return jsonify({"error": "not found"}), 404
    item = store.decode(row)
    item["score"] = item.pop("user_score"); item["status"] = item.pop("user_status")
    item["matched_terms"] = json.loads(item.pop("user_terms") or "[]")
    item["breakdown"] = json.loads(item.pop("user_breakdown") or "{}")
    return jsonify(item)


@app.route("/api/status", methods=["POST"])
@auth.login_required
def api_status():
    auth.verify_csrf()
    data = request.get_json(force=True, silent=True) or {}
    opp_id, status = data.get("id"), data.get("status")
    kind = data.get("track", "academic")
    if not opp_id or status not in ("new", "saved", "applied", "dismissed", "seen"):
        return jsonify({"error": "bad request"}), 400
    matching.set_user_status(g.user["id"], opp_id, kind, status)
    conn = store.connect()
    try: summary = _user_summary(conn, g.user["id"], kind, DISPLAY_MIN_SCORE)
    finally: conn.close()
    return jsonify({"ok": True, "summary": summary})


@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    if pipeline.STATE["running"]:
        return jsonify({"ok": False, "message": "already running",
                        "state": pipeline.STATE})
    track = request.args.get("track")
    tracks = {track} if track in {"academic", "industry"} else None
    pipeline.run_refresh_background(tracks)
    return jsonify({"ok": True, "state": pipeline.STATE})


@app.route("/api/refresh/status")
def api_refresh_status():
    state = dict(pipeline.STATE)
    state["lines"] = state["lines"][-40:]
    conn = store.connect()
    try:
        state["summary"] = _global_summary(conn)
    finally:
        conn.close()
    return jsonify(state)


@app.route("/api/profiles")
@auth.login_required
def api_profiles():
    return jsonify(profiles.profile_summaries(g.user["id"]))


@app.route("/api/profiles/<kind>", methods=["POST"])
@auth.login_required
def api_upload_profile(kind):
    auth.verify_csrf()
    upload = request.files.get("cv")
    if not upload or not upload.filename:
        return jsonify({"error": "Choose a CV file to upload."}), 400
    try:
        result = profiles.save_profile(g.user["id"], kind, upload.filename,
                                       upload.stream.read(profiles.MAX_CV_BYTES + 1))
        result["matched"] = matching.rebuild_matches(g.user["id"], kind)
        return jsonify(result)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@app.route("/api/profiles/<kind>/preferences", methods=["POST"])
@auth.login_required
def api_profile_preferences(kind):
    auth.verify_csrf()
    try:
        result = profiles.update_preferences(
            g.user["id"], kind, request.get_json(silent=True) or {})
        result["matched"] = matching.rebuild_matches(g.user["id"], kind)
        return jsonify(result)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@app.route("/api/providers")
@auth.login_required
def api_provider_config():
    return jsonify({"config": providers.get_config(g.user["id"]),
                    "catalog": providers.public_catalog()})


@app.route("/api/providers", methods=["POST"])
@auth.login_required
def api_save_provider():
    auth.verify_csrf()
    try:
        config = providers.save_config(g.user["id"], request.get_json(silent=True) or {})
        return jsonify({"ok": True, "config": config})
    except (ValueError, RuntimeError) as exc:
        return jsonify({"error": str(exc)}), 400


@app.route("/api/providers/test", methods=["POST"])
@auth.login_required
def api_test_provider():
    auth.verify_csrf()
    try:
        answer = providers.chat(g.user["id"], "Reply with exactly: connection successful",
                                "Test this provider configuration.", max_tokens=30)
        config = providers.get_config(g.user["id"], include_keys=True) or {}
        search_provider = config.get("search_provider", "duckduckgo")
        search_results = None
        if search_provider != "duckduckgo":
            from finder.research import _search
            search_results = len(_search(
                'registered nurse job Canada apply', search_provider,
                config.get("search_key", ""), limit=2))
        return jsonify({"ok": True, "response": answer[:200],
                        "search_provider": search_provider,
                        "search_results": search_results})
    except Exception as exc:
        return jsonify({"error": f"{type(exc).__name__}: {exc}"}), 400


@app.route("/api/packs", methods=["POST"])
@auth.login_required
def api_create_pack():
    auth.verify_csrf()
    data = request.get_json(silent=True) or {}
    kind = data.get("track", "academic")
    if kind not in ("academic", "industry") or not data.get("opportunity_id"):
        return jsonify({"error": "Invalid application pack request."}), 400
    if not providers.get_config(g.user["id"]):
        return jsonify({"error": "Configure and test an AI provider first.",
                        "settings_url": url_for("settings_page")}), 400
    pack_id = start_pack(g.user["id"], data["opportunity_id"], kind,
                         data.get("documents") or [])
    return jsonify({"ok": True, "id": pack_id, "status": "working"}), 202


@app.route("/api/packs/<pack_id>")
@auth.login_required
def api_pack_status(pack_id):
    pack = get_pack(g.user["id"], pack_id)
    return (jsonify(pack) if pack else (jsonify({"error": "not found"}), 404))


@app.route("/api/packs/<pack_id>/download")
@auth.login_required
def download_pack(pack_id):
    pack = get_pack(g.user["id"], pack_id, include_blob=True)
    if not pack or pack["status"] != "ready" or not pack.get("zip_blob"):
        return jsonify({"error": "Application pack is not ready."}), 404
    opportunity = get_pack_opportunity(pack) or {}
    return send_file(io.BytesIO(base64.b64decode(pack["zip_blob"])),
                     mimetype="application/zip", as_attachment=True,
                     download_name=pack_filename(opportunity))


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

# -*- coding: utf-8 -*-
"""Fetch -> score -> save -> enrich -> save again."""

from __future__ import annotations

import datetime as dt
import threading
import traceback

from . import store
from .config import LIMITS, SOURCES_ENABLED
from .enrich import enrich
from .scoring import score_opportunity
from .sources import REGISTRY
from . import industry

# Progress shared with the web UI.
STATE = {
    "running": False,
    "stage": "idle",
    "lines": [],
    "started": None,
    "finished": None,
    "added": 0,
    "updated": 0,
    "found": 0,
    "error": None,
}
_LOCK = threading.Lock()


def _log(line: str) -> None:
    with _LOCK:
        STATE["lines"].append(line)
        if len(STATE["lines"]) > 400:
            del STATE["lines"][:-400]
    try:
        print(line, flush=True)
    except (OSError, ValueError):
        # No usable stdout - a scheduled task with no console, or a closed pipe.
        # The run must carry on; STATE and the refresh log still have the detail.
        pass


def _apply_score(item: dict) -> dict:
    item.update(score_opportunity(item))
    return item


def _enriched_ids() -> set[str]:
    """Adverts already opened, so a repeat run never re-reads them."""
    conn = store.connect()
    try:
        return {r["id"] for r in conn.execute(
            "SELECT id FROM opportunities WHERE enriched = 1").fetchall()}
    finally:
        conn.close()


def _carry_forward(items: list[dict]) -> None:
    """Keep detail we already fetched when a listing re-serves a posting."""
    conn = store.connect()
    try:
        known = {r["id"]: r for r in conn.execute(
            "SELECT id, deadline, posted, location, description "
            "FROM opportunities WHERE enriched = 1").fetchall()}
    finally:
        conn.close()
    for item in items:
        row = known.get(item["id"])
        if not row:
            continue
        for field in ("deadline", "posted", "location"):
            if row[field] and not item.get(field):
                item[field] = row[field]
        if len(row["description"] or "") > len(item.get("description") or ""):
            item["description"] = row["description"]
        item["enriched"] = 1


def _save(items: list[dict]) -> tuple[int, int]:
    conn = store.connect()
    try:
        return store.upsert_many(conn, items)
    finally:
        conn.close()


def run_refresh(enrich_details: bool = True, tracks: set[str] | None = None) -> dict:
    """
    One full collection pass.

    Each source is scored and written as soon as it is fetched, rather than
    everything being held until the end. On a host that suspends idle services
    a run can be cut off part way, and this way the work already done survives.
    """
    tracks = tracks or {"academic", "industry"}
    with _LOCK:
        if STATE["running"]:
            return dict(STATE)
        STATE.update(running=True, stage="starting", lines=[], error=None,
                     added=0, updated=0, found=0,
                     started=dt.datetime.now().isoformat(timespec="seconds"),
                     finished=None)

    started = STATE["started"]
    seen_ids: set[str] = set()
    seen_sigs: set[tuple] = set()
    everything: list[dict] = []

    try:
        for key, module in (REGISTRY.items() if "academic" in tracks else []):
            if not SOURCES_ENABLED.get(key, True):
                continue
            STATE["stage"] = "searching %s" % module.NAME
            _log("[%s]" % module.NAME)
            try:
                got = module.fetch(_log)
            except Exception as exc:            # a dead source must not kill the run
                _log("  !! %s failed: %s" % (module.NAME, exc))
                continue

            fresh = []
            for item in got:
                sig = ((item.get("title") or "").lower().strip()[:90],
                       (item.get("org") or "").lower().strip()[:50])
                if item["id"] in seen_ids or (sig[0] and sig in seen_sigs):
                    continue
                seen_ids.add(item["id"])
                seen_sigs.add(sig)
                fresh.append(item)

            _carry_forward(fresh)
            for item in fresh:
                _apply_score(item)

            added, updated = _save(fresh)
            STATE["added"] += added
            STATE["updated"] += updated
            STATE["found"] += len(fresh)
            everything.extend(fresh)
            _log("  -> %d postings (%d new)" % (len(fresh), added))

        if "industry" in tracks:
            STATE["stage"] = "searching industry jobs"
            _log("[Industry jobs]")
            try:
                industry_items = industry.fetch(_log)
                added, updated = _save(industry_items)
                STATE["added"] += added
                STATE["updated"] += updated
                STATE["found"] += len(industry_items)
                _log("  -> %d industry postings (%d new)" % (len(industry_items), added))
            except Exception as exc:
                _log("  !! Industry sources failed: %s" % exc)

        if enrich_details:
            STATE["stage"] = "reading adverts for deadlines"
            already = _enriched_ids()
            candidates = [i for i in everything
                          if i["score"] >= LIMITS["detail_min_score"]
                          and i["id"] not in already
                          and i["source_key"] != "fellowships"
                          and (i.get("needs_detail") or not i.get("deadline"))]
            candidates.sort(key=lambda i: -i["score"])
            candidates = candidates[:LIMITS["detail_fetch_max"]]
            _log("Opening %d adverts for deadline and location detail" % len(candidates))

            batch: list[dict] = []
            for n, item in enumerate(candidates, 1):
                try:
                    if enrich(item):
                        _apply_score(item)      # detail text can change the match
                        batch.append(item)
                except Exception as exc:
                    _log("  detail failed: %s (%s)" % (item.get("title", "")[:50], exc))
                if n % 10 == 0:
                    STATE["stage"] = "reading adverts %d/%d" % (n, len(candidates))
                    _log("  ... %d/%d" % (n, len(candidates)))
                    if batch:
                        _save(batch)            # keep partial progress
                        batch = []
            if batch:
                _save(batch)

        STATE["stage"] = "finishing"
        try:
            from .matching import rebuild_all_matches
            matched = rebuild_all_matches()
            _log("Updated %d private user matches" % matched)
        except Exception as exc:
            _log("  !! User match refresh failed: %s" % exc)
        conn = store.connect()
        try:
            store.recompute_days_left(conn)
            finished = dt.datetime.now().isoformat(timespec="seconds")
            store.log_refresh(conn, started, finished, STATE["found"],
                              STATE["added"], STATE["updated"],
                              "\n".join(STATE["lines"][-200:]), ok=True)
        finally:
            conn.close()

        STATE.update(finished=finished, stage="done")
        _log("Done: %d scanned, %d new, %d updated"
             % (STATE["found"], STATE["added"], STATE["updated"]))

    except Exception as exc:
        STATE["error"] = "%s: %s" % (type(exc).__name__, exc)
        _log("REFRESH FAILED\n" + traceback.format_exc())
        try:
            conn = store.connect()
            store.log_refresh(conn, started,
                              dt.datetime.now().isoformat(timespec="seconds"),
                              STATE["found"], STATE["added"], STATE["updated"],
                              STATE["error"], ok=False)
            conn.close()
        except Exception:
            pass
    finally:
        STATE["running"] = False
        if STATE["stage"] != "done":
            STATE["stage"] = "failed" if STATE["error"] else "idle"

    return dict(STATE)


def run_refresh_background(tracks: set[str] | None = None) -> None:
    if STATE["running"]:
        return
    threading.Thread(target=run_refresh, kwargs={"tracks": tracks}, daemon=True,
                     name="refresh").start()

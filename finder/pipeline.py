# -*- coding: utf-8 -*-
"""Fetch -> score -> save -> enrich -> save again."""

from __future__ import annotations

import datetime as dt
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed

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
    hint = item.get("country_hint")
    item.update(score_opportunity(item))
    if hint and not item.get("country"):
        # The board only serves one country, so a posting with no place in its
        # text still belongs there.
        item["country"] = hint
        item["country_tier"] = "target"
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
    """Keep detail we already fetched when a listing re-serves a posting.

    Only the small fields are read back. The stored advert text is protected by the
    save itself (a shorter snippet never replaces a longer stored advert), so nothing
    large has to travel from the database on every refresh.
    """
    ids = [item["id"] for item in items]
    known: dict[str, dict] = {}
    conn = store.connect()
    try:
        for start in range(0, len(ids), 400):
            chunk = ids[start:start + 400]
            marks = ",".join("?" for _ in chunk)
            for row in conn.execute(
                    "SELECT id, deadline, posted, location FROM opportunities "
                    "WHERE enriched = 1 AND id IN (%s)" % marks, chunk).fetchall():
                known[row["id"]] = row
    finally:
        conn.close()
    for item in items:
        row = known.get(item["id"])
        if not row:
            continue
        for field in ("deadline", "posted", "location"):
            if row[field] and not item.get(field):
                item[field] = row[field]
        item["enriched"] = 1


def _save(items: list[dict]) -> tuple[int, int]:
    conn = store.connect()
    try:
        return store.upsert_many(conn, items)
    finally:
        conn.close()


def _enrich_parallel(candidates: list[dict]) -> None:
    """Open adverts several at a time; every board is still rate-limited per host."""
    if not candidates:
        return
    done = 0
    batch: list[dict] = []

    def one(item):
        try:
            return item, enrich(item), None
        except Exception as exc:
            return item, False, exc

    with ThreadPoolExecutor(max_workers=8) as pool:
        for item, changed, error in pool.map(one, candidates):
            done += 1
            if error is not None:
                _log("  detail failed: %s (%s)" % (item.get("title", "")[:50], error))
            elif changed:
                if item.get("career_track") != "industry":
                    _apply_score(item)          # detail text can change the match
                batch.append(item)
            if done % 20 == 0:
                STATE["stage"] = "reading adverts %d/%d" % (done, len(candidates))
                _log("  ... %d/%d" % (done, len(candidates)))
                if batch:
                    _save(batch)                # keep partial progress
                    batch = []
    if batch:
        _save(batch)


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
        # ---- academic boards: all sources at once -------------------------
        if "academic" in tracks:
            active = [(key, module) for key, module in REGISTRY.items()
                      if SOURCES_ENABLED.get(key, True)]
            STATE["stage"] = "searching %d academic job boards" % len(active)
            _log("[Academic boards: %s]" % ", ".join(m.NAME for _, m in active))

            def fetch_one(entry):
                key, module = entry
                began = time.time()
                try:
                    return key, module, module.fetch(_log), None, time.time() - began
                except Exception as exc:          # a dead source must not kill the run
                    return key, module, [], exc, time.time() - began

            with ThreadPoolExecutor(max_workers=len(active) or 1) as pool:
                futures = [pool.submit(fetch_one, entry) for entry in active]
                for future in as_completed(futures):
                    key, module, got, error, seconds = future.result()
                    if error is not None:
                        _log("  !! %s failed: %s" % (module.NAME, error))
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
                    _log("  -> %s: %d postings (%d new) in %.0fs"
                         % (module.NAME, len(fresh), added, seconds))

        # ---- industry boards ----------------------------------------------
        if "industry" in tracks:
            STATE["stage"] = "searching industry job boards"
            _log("[Industry boards]")
            try:
                industry_items = industry.fetch(_log)
                _carry_forward(industry_items)
                added, updated = _save(industry_items)
                STATE["added"] += added
                STATE["updated"] += updated
                STATE["found"] += len(industry_items)
                everything.extend(industry_items)
                _log("  -> %d industry postings (%d new)" % (len(industry_items), added))
            except Exception as exc:
                _log("  !! Industry sources failed: %s" % exc)

        # ---- read the adverts themselves for deadlines --------------------
        if enrich_details:
            STATE["stage"] = "reading adverts for deadlines"
            already = _enriched_ids()
            def wants_detail(item: dict) -> bool:
                if item["id"] in already or item["source_key"] == "fellowships":
                    return False
                if item.get("needs_detail"):
                    return True
                # Academic adverts that scored well but state no closing date.
                return (item.get("career_track") != "industry" and not item.get("deadline")
                        and item.get("score", 0) >= LIMITS["detail_min_score"])

            candidates = [i for i in everything if wants_detail(i)]
            candidates.sort(key=lambda i: -i.get("score", 0))
            candidates = candidates[:LIMITS["detail_fetch_max"]]
            _log("Opening %d adverts for deadline and location detail" % len(candidates))
            _enrich_parallel(candidates)

        STATE["stage"] = "finishing"
        conn = store.connect()
        try:
            store.recompute_days_left(conn)     # before matching: timing depends on it
        finally:
            conn.close()
        try:
            from .matching import rebuild_all_matches
            matched = rebuild_all_matches()
            _log("Updated %d private user matches" % matched)
        except Exception as exc:
            _log("  !! User match refresh failed: %s" % exc)
        finished = dt.datetime.now().isoformat(timespec="seconds")
        conn = store.connect()
        try:
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

"""Private, CV-specific opportunity scoring and user status."""

from __future__ import annotations

import datetime as dt
import json
import math
import re

from . import store
from .auth import now
from .profiles import get_profile


def _terms(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z][a-z0-9+#.-]{2,}", (text or "").lower())
            if len(w) > 3}


def score_for_profile(opportunity: dict, profile: dict) -> tuple[int, list[str], dict]:
    structured = profile.get("profile") or {}
    cv_text = profile.get("cv_text") or ""
    keywords = list(structured.get("keywords") or [])
    job_blob = " ".join(str(opportunity.get(k) or "") for k in
                        ("title", "org", "department", "description", "location")).lower()
    cv_words = _terms(cv_text)
    job_words = _terms(job_blob)
    phrase_hits = [k for k in keywords if str(k).lower() in job_blob]
    word_hits = sorted(cv_words & job_words, key=lambda w: (-len(w), w))
    matched = list(dict.fromkeys(phrase_hits + word_hits))[:16]

    phrase_score = min(1.0, len(phrase_hits) / 7.0)
    overlap = len(cv_words & job_words) / max(12.0, math.sqrt(max(1, len(cv_words) * len(job_words))))
    topic = min(1.0, 0.65 * phrase_score + 0.35 * min(1.0, overlap * 5))
    titles = [t.lower() for t in structured.get("target_titles") or []]
    role = 1.0 if any(t in (opportunity.get("title") or "").lower() for t in titles) else 0.58
    country = 1.0 if opportunity.get("country_tier") == "target" else 0.72
    days = opportunity.get("days_left")
    timing = 0.9 if days is None or days >= 14 else (0.7 if days >= 4 else 0.4)
    score = round(100 * (0.55 * topic + 0.22 * role + 0.13 * country + 0.10 * timing))
    if not matched:
        score = min(score, 28)
    return max(0, min(100, score)), matched, {
        "topic": round(topic * 100), "role": round(role * 100),
        "country": round(country * 100), "timing": round(timing * 100),
    }


def rebuild_matches(user_id: str, kind: str) -> int:
    profile = get_profile(user_id, kind, include_text=True)
    if not profile:
        return 0
    conn = store.connect()
    try:
        rows = conn.execute(
            "SELECT * FROM opportunities WHERE career_track=?", (kind,)
        ).fetchall()
        current = conn.execute(
            "SELECT opportunity_id,status FROM user_matches WHERE user_id=? AND profile_kind=?",
            (user_id, kind),
        ).fetchall()
        statuses = {row["opportunity_id"]: row["status"] for row in current}
        values = []
        for row in rows:
            item = store.decode(row)
            score, terms, breakdown = score_for_profile(item, profile)
            status = statuses.get(item["id"], "new")
            values.append((user_id, item["id"], kind, score, json.dumps(terms),
                           json.dumps(breakdown), status, now()))
        for start in range(0, len(values), 300):
            chunk = values[start:start + 300]
            placeholders = ",".join("(" + ",".join("?" for _ in range(8)) + ")"
                                    for _ in chunk)
            params = [value for record in chunk for value in record]
            conn.execute(
                """INSERT INTO user_matches
                   (user_id,opportunity_id,profile_kind,score,matched_terms,breakdown,status,updated_at)
                   VALUES %s
                   ON CONFLICT(user_id,opportunity_id,profile_kind) DO UPDATE SET
                   score=excluded.score,matched_terms=excluded.matched_terms,
                   breakdown=excluded.breakdown,updated_at=excluded.updated_at""" % placeholders,
                params)
        conn.commit()
        return len(values)
    finally:
        conn.close()


def rebuild_all_matches() -> int:
    conn = store.connect()
    try:
        rows = conn.execute("SELECT user_id,kind FROM user_profiles").fetchall()
    finally:
        conn.close()
    return sum(rebuild_matches(row["user_id"], row["kind"]) for row in rows)


def set_user_status(user_id: str, opportunity_id: str, kind: str, status: str) -> None:
    conn = store.connect()
    try:
        row = conn.execute(
            "SELECT 1 FROM user_matches WHERE user_id=? AND opportunity_id=? AND profile_kind=?",
            (user_id, opportunity_id, kind),
        ).fetchone()
        if not row:
            raise ValueError("Opportunity has not been matched to this profile.")
        conn.execute(
            "UPDATE user_matches SET status=?,updated_at=? WHERE user_id=? AND opportunity_id=? AND profile_kind=?",
            (status, now(), user_id, opportunity_id, kind),
        )
        conn.commit()
    finally:
        conn.close()


def decode_match(row) -> dict:
    item = store.decode(row)
    for key in ("matched_terms", "breakdown"):
        raw = item.get(key)
        if isinstance(raw, (list, dict)):
            continue
        try:
            item[key] = json.loads(raw or ("{}" if key == "breakdown" else "[]"))
        except (TypeError, ValueError):
            item[key] = {} if key == "breakdown" else []
    return item

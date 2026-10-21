# -*- coding: utf-8 -*-
"""Search phrases for the job boards, derived from the CVs that users uploaded.

The boards are queried with what the registered users actually work on, so a
nursing CV pulls nursing posts and a civil-engineering CV pulls civil posts,
instead of everyone being served one hard-coded subject list.
"""

from __future__ import annotations

import json

from . import store
from .config import SEARCH_QUERIES
from .domains import TARGET_TITLES

ACADEMIC_ROLES = ("postdoctoral", "assistant professor", "lecturer")
MAX_ACADEMIC_QUERIES = 30
MAX_INDUSTRY_QUERIES = 10


def _profiles(kind: str) -> list[dict]:
    conn = store.connect()
    try:
        rows = conn.execute(
            "SELECT profile_json FROM user_profiles WHERE kind=?", (kind,)).fetchall()
    finally:
        conn.close()
    out = []
    for row in rows:
        try:
            out.append(json.loads(row["profile_json"] or "{}"))
        except (TypeError, ValueError):
            continue
    return out


def _subject_phrases(profile: dict, limit: int) -> list[str]:
    phrases = [k for k in profile.get("keywords") or [] if " " in str(k)]
    return phrases[:limit]


def academic_queries() -> list[str]:
    """Subject phrases first, then role-shaped variants of the strongest ones."""
    profiles = _profiles("academic")
    if not profiles:
        return list(SEARCH_QUERIES)
    queries: list[str] = []
    per_profile = max(6, MAX_ACADEMIC_QUERIES // max(1, len(profiles)) - 3)
    for profile in profiles:
        phrases = _subject_phrases(profile, per_profile)
        queries.extend(phrases)
        for phrase in phrases[:3]:
            queries.extend(f"{role} {phrase}" for role in ACADEMIC_ROLES)
    deduped = list(dict.fromkeys(q.lower() for q in queries if q))
    return deduped[:MAX_ACADEMIC_QUERIES] or list(SEARCH_QUERIES)


def industry_titles() -> list[str]:
    """Job titles to search for, strongest first."""
    titles: list[str] = []
    for profile in _profiles("industry"):
        titles.extend(str(t).strip().lower() for t in profile.get("target_titles") or []
                      if str(t).strip())
        titles.extend(TARGET_TITLES.get(profile.get("primary_domain"), [])[:3])
    deduped = list(dict.fromkeys(titles))
    return deduped[:MAX_INDUSTRY_QUERIES]


def industry_locations() -> list[str]:
    """Countries users asked for. Empty means worldwide."""
    places: list[str] = []
    for profile in _profiles("industry"):
        places.extend(str(x).strip() for x in profile.get("preferred_locations") or [] if str(x).strip())
    return list(dict.fromkeys(places))


_GENERIC = {"postdoctoral", "assistant", "professor", "lecturer", "research", "fellow",
            "engineering", "management", "science", "sciences", "studies", "systems",
            "learning", "machine", "intelligence", "artificial", "analytics", "health",
            "resources", "project", "digital", "environment", "safety", "design",
            "education", "communication", "quality", "assurance", "data"}


def relevance_terms() -> set[str]:
    """Subject phrases and distinctive words from every user's subjects.

    Used to filter broad all-discipline listings. A multi-word phrase is strong
    evidence on its own; single words only count in groups (see looks_relevant).
    """
    terms: set[str] = set()
    for query in academic_queries():
        low = query.lower()
        for role in ACADEMIC_ROLES:
            low = low.replace(role, "").strip()
        if " " in low:
            terms.add(low)
        for word in low.split():
            if len(word) >= 5 and word not in _GENERIC:
                terms.add(word)
    return terms


def looks_relevant(text: str, terms: set[str]) -> bool:
    """True when a posting names one of the users' subjects.

    One phrase ("water infrastructure") is enough; otherwise at least two
    distinctive words must appear, so a single stray word cannot admit a post.
    """
    low = (text or "").lower()
    singles = 0
    for term in terms:
        if term in low:
            if " " in term:
                return True
            singles += 1
            if singles >= 2:
                return True
    return False

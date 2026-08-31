# -*- coding: utf-8 -*-
"""Match an opportunity against the candidate profile and explain the result."""

from __future__ import annotations

import datetime as dt
import re
from email.utils import parsedate_to_datetime
from typing import Dict, List, Tuple

from . import profile as P

_WORD_CACHE: Dict[str, re.Pattern] = {}


def _word_re(term: str) -> re.Pattern:
    if term not in _WORD_CACHE:
        _WORD_CACHE[term] = re.compile(r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])")
    return _WORD_CACHE[term]


def _contains(haystack: str, term: str) -> bool:
    """Substring match, but whole-word for short/ambiguous terms."""
    if term in P.WORD_BOUNDARY_TERMS or len(term) <= 4:
        return bool(_word_re(term).search(haystack))
    return term in haystack


def _scan(text: str, title: str, tier: Dict[str, float], title_bonus: float
          ) -> Tuple[float, List[Tuple[str, float]]]:
    """Score one tier. Terms found in the title count for more."""
    total = 0.0
    hits: List[Tuple[str, float]] = []
    for term, weight in tier.items():
        if _contains(text, term):
            value = float(weight)
            if _contains(title, term):
                value *= title_bonus
            total += value
            hits.append((term, round(value, 1)))
    return total, hits


def topic_score(title: str, body: str) -> Tuple[float, List[Tuple[str, float]], Dict[str, float]]:
    """Raw topic score plus the terms that produced it."""
    title_l = (title or "").lower()
    text = (title_l + " \n " + (body or "").lower())

    a, a_hits = _scan(text, title_l, P.TIER_A, 1.9)
    b, b_hits = _scan(text, title_l, P.TIER_B, 1.6)
    c, c_hits = _scan(text, title_l, P.TIER_C, 1.4)
    d, d_hits = _scan(text, title_l, P.TIER_D, 1.3)
    bw, bw_hits = _scan(text, title_l, P.TIER_B_WORDS, 1.6)
    b += bw
    b_hits += bw_hits

    # Diminishing returns inside each tier so a keyword-stuffed advert cannot
    # out-score a genuinely on-topic one.
    def damp(x: float, cap: float) -> float:
        return cap * (1.0 - pow(2.718281828, -x / cap)) if x > 0 else 0.0

    raw = damp(a, 26) + damp(b, 16) + damp(c, 7) + damp(d, 4)

    # Methods alone (AI/ML with no civil/water/construction domain) are a weak signal.
    if a == 0 and b == 0:
        raw *= 0.45

    hits = sorted(a_hits + b_hits + c_hits + d_hits, key=lambda h: -h[1])
    parts = {"tier_a": round(a, 1), "tier_b": round(b, 1),
             "tier_c": round(c, 1), "tier_d": round(d, 1)}
    return raw, hits, parts


def role_of(title: str, body: str = "") -> Tuple[str, str, float]:
    """Classify the post type from its title (falling back to the body)."""
    t = (title or "").lower()
    for key, label, patterns, fit in P.ROLE_PATTERNS:
        if any(p in t for p in patterns):
            return key, label, fit
    b = (body or "").lower()[:1200]
    for key, label, patterns, fit in P.ROLE_PATTERNS:
        if any(p in b for p in patterns):
            return key, label, fit
    return P.DEFAULT_ROLE


def contract_modifier(title: str, body: str = "") -> Tuple[float, List[str], List[str]]:
    """
    Adjust role fit for contract quality.

    Returns (factor, warnings, positives) so the UI can show the two kinds of
    note differently - an adjunct contract is a caveat, tenure-track is a draw.
    """
    t = (title or "").lower()
    b = (body or "").lower()[:2500]
    factor = 1.0
    warnings: List[str] = []
    positives: List[str] = []

    for terms, mult, note in P.ROLE_DOWNGRADES:
        if any(term in t for term in terms):
            factor *= mult
            warnings.append(note)
            break
        if any(term in b for term in terms):
            factor *= (mult + 1.0) / 2.0   # softer when only the body says so
            warnings.append(note)
            break

    for terms, mult, note in P.ROLE_UPGRADES:
        if any(term in t for term in terms) or any(term in b for term in terms):
            factor *= mult
            positives.append(note)
            break

    return factor, warnings, positives


def locate(*fields: str) -> Tuple[str, str]:
    """Return (country, tier) where tier is target / secondary / unknown."""
    blob = " ".join(f or "" for f in fields).lower()
    for country, cues in P.TARGET_COUNTRIES.items():
        if any(cue in blob for cue in cues):
            return country, "target"
    for country, cues in P.SECONDARY_COUNTRIES.items():
        if any(cue in blob for cue in cues):
            return country, "secondary"
    return "", "unknown"


def off_field(title: str) -> str:
    t = (title or "").lower()
    for term in P.OFF_FIELD_TITLE_TERMS:
        if term in t:
            return term
    return ""


def _parse_date(value) -> dt.date | None:
    """Accept ISO, RFC-822 (RSS pubDate), and the long formats job boards use."""
    if not value:
        return None
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    s = str(value).strip()

    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        try:
            return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None

    if "," in s[:5] or re.match(r"^[A-Z][a-z]{2},", s):
        try:
            return parsedate_to_datetime(s).date()
        except (TypeError, ValueError):
            pass

    s2 = re.sub(r"\b(\d{1,2})(st|nd|rd|th)\b", r"\1", s)
    s2 = re.split(r"\s+-\s+|\s+at\s+|\s{2,}", s2)[0].strip()
    for fmt in ("%d %B %Y", "%d %b %Y", "%B %d %Y", "%b %d %Y",
                "%d/%m/%Y", "%m/%d/%Y", "%d.%m.%Y", "%Y/%m/%d"):
        try:
            return dt.datetime.strptime(s2, fmt).date()
        except ValueError:
            continue

    m = re.search(r"(\d{1,2})\s+([A-Za-z]{3,9})\s+(\d{4})", s2)
    if m:
        for fmt in ("%d %B %Y", "%d %b %Y"):
            try:
                return dt.datetime.strptime(" ".join(m.groups()), fmt).date()
            except ValueError:
                continue
    return None


def _iso(value) -> str:
    d = _parse_date(value)
    return d.isoformat() if d else ""


def freshness_score(posted, deadline, today: dt.date | None = None
                    ) -> Tuple[float, int | None, int | None]:
    """Fit component for timing, plus days_old and days_left."""
    today = today or dt.date.today()
    p, d = _parse_date(posted), _parse_date(deadline)

    days_old = (today - p).days if p else None
    days_left = (d - today).days if d else None

    s = 0.55  # neutral when nothing is known
    if days_old is not None:
        if days_old <= 2:
            s = 1.00
        elif days_old <= 7:
            s = 0.90
        elif days_old <= 21:
            s = 0.72
        elif days_old <= 45:
            s = 0.55
        else:
            s = 0.35
    if days_left is not None:
        if days_left < 0:
            s = 0.0
        elif days_left <= 3:
            s = min(s, 0.45)      # technically open, but very tight
        elif days_left <= 10:
            s = max(s, 0.80)
        elif days_left <= 60:
            s = max(s, 0.92)
    return s, days_old, days_left


def score_opportunity(item: Dict) -> Dict:
    """
    Score one opportunity dict with keys:
        title, org, location, description, posted, deadline, source, url
    Returns the scoring fields to merge back into the item.
    """
    title = item.get("title", "") or ""
    body = " ".join(str(item.get(k) or "") for k in ("description", "org", "location", "department"))

    curated = bool(item.get("curated"))

    raw_topic, hits, tier_parts = topic_score(title, body)
    topic_fit = min(1.0, raw_topic / P.TOPIC_SATURATION)

    role_key, role_label, role_fit = role_of(title, body)
    contract_factor, contract_warnings, positives = contract_modifier(title, body)
    role_fit = min(1.0, role_fit * contract_factor)

    if curated:
        # These schemes were put on the register precisely because he is
        # eligible and they fund his kind of work. Most are open to all
        # disciplines, so their text carries no subject keywords and the topic
        # scanner would bury them. Judge them on eligibility, not wording.
        topic_fit = max(topic_fit, P.CURATED_TOPIC_FLOOR)
        if role_key in ("other", "phd", "assistant"):
            role_key, role_label, role_fit = "fellowship", "Fellowship", 0.95
    country, country_tier = locate(item.get("location"), item.get("org"), title, body[:400])
    country_fit = P.COUNTRY_FIT[country_tier]
    fresh_fit, days_old, days_left = freshness_score(item.get("posted"), item.get("deadline"))

    w = P.WEIGHTS
    base = (w["topic"] * topic_fit + w["role"] * role_fit +
            w["country"] * country_fit + w["freshness"] * fresh_fit)

    flags: List[str] = list(item.get("extra_flags") or []) + list(contract_warnings)

    # Hard suppressors -------------------------------------------------------
    bad = off_field(title)
    if bad:
        base *= 0.22
        flags.append("different discipline (%s)" % bad)

    if raw_topic < P.PLAUSIBILITY_FLOOR and not curated:
        base *= 0.45
        flags.append("weak subject overlap")

    if role_key == "phd":
        flags.append("PhD-level post - below your stage")
    if role_key == "chair":
        flags.append("senior chair - likely above your current stage")
    if country_tier == "secondary":
        flags.append("outside your target regions (%s)" % country)
    if days_left is not None and days_left < 0:
        flags.append("deadline passed")
    elif days_left is not None and days_left <= 5:
        flags.append("closes in %d day%s" % (days_left, "" if days_left == 1 else "s"))

    score = int(round(max(0.0, min(1.0, base)) * 100))

    return {
        "score": score,
        "role_key": role_key,
        "role_label": role_label,
        "country": country,
        "country_tier": country_tier,
        "days_old": days_old,
        "days_left": days_left,
        "matched_terms": [h[0] for h in hits[:14]],
        "flags": flags,
        "positives": positives,
        "posted": _iso(item.get("posted")) or item.get("posted") or "",
        "deadline": _iso(item.get("deadline")) or item.get("deadline") or "",
        "breakdown": {
            "topic": round(topic_fit * 100),
            "role": round(role_fit * 100),
            "country": round(country_fit * 100),
            "timing": round(fresh_fit * 100),
            "raw_topic": round(raw_topic, 1),
            "tiers": tier_parts,
        },
    }

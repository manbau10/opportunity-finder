# -*- coding: utf-8 -*-
"""
AcademicJobsOnline (academicjobsonline.org) - the main US/Canada academic job
register for mathematics, the sciences, engineering and the social sciences.

The site publishes one RSS feed of every open post. It carries structured
fields (university, city, state, country, deadline), so no detail page is
needed. The feed spans every discipline, so it is filtered to the subjects of
the registered users.
"""

from __future__ import annotations

import feedparser

from ..queries import looks_relevant, relevance_terms
from .base import clean, get, make_id

NAME = "AcademicJobsOnline"
FEED = "https://academicjobsonline.org/ajo?joblist-0-0-0-----rss--"


def parse(content: bytes, terms: set[str]) -> list[dict]:
    items = []
    for entry in feedparser.parse(content).entries:
        link = (entry.get("link") or "").replace("?rss", "")
        title = clean(entry.get("title"))
        if not link or not title:
            continue
        summary = clean(entry.get("summary"))
        field = clean(entry.get("ads_disciplines"))
        if not looks_relevant(f"{title} {summary} {field}", terms):
            continue
        place = ", ".join(x for x in (clean(entry.get("ads_city")), clean(entry.get("ads_state")),
                                      clean(entry.get("ads_country"))) if x)
        posted = (entry.get("updated") or "")[:10]
        items.append({
            "id": make_id("ajo", link),
            "source": NAME,
            "source_key": "ajo",
            "title": title,
            "org": clean(entry.get("ads_univ")),
            "department": clean(entry.get("ads_dept")),
            "location": place,
            "url": link,
            "description": f"{summary} Discipline: {field}".strip(),
            "posted": posted,
            "deadline": "",
            "query": "register",
            "needs_detail": False,
            "country_hint": "Canada" if clean(entry.get("ads_country")) == "CA" else "United States",
        })
    return items


def fetch(log=print) -> list[dict]:
    r = get(FEED, timeout=60)
    if r is None:
        log("  AcademicJobsOnline: no response")
        return []
    items = parse(r.content, relevance_terms())
    log("  AcademicJobsOnline: %d relevant postings" % len(items))
    return items

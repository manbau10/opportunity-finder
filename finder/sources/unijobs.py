# -*- coding: utf-8 -*-
"""
Times Higher Education unijobs (timeshighereducation.com/unijobs).

Global coverage with a strong UK / Australia / New Zealand bias. Exposes a
keyword RSS feed that returns the 20 newest matches per query, so we run one
request per search phrase.
"""

from __future__ import annotations

import urllib.parse

import feedparser

from ..config import SEARCH_QUERIES
from .base import clean, get, make_id

NAME = "THE unijobs"
FEED = "https://www.timeshighereducation.com/unijobs/jobsrss/?keywords="


def fetch(log=print) -> list[dict]:
    out: dict[str, dict] = {}
    for query in SEARCH_QUERIES:
        r = get(FEED + urllib.parse.quote_plus(query))
        if r is None:
            log("  unijobs: no response for %r" % query)
            continue
        feed = feedparser.parse(r.content)
        for e in feed.entries:
            link = e.get("link", "")
            if not link:
                continue
            raw_title = clean(e.get("title", ""))
            # Feed titles look like "UNIVERSITY OF X: Lecturer in Y"
            org, _, title = raw_title.partition(":")
            if not title:
                org, title = "", raw_title
            summary = clean(e.get("summary", ""))
            # The summary ends with the location on its own line.
            location = ""
            lines = [l.strip() for l in clean(e.get("summary", "")).split("  ") if l.strip()]
            parts = [p.strip() for p in (e.get("summary", "") or "").split("\n") if p.strip()]
            if parts:
                location = clean(parts[-1])[:120]
            key = make_id("unijobs", link)
            out[key] = {
                "id": key,
                "source": NAME,
                "source_key": "unijobs",
                "title": title.strip() or raw_title,
                "org": org.strip().title(),
                "location": location,
                "url": link,
                "description": summary,
                "posted": e.get("published", ""),
                "deadline": "",
                "query": query,
            }
        log("  unijobs: %-38s %3d entries" % (query, len(feed.entries)))
    return list(out.values())

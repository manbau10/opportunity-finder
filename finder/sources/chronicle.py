# -*- coding: utf-8 -*-
"""
The Chronicle of Higher Education job board (jobs.chronicle.com).

Best single source for United States and Canadian faculty and postdoc posts.
Keyword RSS returns the 20 newest matches per query.
"""

from __future__ import annotations

import urllib.parse

import feedparser

from ..config import SEARCH_QUERIES
from .base import clean, get, make_id

NAME = "Chronicle of Higher Ed"
FEED = "https://jobs.chronicle.com/jobsrss/?keywords="

# The Chronicle indexes US titles, so a couple of US-specific phrasings help.
EXTRA_QUERIES = [
    "assistant professor construction",
    "postdoctoral water",
    "civil and environmental engineering",
    "construction science",
    "engineering technology construction",
]


def fetch(log=print) -> list[dict]:
    out: dict[str, dict] = {}
    for query in SEARCH_QUERIES + EXTRA_QUERIES:
        r = get(FEED + urllib.parse.quote_plus(query))
        if r is None:
            log("  chronicle: no response for %r" % query)
            continue
        feed = feedparser.parse(r.content)
        for e in feed.entries:
            link = e.get("link", "")
            if not link:
                continue
            raw_title = clean(e.get("title", ""))
            org, _, title = raw_title.partition(":")
            if not title:
                org, title = "", raw_title
            summary_raw = e.get("summary", "") or ""
            parts = [clean(p) for p in summary_raw.split("\n") if clean(p)]
            location = parts[-1][:120] if parts else ""
            key = make_id("chronicle", link)
            out[key] = {
                "id": key,
                "source": NAME,
                "source_key": "chronicle",
                "title": title.strip() or raw_title,
                "org": org.strip(),
                "location": location,
                "url": link,
                "description": clean(summary_raw),
                "posted": e.get("published", ""),
                "deadline": "",
                "query": query,
            }
        log("  chronicle: %-36s %3d entries" % (query, len(feed.entries)))
    return list(out.values())

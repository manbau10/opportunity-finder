# -*- coding: utf-8 -*-
"""
Madgex job boards.

Times Higher Education unijobs, the Chronicle of Higher Education, Inside Higher
Ed Careers and AAAS Science Careers all run on the same platform and expose the
same keyword RSS feed (`/jobsrss/?keywords=`), which returns the newest matches
for one search phrase. One parser serves all of them.
"""

from __future__ import annotations

import urllib.parse
from concurrent.futures import ThreadPoolExecutor

import feedparser

from .base import clean, get, make_id


def _location_of(summary_raw: str) -> str:
    parts = [clean(p) for p in (summary_raw or "").split("\n") if clean(p)]
    return parts[-1][:120] if parts else ""


def parse_feed(content: bytes, source: str, key: str, query: str,
               country_hint: str = "") -> list[dict]:
    items = []
    for entry in feedparser.parse(content).entries:
        link = entry.get("link", "")
        if not link:
            continue
        # Drop tracking parameters so the same advert keeps one identity.
        link = link.split("?TrackID", 1)[0].split("&TrackID", 1)[0]
        raw_title = clean(entry.get("title", ""))
        org, _, title = raw_title.partition(":")
        if not title:
            org, title = "", raw_title
        summary_raw = entry.get("summary", "") or ""
        item = {
            "id": make_id(key, link),
            "source": source,
            "source_key": key,
            "title": title.strip() or raw_title,
            "org": org.strip().title() if org.isupper() else org.strip(),
            "location": _location_of(summary_raw),
            "url": link,
            "description": clean(summary_raw),
            "posted": entry.get("published", ""),
            "deadline": "",
            "query": query,
        }
        if country_hint:
            item["country_hint"] = country_hint
        items.append(item)
    return items


def fetch_board(feed_url: str, source: str, key: str, queries: list[str],
                log=print, country_hint: str = "", workers: int = 1) -> list[dict]:
    """Run every query against one board's RSS feed."""
    out: dict[str, dict] = {}

    def one(query: str):
        r = get(feed_url + urllib.parse.quote_plus(query))
        if r is None:
            return query, None
        return query, parse_feed(r.content, source, key, query, country_hint)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(one, queries))
    failures = 0
    for query, items in results:
        if items is None:
            failures += 1
            continue
        for item in items:
            out.setdefault(item["id"], item)
    log("  %s: %d queries, %d postings%s" % (
        source, len(queries), len(out),
        (", %d queries got no response" % failures) if failures else ""))
    return list(out.values())

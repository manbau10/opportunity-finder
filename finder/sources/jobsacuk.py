# -*- coding: utf-8 -*-
"""
jobs.ac.uk - the main UK academic board, with some European and global posts.

No usable feed, so we read the search results pages. Detail pages carry a
schema.org JobPosting block, which is where the closing date comes from; that
enrichment happens later in the pipeline.
"""

from __future__ import annotations

import urllib.parse
from concurrent.futures import ThreadPoolExecutor

from bs4 import BeautifulSoup

from ..config import LIMITS
from .. import queries
from .base import clean, get, make_id

NAME = "jobs.ac.uk"
ROOT = "https://www.jobs.ac.uk"
SEARCH = ROOT + "/search/?keywords={kw}&page={page}"


def _field(card, css: str) -> str:
    el = card.select_one(css)
    return clean(el.get_text(" ", strip=True)) if el else ""


def _labelled(card, label: str) -> str:
    """Pull 'Location: Nottingham' style rows out of a result card."""
    for div in card.find_all("div"):
        text = clean(div.get_text(" ", strip=True))
        if text.lower().startswith(label.lower()):
            return text[len(label):].lstrip(": ").strip()
    return ""


def _search(query: str, pages: int) -> tuple[list[dict], int]:
    found: list[dict] = []
    failed = 0
    for page in range(1, pages + 1):
        url = SEARCH.format(kw=urllib.parse.quote_plus(query), page=page)
        r = get(url)
        if r is None:
            failed += 1
            break
        soup = BeautifulSoup(r.text, "html.parser")
        cards = soup.select("div.j-search-result__text")
        if not cards:
            break
        for card in cards:
            a = card.find("a", href=True)
            if not a:
                continue
            link = urllib.parse.urljoin(ROOT, a["href"])
            found.append({
                "id": make_id("jobsacuk", link),
                "source": NAME,
                "source_key": "jobsacuk",
                "title": clean(a.get_text(" ", strip=True)),
                "org": _field(card, ".j-search-result__employer"),
                "department": _field(card, ".j-search-result__department"),
                "location": _labelled(card, "Location"),
                "url": link,
                "description": clean(card.get_text(" ", strip=True)),
                "posted": "",
                "deadline": "",
                "query": query,
                "needs_detail": True,
            })
        if len(cards) < 20:
            break
    return found, failed


def fetch(log=print) -> list[dict]:
    phrases = queries.academic_queries()
    out: dict[str, dict] = {}
    failures = 0
    with ThreadPoolExecutor(max_workers=3) as pool:
        for found, failed in pool.map(lambda q: _search(q, LIMITS["jobs_ac_uk_pages"]), phrases):
            failures += failed
            for item in found:
                out.setdefault(item["id"], item)
    log("  jobs.ac.uk: %d queries, %d postings%s" % (
        len(phrases), len(out),
        (", %d pages got no response" % failures) if failures else ""))
    return list(out.values())

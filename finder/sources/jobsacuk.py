# -*- coding: utf-8 -*-
"""
jobs.ac.uk - the main UK academic board, with some European and global posts.

No usable feed, so we read the search results pages. Detail pages carry a
schema.org JobPosting block, which is where the closing date comes from; that
enrichment happens later in the pipeline.
"""

from __future__ import annotations

import urllib.parse

from bs4 import BeautifulSoup

from ..config import LIMITS, SEARCH_QUERIES
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


def fetch(log=print) -> list[dict]:
    out: dict[str, dict] = {}
    for query in SEARCH_QUERIES:
        for page in range(1, LIMITS["jobs_ac_uk_pages"] + 1):
            url = SEARCH.format(kw=urllib.parse.quote_plus(query), page=page)
            r = get(url)
            if r is None:
                log("  jobs.ac.uk: no response for %r p%d" % (query, page))
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
                key = make_id("jobsacuk", link)
                if key in out:
                    continue
                out[key] = {
                    "id": key,
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
                }
            log("  jobs.ac.uk: %-33s p%d %3d results" % (query, page, len(cards)))
            if len(cards) < 20:
                break
    return list(out.values())

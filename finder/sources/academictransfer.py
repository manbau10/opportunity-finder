# -*- coding: utf-8 -*-
"""
AcademicTransfer (academictransfer.com) - the Dutch academic job board,
English-language posts from all Dutch universities and research institutes.

Server-rendered search pages, ten results per page.
"""

from __future__ import annotations

import re
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

from bs4 import BeautifulSoup

from .. import queries
from .base import clean, get, make_id

NAME = "AcademicTransfer"
ROOT = "https://www.academictransfer.com"
SEARCH = ROOT + "/en/jobs/?q={q}"
_JOB = re.compile(r"^/en/jobs/\d+/")
_DEADLINE = re.compile(r"Deadline\s*\|?\s*(\d{1,2}\s+[A-Za-z]{3,9}\s+['’]?\d{2,4})")


def parse(html: str, query: str = "") -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    items = []
    for article in soup.select("article"):
        anchor = article.find("a", href=_JOB)
        title_el = article.find(["h3", "h2"])
        if not anchor or not title_el:
            continue
        link = urllib.parse.urljoin(ROOT, anchor["href"])
        body = article.find("p")
        segments = [clean(s) for s in article.get_text("|", strip=True).split("|") if clean(s)]
        org = location = ""
        if "Published" in segments:
            tail = segments[segments.index("Published") + 2:]   # skip the date itself
            location = tail[0] if tail else ""
            org = tail[1] if len(tail) > 1 else ""
        items.append({
            "id": make_id("academictransfer", link),
            "source": NAME,
            "source_key": "academictransfer",
            "title": clean(title_el.get_text(" ", strip=True)),
            "org": org,
            "location": (location + ", Netherlands").strip(", "),
            "url": link,
            "description": clean(body.get_text(" ", strip=True)) if body else "",
            "posted": "",
            "deadline": "",
            "query": query,
            "needs_detail": True,
            "country_hint": "Netherlands",
        })
    return items


def _search(query: str) -> list[dict]:
    r = get(SEARCH.format(q=urllib.parse.quote_plus(query)))
    return parse(r.text, query) if r is not None else []


def fetch(log=print) -> list[dict]:
    phrases = queries.academic_queries()
    out: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=3) as pool:
        for found in pool.map(_search, phrases):
            for item in found:
                out.setdefault(item["id"], item)
    log("  AcademicTransfer: %d queries, %d postings" % (len(phrases), len(out)))
    return list(out.values())

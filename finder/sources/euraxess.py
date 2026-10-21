# -*- coding: utf-8 -*-
"""
EURAXESS (euraxess.ec.europa.eu) - the European Commission research job portal.

Its keyword box does not filter server-side, but the newest-first listing pages
can be walked over plain HTTP (`?page=N`, ten postings per page). Several
pages are read in parallel and filtered locally against the subjects of the
registered users.
"""

from __future__ import annotations

import re
import urllib.parse

from bs4 import BeautifulSoup

from concurrent.futures import ThreadPoolExecutor

from ..config import LIMITS
from ..queries import looks_relevant, relevance_terms
from .base import clean, get, make_id

NAME = "EURAXESS"
ROOT = "https://euraxess.ec.europa.eu"
LIST = ROOT + "/jobs/search?page={page}"

_JOB_HREF = re.compile(r"^/jobs/\d{4,}$")
_POSTED = re.compile(r"Posted on:\s*([0-9]{1,2} [A-Za-z]+ [0-9]{4})")


def _card_of(anchor):
    """The largest ancestor that still holds only this posting's link: its whole card."""
    node, card = anchor, None
    for _ in range(7):
        parent = node.parent
        if parent is None:
            break
        if len({x["href"] for x in parent.find_all("a", href=_JOB_HREF)}) > 1:
            break
        node = card = parent
    return card


def parse(html: str, terms: set[str]) -> tuple[list[dict], int]:
    """Return (relevant postings, postings seen) for one listing page."""
    soup = BeautifulSoup(html, "html.parser")
    anchors = [a for a in soup.find_all("a", href=True) if _JOB_HREF.match(a["href"])]
    seen_here, out = set(), []
    for a in anchors:
        href = a["href"]
        if href in seen_here:
            continue
        seen_here.add(href)
        title = clean(a.get_text(" ", strip=True))
        if not title:
            continue
        card = _card_of(a)
        card_text = clean(card.get_text(" | ", strip=True)) if card else title
        if not looks_relevant(card_text, terms):
            continue
        pieces = [p.strip() for p in card_text.split("|") if p.strip()]
        org, posted = "", ""
        for index, piece in enumerate(pieces):
            m = _POSTED.search(piece)
            if m:
                posted = m.group(1)
                org = pieces[index - 1][:160] if index else ""
                break
        if not org and pieces:
            org = pieces[0][:160] if len(pieces[0]) < 120 else ""
        link = urllib.parse.urljoin(ROOT, href)
        out.append({
            "id": make_id("euraxess", link),
            "source": NAME,
            "source_key": "euraxess",
            "title": title,
            "org": org,
            "location": "",
            "url": link,
            "description": card_text[:2500],
            "posted": posted,
            "deadline": "",
            "query": "listing crawl",
            "needs_detail": True,
        })
    return out, len(seen_here)


def fetch(log=print) -> list[dict]:
    terms = relevance_terms()
    pages = list(range(LIMITS["euraxess_pages"]))

    def one(page: int):
        r = get(LIST.format(page=page))
        return (page, parse(r.text, terms)) if r is not None else (page, None)

    out: dict[str, dict] = {}
    seen = failed = 0
    with ThreadPoolExecutor(max_workers=4) as pool:
        for page, result in pool.map(one, pages):
            if result is None:
                failed += 1
                continue
            items, count = result
            seen += count
            for item in items:
                out.setdefault(item["id"], item)
    log("  EURAXESS: %d pages, %d postings read, %d relevant%s" % (
        len(pages), seen, len(out), (", %d pages failed" % failed) if failed else ""))
    return list(out.values())

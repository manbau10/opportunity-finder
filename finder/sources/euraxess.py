# -*- coding: utf-8 -*-
"""
EURAXESS (euraxess.ec.europa.eu) - the European Commission research job portal.

Its keyword search is a JavaScript form we cannot drive with plain HTTP, so we
walk the newest-first listing pages instead and filter locally against
CRAWL_KEEP_TERMS. Ten postings per page.
"""

from __future__ import annotations

import re
import urllib.parse

from bs4 import BeautifulSoup

from ..config import CRAWL_KEEP_TERMS, LIMITS
from .base import clean, get, make_id

NAME = "EURAXESS"
ROOT = "https://euraxess.ec.europa.eu"
LIST = ROOT + "/jobs/search?page={page}"

_JOB_HREF = re.compile(r"^/jobs/\d{4,}$")
_POSTED = re.compile(r"Posted on:\s*([0-9]{1,2} [A-Za-z]+ [0-9]{4})")


def _relevant(text: str) -> bool:
    low = text.lower()
    return any(term in low for term in CRAWL_KEEP_TERMS)


def _card_of(anchor):
    """Climb to the smallest ancestor that holds the whole posting summary."""
    node = anchor
    for _ in range(6):
        node = node.parent
        if node is None:
            return None
        if len(node.get_text(strip=True)) > 200:
            return node
    return None


def fetch(log=print) -> list[dict]:
    out: dict[str, dict] = {}
    empty_pages = 0
    for page in range(0, LIMITS["euraxess_pages"]):
        r = get(LIST.format(page=page))
        if r is None:
            log("  euraxess: no response for page %d" % page)
            break
        soup = BeautifulSoup(r.text, "html.parser")
        anchors = [a for a in soup.find_all("a", href=True) if _JOB_HREF.match(a["href"])]
        seen_here, kept_here = set(), 0
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
            if not _relevant(card_text):
                continue
            pieces = [p.strip() for p in card_text.split("|") if p.strip()]
            org = pieces[0][:160] if pieces else ""
            posted = ""
            m = _POSTED.search(card_text)
            if m:
                posted = m.group(1)
                org = card_text[:m.start()].strip(" |")[:160]
            link = urllib.parse.urljoin(ROOT, href)
            key = make_id("euraxess", link)
            out[key] = {
                "id": key,
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
            }
            kept_here += 1
        log("  euraxess: page %-2d %2d postings, %2d relevant" % (page, len(seen_here), kept_here))
        if not seen_here:
            empty_pages += 1
            if empty_pages >= 2:
                break
    return list(out.values())

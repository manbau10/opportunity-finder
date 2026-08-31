# -*- coding: utf-8 -*-
"""
Detail-page enrichment.

Listing pages rarely carry a closing date, so for the postings that actually
matter (score above a threshold) we open the advert itself and pull the
deadline, country and full description. Two shapes cover every source we use:

* schema.org JobPosting JSON-LD - jobs.ac.uk, THE unijobs, Chronicle
* EURAXESS's "Application Deadline ..." label
"""

from __future__ import annotations

import json
import re

from bs4 import BeautifulSoup

from .sources.base import clean, get

_LD = re.compile(r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>', re.S)
_EURAXESS_DEADLINE = re.compile(
    r"(?:Application\s+)?Deadline\s+(\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4})", re.I)
_EURAXESS_COUNTRY = re.compile(r"Country\s+([A-Z][A-Za-z .'-]{2,40})")
_TEXT_DEADLINE = re.compile(
    r"(?:Closing date|Closes|Closing Date|Application deadline|Apply by|Deadline)\s*[:\-]?\s*"
    r"(\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]{3,9}\s+\d{4}|\d{4}-\d{2}-\d{2})", re.I)

_COUNTRY_CODES = {
    "GB": "United Kingdom", "US": "United States", "CA": "Canada",
    "AU": "Australia", "NZ": "New Zealand", "IE": "Ireland", "DE": "Germany",
    "NL": "Netherlands", "CH": "Switzerland", "SE": "Sweden", "NO": "Norway",
    "DK": "Denmark", "FI": "Finland", "BE": "Belgium", "AT": "Austria",
    "FR": "France", "ES": "Spain", "IT": "Italy", "PT": "Portugal",
    "PL": "Poland", "CZ": "Czechia", "GR": "Greece", "LU": "Luxembourg",
    "IS": "Iceland", "EE": "Estonia", "SI": "Slovenia", "RO": "Romania",
    "HU": "Hungary", "CY": "Cyprus", "MT": "Malta", "AE": "UAE",
    "SA": "Saudi Arabia", "QA": "Qatar", "SG": "Singapore", "HK": "Hong Kong",
    "CN": "China", "JP": "Japan", "KR": "South Korea", "IL": "Israel",
    "ZA": "South Africa",
}


def _iter_ld(html: str):
    for blob in _LD.findall(html):
        try:
            data = json.loads(blob)
        except (ValueError, TypeError):
            continue
        items = data if isinstance(data, list) else [data]
        for item in items:
            if isinstance(item, dict) and "JobPosting" in str(item.get("@type", "")):
                yield item


def _location_from_ld(posting: dict) -> str:
    loc = posting.get("jobLocation")
    if isinstance(loc, list):
        loc = loc[0] if loc else None
    if not isinstance(loc, dict):
        return ""
    addr = loc.get("address")
    if not isinstance(addr, dict):
        return clean(str(loc.get("name", "")))
    bits = [addr.get("addressLocality"), addr.get("addressRegion")]
    country = addr.get("addressCountry")
    if isinstance(country, dict):
        country = country.get("name")
    if isinstance(country, str):
        bits.append(_COUNTRY_CODES.get(country.upper(), country))
    return ", ".join(clean(b) for b in bits if b)


def enrich(item: dict) -> bool:
    """Fill deadline / posted / location / description in place. True if changed."""
    r = get(item["url"])
    if r is None:
        return False
    html = r.text
    changed = False

    for posting in _iter_ld(html):
        valid = posting.get("validThrough")
        if valid and not item.get("deadline"):
            item["deadline"] = str(valid)[:10]
            changed = True
        posted = posting.get("datePosted")
        if posted and not item.get("posted"):
            item["posted"] = str(posted)[:10]
            changed = True
        loc = _location_from_ld(posting)
        if loc and len(loc) > len(item.get("location") or ""):
            item["location"] = loc
            changed = True
        desc = clean(posting.get("description"))
        if len(desc) > len(item.get("description") or ""):
            item["description"] = desc[:6000]
            changed = True
        break

    text = clean(BeautifulSoup(html, "html.parser").get_text(" ", strip=True))

    if not item.get("deadline"):
        m = _EURAXESS_DEADLINE.search(text) or _TEXT_DEADLINE.search(text)
        if m:
            item["deadline"] = re.sub(r"(st|nd|rd|th)\b", "", m.group(1)).strip()
            changed = True

    if not item.get("location"):
        m = _EURAXESS_COUNTRY.search(text)
        if m:
            item["location"] = m.group(1).strip()
            changed = True

    if len(text) > len(item.get("description") or ""):
        item["description"] = text[:6000]
        changed = True

    item["enriched"] = 1
    return changed

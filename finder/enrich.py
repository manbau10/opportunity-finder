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

import datetime as dt
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
    r"(\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]{3,9}\s+\d{4}|"
    r"[A-Za-z]{3,9}\s+\d{1,2}(?:st|nd|rd|th)?[,]?\s+\d{4}|\d{4}-\d{2}-\d{2})", re.I)
_APPLICATION_UNTIL = re.compile(
    r"(?:review\s+of\s+)?applications?[^.]{0,220}?"
    r"(?:continue(?:d)?|accepted|remain\s+open|open)[^.]{0,80}?until\s+"
    r"(\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]{3,9}\s+\d{4}|"
    r"[A-Za-z]{3,9}\s+\d{1,2}(?:st|nd|rd|th)?[,]?\s+\d{4}|\d{4}-\d{2}-\d{2})", re.I)

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


def _normalise_deadline(value: str) -> str:
    value = re.sub(r"\b(\d{1,2})(st|nd|rd|th)\b", r"\1", value.strip(), flags=re.I)
    value = value.replace(",", "")
    for fmt in ("%Y-%m-%d", "%d %B %Y", "%d %b %Y", "%B %d %Y", "%b %d %Y"):
        try:
            return dt.datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue
    return ""


def explicit_deadline(text: str) -> str:
    """Return the earliest deadline explicitly stated in application context."""
    dates = []
    for pattern in (_EURAXESS_DEADLINE, _TEXT_DEADLINE, _APPLICATION_UNTIL):
        for match in pattern.finditer(text or ""):
            value = _normalise_deadline(match.group(1))
            if value:
                dates.append(value)
    return min(dates) if dates else ""


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
            item["description"] = desc
            changed = True
        break

    text = clean(BeautifulSoup(html, "html.parser").get_text(" ", strip=True))

    stated_deadline = explicit_deadline(text)
    if stated_deadline and stated_deadline != item.get("deadline"):
        # An explicit date inside the advert is more authoritative than an
        # aggregator's JSON-LD validThrough value.
        item["deadline"] = stated_deadline
        changed = True

    if not item.get("location"):
        m = _EURAXESS_COUNTRY.search(text)
        if m:
            item["location"] = m.group(1).strip()
            changed = True

    if len(text) > len(item.get("description") or ""):
        item["description"] = text
        changed = True

    item["enriched"] = 1
    return changed

"""Key-free industry job sources used by the shared opportunity catalogue."""

from __future__ import annotations

import datetime as dt
import hashlib
import re
from html import unescape

import requests
from bs4 import BeautifulSoup

from .config import REQUEST_TIMEOUT, USER_AGENT
from .scoring import freshness_score, locate

QUERIES = (
    "construction manager", "civil engineer", "infrastructure manager",
    "project manager construction", "water engineer", "asset manager infrastructure",
)
KEEP = ("construction", "civil", "infrastructure", "project manager", "water",
        "engineering", "built environment", "asset management", "programme manager")


def _id(source: str, url: str, title: str) -> str:
    return hashlib.sha1(f"{source}|{url}|{title}".encode("utf-8")).hexdigest()[:20]


def _text(value: str) -> str:
    return BeautifulSoup(unescape(value or ""), "html.parser").get_text(" ", strip=True)


def _item(source: str, key: str, title: str, org: str, location: str, url: str,
          description: str, posted: str = "", query: str = "") -> dict:
    country, tier = locate(location, org, title, description[:500])
    timing, _, days_left = freshness_score(posted, "")
    return {
        "id": _id(key, url, title), "source": source, "source_key": key,
        "title": title, "org": org, "department": "", "location": location,
        "country": country, "country_tier": tier, "url": url,
        "description": description[:12000], "posted": posted, "deadline": "",
        "days_left": days_left, "role_key": "industry", "role_label": "Industry role",
        "score": round(35 + timing * 15), "matched_terms": [], "flags": [],
        "positives": [], "breakdown": {}, "query": query, "enriched": 1,
        "career_track": "industry", "status": "new",
    }


def fetch(log=print) -> list[dict]:
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    found: dict[str, dict] = {}
    for query in QUERIES:
        try:
            response = requests.get("https://remotive.com/api/remote-jobs",
                                    params={"search": query, "limit": 100},
                                    headers=headers, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            rows = response.json().get("jobs", [])
            for row in rows:
                item = _item("Remotive", "remotive", row.get("title", ""),
                    row.get("company_name", ""), row.get("candidate_required_location", "Remote"),
                    row.get("url", ""), _text(row.get("description", "")),
                    (row.get("publication_date") or "")[:10], query)
                found[item["id"]] = item
            log(f"  remotive: {query:<32} {len(rows):3d} results")
        except Exception as exc:
            log(f"  !! Remotive query failed: {exc}")

    try:
        response = requests.get("https://www.arbeitnow.com/api/job-board-api",
                                headers=headers, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        rows = response.json().get("data", [])
        kept = 0
        for row in rows:
            title = row.get("title", "")
            desc = _text(row.get("description", ""))
            blob = f"{title} {desc}".lower()
            if not any(term in blob for term in KEEP):
                continue
            stamp = row.get("created_at")
            posted = (dt.datetime.fromtimestamp(stamp, dt.timezone.utc).date().isoformat()
                      if isinstance(stamp, (int, float)) else str(stamp or "")[:10])
            item = _item("Arbeitnow", "arbeitnow", title, row.get("company_name", ""),
                         row.get("location", ""), row.get("url", ""), desc, posted, "broad crawl")
            found[item["id"]] = item
            kept += 1
        log(f"  arbeitnow: {kept} relevant jobs")
    except Exception as exc:
        log(f"  !! Arbeitnow failed: {exc}")
    return list(found.values())


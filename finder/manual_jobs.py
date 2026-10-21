# -*- coding: utf-8 -*-
"""Add a job from any website, privately, for one user.

No aggregator can legally or technically cover every board: some (HigherEdJobs,
Indeed, LinkedIn and others) refuse automated readers. This lets a person paste the
link of any advert they found themselves. The page is read once if the site allows it;
if it does not, they paste the advert text. The job is visible only to the person who
added it, and goes through the same matching and application workspace as any other.
"""

from __future__ import annotations

import hashlib
import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from . import store
from .enrich import _iter_ld, _advert_body, explicit_deadline
from .research import _public_url
from .scoring import freshness_score, locate, _iso
from .sources.base import clean, get

MIN_TEXT = 200


def _meta(soup: BeautifulSoup, prop: str) -> str:
    tag = soup.find("meta", attrs={"property": prop}) or soup.find("meta", attrs={"name": prop})
    return clean(tag.get("content")) if tag and tag.get("content") else ""


def prefill(url: str) -> dict:
    """Best-effort title, employer, deadline and text from the advert page. {} if blocked."""
    if not _public_url(url):
        return {}
    response = get(url, retries=0)
    if response is None:
        return {}
    html = response.text
    if "_Incapsula_Resource" in html[:2000] or "Just a moment" in html[:3000]:
        return {}                                   # bot protection: respect it, do not try to pass
    soup = BeautifulSoup(html, "html.parser")
    found = {"title": "", "org": "", "location": "", "deadline": "", "description": ""}
    for posting in _iter_ld(html):
        found["title"] = clean(posting.get("title"))
        org = posting.get("hiringOrganization")
        found["org"] = clean(org.get("name") if isinstance(org, dict) else org)
        found["deadline"] = str(posting.get("validThrough") or "")[:10]
        found["description"] = clean(posting.get("description"))
        break
    found["title"] = found["title"] or _meta(soup, "og:title") or clean(soup.title.string if soup.title else "")
    found["org"] = found["org"] or _meta(soup, "og:site_name")
    body = _advert_body(soup)
    if len(body) > len(found["description"]):
        found["description"] = body
    found["deadline"] = found["deadline"] or explicit_deadline(body)
    return {k: v for k, v in found.items() if v}


def add_job(user_id: str, track: str, data: dict) -> dict:
    """Validate, enrich and store one private job. Returns the stored job's summary."""
    url = (data.get("url") or "").strip()
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc or len(url) > 2000:
        raise ValueError("Enter the full web address of the advert, starting with https://")
    if track not in ("academic", "industry"):
        raise ValueError("Choose Academic or Industry.")
    guess = prefill(url) if not (data.get("title") and data.get("description")) else {}
    pick = lambda key: clean(data.get(key)) or guess.get(key, "")
    title, org = pick("title")[:300], pick("org")[:200]
    description = (clean(data.get("description")) or guess.get("description", ""))[:12000]
    if not title:
        raise ValueError("Enter the job title. The site would not let us read it automatically.")
    if len(description) < MIN_TEXT:
        raise ValueError("That site did not let us read the advert. Paste the advert text "
                         f"(at least {MIN_TEXT} characters) so it can be matched to your CV.")
    location = pick("location")[:200]
    deadline = _iso(pick("deadline")) or explicit_deadline(description)
    country, tier = locate(location, org, title, description[:400])
    _timing, _old, days_left = freshness_score("", deadline)
    job_id = hashlib.sha1(f"manual|{user_id}|{url}".encode()).hexdigest()[:20]
    item = {
        "id": job_id, "source": "Added by you", "source_key": "manual", "title": title, "org": org,
        "department": "", "location": location, "country": country, "country_tier": tier,
        "url": url, "description": description, "posted": "", "deadline": deadline,
        "days_left": days_left, "role_key": "industry" if track == "industry" else "other",
        "role_label": "Added by you", "score": 0, "matched_terms": [], "flags": [], "positives": [],
        "breakdown": {}, "query": "added manually", "enriched": 1, "career_track": track,
        "status": "new",
    }
    conn = store.connect()
    try:
        store.upsert_many(conn, [item])
        conn.execute("UPDATE opportunities SET owner_user_id=? WHERE id=?", (user_id, job_id))
        conn.commit()
    finally:
        conn.close()
    return {"id": job_id, "title": title, "org": org, "deadline": deadline}

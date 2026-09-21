"""Key-free industry job sources used by the shared opportunity catalogue."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from html import unescape
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

import requests
from bs4 import BeautifulSoup

from .config import REQUEST_TIMEOUT, USER_AGENT
from . import store
from .providers import get_config
from .research import _search
from .scoring import freshness_score, locate

WEB_JOB_HOSTS = (
    "jobs.lever.co", "boards.greenhouse.io", "job-boards.greenhouse.io",
    "jobs.ashbyhq.com", "apply.workable.com", "jobs.smartrecruiters.com",
    "myworkdayjobs.com",
)


def _id(source: str, url: str, title: str) -> str:
    return hashlib.sha1(f"{source}|{url}|{title}".encode("utf-8")).hexdigest()[:20]


def _text(value: str) -> str:
    return BeautifulSoup(unescape(value or ""), "html.parser").get_text(" ", strip=True)


def _item(source: str, key: str, title: str, org: str, location: str, url: str,
          description: str, posted: str = "", query: str = "",
          deadline: str = "") -> dict:
    country, tier = locate(location, org, title, description[:500])
    timing, _, days_left = freshness_score(posted, deadline)
    return {
        "id": _id(key, url, title), "source": source, "source_key": key,
        "title": title, "org": org, "department": "", "location": location,
        "country": country, "country_tier": tier, "url": url,
        "description": description[:12000], "posted": posted, "deadline": deadline,
        "days_left": days_left, "role_key": "industry", "role_label": "Industry role",
        "score": round(35 + timing * 15), "matched_terms": [], "flags": [],
        "positives": [], "breakdown": {}, "query": query, "enriched": 1,
        "career_track": "industry", "status": "new",
    }


def _xml_text(node, name: str) -> str:
    child = node.find(name)
    return "" if child is None else " ".join("".join(child.itertext()).split())


def _parse_nhs_xml(payload: bytes) -> list[dict]:
    """Normalize the official NHS Jobs self-serve API response."""
    root = ET.fromstring(payload)
    items = []
    for row in root.findall("vacancyDetails"):
        title = _xml_text(row, "title")
        url = _xml_text(row, "url")
        if not title or not url:
            continue
        locations = [" ".join((part.text or "").split())
                     for part in row.findall("./locations/*") if (part.text or "").strip()]
        location = "; ".join(locations) or "United Kingdom"
        description = _xml_text(row, "description")
        # Staff-group filtering is stronger occupational evidence than broad
        # advert wording and covers valid titles such as Theatre Team Leader.
        description = "Registered nursing and midwifery vacancy. " + description
        item = _item(
            "NHS Jobs", "nhs_jobs", title, _xml_text(row, "employer"),
            location, url, description, _xml_text(row, "postDate")[:10],
            "NHS registered nursing and midwifery", _xml_text(row, "closeDate")[:10],
        )
        item["country"], item["country_tier"] = "United Kingdom", "target"
        items.append(item)
    return items


def _fetch_nhs(log=print, pages: int = 5) -> list[dict]:
    """Fetch the newest open registered nursing/midwifery NHS vacancies."""
    headers = {"User-Agent": USER_AGENT, "Accept": "application/xml"}
    found: dict[str, dict] = {}
    for page in range(1, pages + 1):
        response = requests.get(
            "https://www.jobs.nhs.uk/api/v1/search_xml",
            params={"staffGroup": "NURSING_AND_MIDWIFERY_REGD", "limit": 100,
                    "sort": "publicationDateDesc", "page": page},
            headers=headers, timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        rows = _parse_nhs_xml(response.content)
        for item in rows:
            found[item["id"]] = item
        log(f"  NHS Jobs: nursing page {page}/{pages:<2} {len(rows):3d} results")
        if len(rows) < 100:
            break
    return list(found.values())


def _profile_search_specs() -> list[tuple[str, list[str], str, str]]:
    """Return occupation-level searches without sending CV text to the web."""
    conn = store.connect()
    try:
        rows = conn.execute(
            "SELECT user_id,profile_json FROM user_profiles WHERE kind='industry'"
        ).fetchall()
    finally:
        conn.close()
    specs = []
    seen = set()
    for row in rows:
        try:
            profile = json.loads(row["profile_json"] or "{}")
        except (TypeError, ValueError):
            continue
        domain = profile.get("primary_domain") or "general"
        titles = [str(x).strip() for x in profile.get("target_titles") or [] if str(x).strip()]
        if not titles:
            continue
        try:
            cfg = get_config(row["user_id"], include_keys=True) or {}
        except Exception:
            cfg = {}
        provider = cfg.get("search_provider") or "duckduckgo"
        key = cfg.get("search_key") or ""
        signature = (domain, provider)
        if signature in seen:
            continue
        seen.add(signature)
        specs.append((domain, titles[:3], provider, key))
    return specs


def _direct_job_result(result: dict, domain: str, query: str) -> dict | None:
    url = (result.get("url") or "").split("#", 1)[0]
    parsed = urlparse(url)
    host = parsed.netloc.lower().removeprefix("www.")
    host_family = ("myworkdayjobs.com" if host.endswith(".myworkdayjobs.com") else host)
    if host_family not in WEB_JOB_HOSTS:
        return None
    parts = [p for p in parsed.path.split("/") if p]
    if host_family == "jobs.lever.co":
        if len(parts) < 2:  # employer landing page, not an advert
            return None
        if parts[-1] == "apply":
            parts = parts[:-1]
            url = f"{parsed.scheme}://{parsed.netloc}/" + "/".join(parts)
        org = parts[0].replace("-", " ").title()
        source, source_key = "Employer jobs via Lever", "web_lever"
    elif host_family in {"boards.greenhouse.io", "job-boards.greenhouse.io"}:
        if "jobs" not in parts or not any(p.isdigit() and len(p) >= 6 for p in parts):
            return None
        org = (parts[0] if parts else "Employer").replace("-", " ").title()
        source, source_key = "Employer jobs via Greenhouse", "web_greenhouse"
    else:
        # Other major employer applicant-tracking systems use a company/job-id
        # path. Reject their root and search pages but keep direct adverts.
        if len(parts) < 2 or parts[-1].lower() in {"jobs", "search", "careers"}:
            return None
        org = parts[0].replace("-", " ").title()
        label = {
            "jobs.ashbyhq.com": "Ashby", "apply.workable.com": "Workable",
            "jobs.smartrecruiters.com": "SmartRecruiters",
            "myworkdayjobs.com": "Workday",
        }[host_family]
        source, source_key = f"Employer jobs via {label}", f"web_{label.lower()}"
    title = re.sub(r"\s*(?:[-|]\s*(?:Lever|Greenhouse Software|Workable|Ashby).*)$", "",
                   result.get("title") or "", flags=re.I).strip()
    if not title:
        return None
    snippet = result.get("snippet") or ""
    return _item(source, source_key, title, org, "", url, snippet, "", query)


def _fetch_profile_web_jobs(log=print) -> list[dict]:
    """Search direct employer ATS pages using each profile's chosen web provider."""
    found: dict[str, dict] = {}
    for domain, titles, provider, key in _profile_search_specs():
        count = 0
        for title in titles:
            for host in WEB_JOB_HOSTS:
                query = f'site:{host} "{title}" job'
                try:
                    results = _search(query, provider, key, limit=8)
                except Exception as exc:
                    log(f"  !! {provider} web search failed for {domain}: {exc}")
                    break
                for result in results:
                    item = _direct_job_result(result, domain, query)
                    if item:
                        found[item["id"]] = item
                        count += 1
        log(f"  web search ({provider}): {domain:<22} {count:3d} direct adverts")
    return list(found.values())


def fetch(log=print) -> list[dict]:
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    found: dict[str, dict] = {}
    try:
        for item in _fetch_nhs(log):
            found[item["id"]] = item
    except Exception as exc:
        log(f"  !! NHS Jobs nursing feed failed: {exc}")
    try:
        response = requests.get("https://remotive.com/api/remote-jobs",
                                headers=headers, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        rows = response.json().get("jobs", [])[:250]
        for row in rows:
            item = _item("Remotive", "remotive", row.get("title", ""),
                row.get("company_name", ""), row.get("candidate_required_location", "Remote"),
                row.get("url", ""), _text(row.get("description", "")),
                (row.get("publication_date") or "")[:10], "all remote professions")
            found[item["id"]] = item
        log(f"  remotive: {len(rows)} jobs across all professions")
    except Exception as exc:
        log(f"  !! Remotive failed: {exc}")

    try:
        response = requests.get("https://www.arbeitnow.com/api/job-board-api",
                                headers=headers, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        rows = response.json().get("data", [])
        for row in rows:
            title = row.get("title", "")
            desc = _text(row.get("description", ""))
            stamp = row.get("created_at")
            posted = (dt.datetime.fromtimestamp(stamp, dt.timezone.utc).date().isoformat()
                      if isinstance(stamp, (int, float)) else str(stamp or "")[:10])
            item = _item("Arbeitnow", "arbeitnow", title, row.get("company_name", ""),
                         row.get("location", ""), row.get("url", ""), desc, posted, "broad crawl")
            found[item["id"]] = item
        log(f"  arbeitnow: {len(rows)} jobs across all professions")
    except Exception as exc:
        log(f"  !! Arbeitnow failed: {exc}")
    try:
        response = requests.get("https://jobicy.com/api/v2/remote-jobs",
                                params={"count": 100}, headers=headers,
                                timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        rows = response.json().get("jobs", [])
        for row in rows:
            item = _item("Jobicy", "jobicy", row.get("jobTitle", ""),
                row.get("companyName", ""), row.get("jobGeo", "Remote"),
                row.get("url", ""), _text(row.get("jobDescription") or row.get("jobExcerpt", "")),
                (row.get("pubDate") or "")[:10], "all remote professions")
            found[item["id"]] = item
        log(f"  jobicy: {len(rows)} jobs across all professions")
    except Exception as exc:
        log(f"  !! Jobicy failed: {exc}")
    try:
        response = requests.get("https://remoteok.com/api", headers=headers,
                                timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        rows = [row for row in response.json() if isinstance(row, dict) and row.get("position")]
        for row in rows[:150]:
            item = _item("Remote OK", "remoteok", row.get("position", ""),
                row.get("company", ""), row.get("location") or "Remote",
                row.get("url", ""), _text(row.get("description", "")),
                (row.get("date") or "")[:10], "all remote professions")
            found[item["id"]] = item
        log(f"  remoteok: {min(len(rows), 150)} jobs across all professions")
    except Exception as exc:
        log(f"  !! Remote OK failed: {exc}")
    try:
        for item in _fetch_profile_web_jobs(log):
            found[item["id"]] = item
    except Exception as exc:
        log(f"  !! Profile-driven web job search failed: {exc}")
    return list(found.values())

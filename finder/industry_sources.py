# -*- coding: utf-8 -*-
"""
Country-specific and global industry job sources.

Each ``fetch_*`` function takes the job titles to search for (taken from the
registered users' industry CVs) and returns normalised postings. Every source
here was checked against the live site; none needs an API key. Sources that
need a key (Adzuna, Reed API, USAJOBS) switch on when the matching environment
variables are set.

``SOURCES`` lists them with the country each one covers, so the pipeline can run
them in parallel and the settings page can show where jobs come from.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

from bs4 import BeautifulSoup

from .scoring import freshness_score, locate
from .sources.base import clean, get, get_json, make_id

MAX_DESC = 12000


# ---------------------------------------------------------------------------
# Item construction
# ---------------------------------------------------------------------------
def make_item(source: str, key: str, title: str, org: str, location: str, url: str,
              description: str, posted: str = "", query: str = "", deadline: str = "",
              country: str = "", needs_detail: bool = False) -> dict:
    """A normalised industry posting. `country` overrides guessing from the text."""
    title = clean(title)
    guessed, tier = locate(location, org, title, (description or "")[:400])
    if country and guessed != country:
        tier = "target"
    country = country or guessed
    timing, _, days_left = freshness_score(posted, deadline)
    return {
        "id": hashlib.sha1(f"{key}|{url}|{title}".encode("utf-8")).hexdigest()[:20],
        "source": source, "source_key": key,
        "title": title, "org": clean(org), "department": "", "location": clean(location),
        "country": country, "country_tier": tier or "unknown", "url": url,
        "description": clean(description)[:MAX_DESC], "posted": posted, "deadline": deadline,
        "days_left": days_left, "role_key": "industry", "role_label": "Industry role",
        "score": round(35 + timing * 15), "matched_terms": [], "flags": [],
        "positives": [], "breakdown": {}, "query": query,
        "enriched": 0 if needs_detail else 1, "needs_detail": needs_detail,
        "career_track": "industry", "status": "new",
    }


def _iso(value) -> str:
    """Best-effort ISO date from the formats these APIs return."""
    if value is None or value == "":
        return ""
    if isinstance(value, (int, float)):
        try:
            return dt.datetime.fromtimestamp(float(value), dt.timezone.utc).date().isoformat()
        except (OverflowError, OSError, ValueError):
            return ""
    text = str(value).strip()
    m = re.match(r"(\d{4}-\d{2}-\d{2})", text)
    return m.group(1) if m else ""


def _segments(node) -> list[str]:
    return [clean(s) for s in node.get_text("|", strip=True).split("|") if clean(s)]


_GENERIC_ROLE_WORDS = {
    "senior", "junior", "assistant", "associate", "manager", "officer", "engineer",
    "specialist", "analyst", "coordinator", "consultant", "executive", "lead", "head",
    "principal", "director", "administrator", "advisor", "technician", "developer",
}


def title_matches(title: str, titles: list[str]) -> bool:
    """True when a posting title fits any wanted title.

    "civil engineer" must contain "civil"; "project manager" must contain "project".
    A wanted title made only of generic words ("engineer") must match as a phrase.
    """
    low = (title or "").lower()
    for wanted in titles:
        wanted = wanted.lower().strip()
        if not wanted:
            continue
        if wanted in low:
            return True
        distinctive = [w for w in re.findall(r"[a-z]{4,}", wanted) if w not in _GENERIC_ROLE_WORDS]
        if distinctive and any(w in low for w in distinctive):
            return True
    return False


# ---------------------------------------------------------------------------
# Structured JSON sources
# ---------------------------------------------------------------------------
def fetch_sweden(titles: list[str], log=print) -> list[dict]:
    """Platsbanken (Arbetsförmedlingen) via the open JobTech search API."""
    out: dict[str, dict] = {}
    for title in titles:
        data = get_json("https://jobsearch.api.jobtechdev.se/search?"
                        + urllib.parse.urlencode({"q": title, "limit": 50}))
        for hit in (data or {}).get("hits", []):
            addr = hit.get("workplace_address") or {}
            place = ", ".join(x for x in (addr.get("municipality"), addr.get("region")) if x)
            url = hit.get("webpage_url") or ""
            if not url:
                continue
            item = make_item(
                "Platsbanken (Sweden)", "se_platsbanken", hit.get("headline", ""),
                (hit.get("employer") or {}).get("name", ""), place or "Sweden", url,
                (hit.get("description") or {}).get("text", ""),
                _iso(hit.get("publication_date")), title,
                _iso(hit.get("application_deadline")), country="Sweden")
            out[item["id"]] = item
    log("  Sweden (Platsbanken): %d postings" % len(out))
    return list(out.values())


def fetch_switzerland(titles: list[str], log=print) -> list[dict]:
    """jobs.ch, the main Swiss job board, via its public search API."""
    out: dict[str, dict] = {}
    for title in titles:
        data = get_json("https://www.jobs.ch/api/v1/public/search?"
                        + urllib.parse.urlencode({"query": title, "rows": 20}))
        for doc in (data or {}).get("documents", []):
            link = ((doc.get("_links") or {}).get("detail_en") or {}).get("href")
            if not link:
                continue
            item = make_item(
                "jobs.ch (Switzerland)", "ch_jobsch", doc.get("title", ""),
                doc.get("company_name", ""), (doc.get("place") or "") + ", Switzerland", link,
                doc.get("preview", ""), _iso(doc.get("publication_date")), title,
                country="Switzerland")
            out[item["id"]] = item
    log("  Switzerland (jobs.ch): %d postings" % len(out))
    return list(out.values())


def fetch_himalayas(titles: list[str], log=print) -> list[dict]:
    """Himalayas: remote jobs worldwide, searchable by title."""
    out: dict[str, dict] = {}
    for title in titles:
        data = get_json("https://himalayas.app/jobs/api/search?"
                        + urllib.parse.urlencode({"q": title, "page": 1}))
        for row in (data or {}).get("jobs", []):
            url = row.get("applicationLink") or row.get("guid") or ""
            if not url:
                continue
            where = ", ".join(row.get("locationRestrictions") or []) or "Remote (worldwide)"
            item = make_item(
                "Himalayas (remote)", "himalayas", row.get("title", ""),
                row.get("companyName", ""), where, url,
                row.get("description") or row.get("excerpt", ""),
                _iso(row.get("pubDate")), title, _iso(row.get("expiryDate")))
            out[item["id"]] = item
    log("  Himalayas (remote, worldwide): %d postings" % len(out))
    return list(out.values())


def fetch_remotive(titles: list[str], log=print) -> list[dict]:
    out: dict[str, dict] = {}
    for title in titles:
        data = get_json("https://remotive.com/api/remote-jobs?"
                        + urllib.parse.urlencode({"search": title, "limit": 40}))
        for row in (data or {}).get("jobs", []):
            if not row.get("url"):
                continue
            item = make_item(
                "Remotive", "remotive", row.get("title", ""), row.get("company_name", ""),
                row.get("candidate_required_location") or "Remote", row["url"],
                row.get("description", ""), _iso(row.get("publication_date")), title)
            out[item["id"]] = item
    log("  Remotive: %d postings" % len(out))
    return list(out.values())


JOBICY_GEO = {"United States": "usa", "United Kingdom": "uk", "Canada": "canada",
              "Australia": "australia", "Germany": "germany", "France": "france",
              "Netherlands": "netherlands", "Ireland": "ireland", "Spain": "spain",
              "Italy": "italy", "Singapore": "singapore", "India": "india",
              "South Africa": "south-africa", "Nigeria": "nigeria", "Brazil": "brazil"}


def fetch_jobicy(titles: list[str], log=print) -> list[dict]:
    out: dict[str, dict] = {}
    queries = [("", t) for t in titles[:4]]
    for geo in JOBICY_GEO.values():
        queries.append((geo, ""))
    for geo, tag in queries:
        params = {"count": 50}
        if geo:
            params["geo"] = geo
        if tag:
            params["tag"] = tag
        data = get_json("https://jobicy.com/api/v2/remote-jobs?" + urllib.parse.urlencode(params))
        for row in (data or {}).get("jobs", []):
            if not row.get("url") or not title_matches(row.get("jobTitle", ""), titles):
                continue
            item = make_item(
                "Jobicy", "jobicy", row.get("jobTitle", ""), row.get("companyName", ""),
                row.get("jobGeo") or "Remote", row["url"],
                row.get("jobDescription") or row.get("jobExcerpt", ""),
                _iso(row.get("pubDate")), tag or geo)
            out[item["id"]] = item
    log("  Jobicy (remote, by country): %d postings" % len(out))
    return list(out.values())


def fetch_workingnomads(titles: list[str], log=print) -> list[dict]:
    data = get_json("https://www.workingnomads.com/api/exposed_jobs/") or []
    out = {}
    for row in data:
        if not row.get("url") or not title_matches(row.get("title", ""), titles):
            continue
        item = make_item("Working Nomads", "workingnomads", row.get("title", ""),
                         row.get("company_name", ""), row.get("location") or "Remote",
                         row["url"], row.get("description", ""), _iso(row.get("pub_date")),
                         "remote crawl")
        out[item["id"]] = item
    log("  Working Nomads: %d relevant postings" % len(out))
    return list(out.values())


def fetch_arbeitnow(titles: list[str], log=print) -> list[dict]:
    """Arbeitnow: jobs in Germany and the DACH region, English-friendly."""
    out: dict[str, dict] = {}
    for page in range(1, 4):
        data = get_json(f"https://www.arbeitnow.com/api/job-board-api?page={page}")
        rows = (data or {}).get("data", [])
        for row in rows:
            if not row.get("url") or not title_matches(row.get("title", ""), titles):
                continue
            item = make_item("Arbeitnow (Germany)", "arbeitnow", row.get("title", ""),
                             row.get("company_name", ""), row.get("location", ""), row["url"],
                             row.get("description", ""), _iso(row.get("created_at")),
                             "broad crawl")
            out[item["id"]] = item
        if not rows:
            break
    log("  Arbeitnow (Germany): %d postings" % len(out))
    return list(out.values())


def fetch_remoteok(titles: list[str], log=print) -> list[dict]:
    data = get_json("https://remoteok.com/api") or []
    out = {}
    for row in data:
        if (not isinstance(row, dict) or not row.get("position") or not row.get("url")
                or not title_matches(row["position"], titles)):
            continue
        item = make_item("Remote OK", "remoteok", row["position"], row.get("company", ""),
                         row.get("location") or "Remote", row["url"],
                         row.get("description", ""), _iso(row.get("date")), "remote crawl")
        out[item["id"]] = item
    log("  Remote OK: %d postings" % len(out))
    return list(out.values())


# ---------------------------------------------------------------------------
# United Kingdom
# ---------------------------------------------------------------------------
def fetch_reed_uk(titles: list[str], log=print) -> list[dict]:
    """Reed.co.uk search pages (the page embeds its results as JSON)."""
    out: dict[str, dict] = {}
    for title in titles:
        slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
        r = get(f"https://www.reed.co.uk/jobs/{slug}-jobs")
        if r is None:
            continue
        m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', r.text, re.S)
        if not m:
            continue
        try:
            rows = json.loads(m.group(1))["props"]["pageProps"]["searchResults"]["jobs"]
        except (ValueError, KeyError, TypeError):
            continue
        for row in rows:
            detail = row.get("jobDetail") or {}
            job_id = detail.get("jobId")
            if not job_id:
                continue
            place = ", ".join(x for x in (detail.get("displayLocationName"),
                                          detail.get("countyLocation")) if x)
            item = make_item(
                "Reed (UK)", "uk_reed", detail.get("jobTitle", ""),
                row.get("profileName", "") or detail.get("ouName", ""), place,
                f"https://www.reed.co.uk{row.get('url') or '/jobs/job/' + str(job_id)}",
                detail.get("jobDescriptionSnippet", ""),
                _iso(detail.get("displayDate")), title, _iso(detail.get("expiryDate")),
                country="United Kingdom", needs_detail=True)
            out[item["id"]] = item
    log("  United Kingdom (Reed): %d postings" % len(out))
    return list(out.values())


# ---------------------------------------------------------------------------
# HTML search pages
# ---------------------------------------------------------------------------
def fetch_canada(titles: list[str], log=print) -> list[dict]:
    """Job Bank (Government of Canada)."""
    out: dict[str, dict] = {}
    for title in titles:
        r = get("https://www.jobbank.gc.ca/jobsearch/jobsearch?"
                + urllib.parse.urlencode({"searchstring": title, "sort": "D", "fsrc": 16}))
        if r is None:
            continue
        for article in BeautifulSoup(r.text, "html.parser").select("article"):
            a = article.find("a", class_="resultJobItem")
            name = article.select_one(".noctitle")
            if not a or not name:
                continue
            job_id = (article.get("id") or "").replace("article-", "")
            if not job_id:
                continue
            url = f"https://www.jobbank.gc.ca/jobsearch/jobposting/{job_id}"
            org_el = article.select_one(".business")
            org = clean(org_el.get_text(" ", strip=True)) if org_el else ""
            loc_el = article.select_one(".location")
            location = clean(loc_el.get_text(" ", strip=True)).replace("Location", "").strip() if loc_el else ""
            posted = ""
            date_el = article.select_one(".date")
            if date_el:
                try:
                    posted = dt.datetime.strptime(clean(date_el.get_text()), "%B %d, %Y").date().isoformat()
                except ValueError:
                    posted = ""
            item = make_item("Job Bank (Canada)", "ca_jobbank", name.get_text(" ", strip=True),
                             org, location, url, f"{name.get_text(' ', strip=True)} at {org}, {location}",
                             posted, title, country="Canada", needs_detail=True)
            out[item["id"]] = item
    log("  Canada (Job Bank): %d postings" % len(out))
    return list(out.values())


def _jobberman_like(host: str, source: str, key: str, country: str,
                    titles: list[str], log) -> list[dict]:
    """Jobberman (Nigeria, Ghana) and BrighterMonday (Kenya, Uganda, Tanzania)."""
    out: dict[str, dict] = {}
    for title in titles:
        r = get(f"https://{host}/jobs?" + urllib.parse.urlencode({"q": title}))
        if r is None:
            continue
        soup = BeautifulSoup(r.text, "html.parser")
        for a in soup.find_all("a", href=re.compile(r"/listings/")):
            name = clean(a.get_text(" ", strip=True))
            if not name or len(name) > 140:
                continue
            card = a
            for _ in range(5):
                card = card.parent
                if card is None:
                    break
                if 60 < len(card.get_text(" ", strip=True)) < 700 and card.find("a", href=re.compile(r"/listings/")) is a:
                    break
            segs = _segments(card) if card is not None else []
            segs = [s for s in segs if s not in {"FEATURED", "Easy Apply", "Full Time", "Part Time",
                                                 "Contract", "Confidential", "Internship"} and s != name]
            org = segs[0] if segs else ""
            location = segs[1] if len(segs) > 1 else country
            url = a["href"].split("?", 1)[0]
            item = make_item(source, key, name, org, location, url, " | ".join(segs[:8]),
                             "", title, country=country, needs_detail=True)
            out[item["id"]] = item
    log("  %s: %d postings" % (country, len(out)))
    return list(out.values())


def fetch_nigeria(titles, log=print):
    return _jobberman_like("www.jobberman.com", "Jobberman (Nigeria)", "ng_jobberman",
                           "Nigeria", titles, log)


def fetch_ghana(titles, log=print):
    return _jobberman_like("www.jobberman.com.gh", "Jobberman (Ghana)", "gh_jobberman",
                           "Ghana", titles, log)


def fetch_kenya(titles, log=print):
    return _jobberman_like("www.brightermonday.co.ke", "BrighterMonday (Kenya)", "ke_brightermonday",
                           "Kenya", titles, log)


def fetch_south_africa(titles: list[str], log=print) -> list[dict]:
    """Careers24."""
    out: dict[str, dict] = {}
    for title in titles:
        slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
        r = get(f"https://www.careers24.com/jobs/kw-{slug}/")
        if r is None:
            continue
        soup = BeautifulSoup(r.text, "html.parser")
        for card in soup.select("div.job-card"):
            a = card.find("a", href=re.compile(r"/jobs/adverts/"))
            if not a:
                continue
            url = urllib.parse.urljoin("https://www.careers24.com", a["href"].split("?", 1)[0])
            name = clean(a.get_text(" ", strip=True))
            segs = [s for s in _segments(card) if s != name]
            facts = " ".join(segs)
            location = re.split(r"\s*(?:Job Type|Salary|Posted|Employer)\b", segs[0] if segs else "")[0].strip()
            org_match = re.search(r"Employer\s*:?\s*([^|]+)", facts)
            item = make_item("Careers24 (South Africa)", "za_careers24", name,
                             org_match.group(1).strip() if org_match else "", location, url,
                             " | ".join(segs[:10]), "", title,
                             country="South Africa", needs_detail=True)
            out[item["id"]] = item
    log("  South Africa (Careers24): %d postings" % len(out))
    return list(out.values())


def fetch_usa_government(titles: list[str], log=print) -> list[dict]:
    """GovernmentJobs.com: US city, county, state and federal agency posts."""
    out: dict[str, dict] = {}
    for title in titles:
        r = get("https://www.governmentjobs.com/jobs?" + urllib.parse.urlencode({"keyword": title}))
        if r is None:
            continue
        for li in BeautifulSoup(r.text, "html.parser").select("li.job-item"):
            a = li.find("a", href=re.compile(r"/jobs/\d+"))
            if not a:
                continue
            segs = _segments(li)
            name = clean(a.get_text(" ", strip=True))
            rest = [s for s in segs if s != name]
            org = rest[0] if rest else ""
            location = rest[1] if len(rest) > 1 else ""
            url = urllib.parse.urljoin("https://www.governmentjobs.com", a["href"].split("?", 1)[0])
            item = make_item("GovernmentJobs (USA)", "us_govjobs", name, org, location, url,
                             " | ".join(segs), "", title, country="United States",
                             needs_detail=True)
            out[item["id"]] = item
    log("  United States (GovernmentJobs): %d postings" % len(out))
    return list(out.values())


# ---------------------------------------------------------------------------
# Keyed sources (switch on when credentials are present)
# ---------------------------------------------------------------------------
ADZUNA_COUNTRIES = {"gb": "United Kingdom", "us": "United States", "ca": "Canada",
                    "au": "Australia", "nz": "New Zealand", "de": "Germany", "fr": "France",
                    "nl": "Netherlands", "at": "Austria", "be": "Belgium", "ch": "Switzerland",
                    "it": "Italy", "es": "Spain", "pl": "Poland", "sg": "Singapore",
                    "za": "South Africa", "in": "India", "br": "Brazil", "mx": "Mexico"}


def adzuna_enabled() -> bool:
    return bool(os.environ.get("ADZUNA_APP_ID") and os.environ.get("ADZUNA_APP_KEY"))


def fetch_adzuna(titles: list[str], log=print) -> list[dict]:
    """Adzuna covers 19 countries. Free keys: https://developer.adzuna.com/"""
    app_id, app_key = os.environ["ADZUNA_APP_ID"], os.environ["ADZUNA_APP_KEY"]
    out: dict[str, dict] = {}

    def one(args):
        code, title = args
        return code, title, get_json(
            f"https://api.adzuna.com/v1/api/jobs/{code}/search/1?"
            + urllib.parse.urlencode({"app_id": app_id, "app_key": app_key,
                                      "results_per_page": 30, "what": title,
                                      "sort_by": "date", "content-type": "application/json"}))

    with ThreadPoolExecutor(max_workers=3) as pool:
        for code, title, data in pool.map(
                one, [(c, t) for c in ADZUNA_COUNTRIES for t in titles[:3]]):
            for row in (data or {}).get("results", []):
                if not row.get("redirect_url"):
                    continue
                item = make_item(
                    f"Adzuna ({ADZUNA_COUNTRIES[code]})", f"adzuna_{code}", row.get("title", ""),
                    (row.get("company") or {}).get("display_name", ""),
                    (row.get("location") or {}).get("display_name", ""), row["redirect_url"],
                    row.get("description", ""), _iso(row.get("created")), title,
                    country=ADZUNA_COUNTRIES[code])
                out[item["id"]] = item
    log("  Adzuna (%d countries): %d postings" % (len(ADZUNA_COUNTRIES), len(out)))
    return list(out.values())


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
# (key, label, countries covered, function). `titles_needed` sources are queried per
# title; the rest are broad crawls that are filtered by title afterwards.
SOURCES = [
    ("se_platsbanken", "Platsbanken", "Sweden", fetch_sweden),
    ("ch_jobsch", "jobs.ch", "Switzerland", fetch_switzerland),
    ("uk_reed", "Reed", "United Kingdom", fetch_reed_uk),
    ("ca_jobbank", "Job Bank", "Canada", fetch_canada),
    ("us_govjobs", "GovernmentJobs", "United States", fetch_usa_government),
    ("ng_jobberman", "Jobberman", "Nigeria", fetch_nigeria),
    ("gh_jobberman", "Jobberman", "Ghana", fetch_ghana),
    ("ke_brightermonday", "BrighterMonday", "Kenya", fetch_kenya),
    ("za_careers24", "Careers24", "South Africa", fetch_south_africa),
    ("arbeitnow", "Arbeitnow", "Germany", fetch_arbeitnow),
    ("himalayas", "Himalayas", "Remote (worldwide)", fetch_himalayas),
    ("remotive", "Remotive", "Remote (worldwide)", fetch_remotive),
    ("jobicy", "Jobicy", "Remote (by country)", fetch_jobicy),
    ("workingnomads", "Working Nomads", "Remote (worldwide)", fetch_workingnomads),
    ("remoteok", "Remote OK", "Remote (worldwide)", fetch_remoteok),
]

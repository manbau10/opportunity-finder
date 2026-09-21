"""Employer and department research with retained source provenance."""

from __future__ import annotations

import datetime as dt
from urllib.parse import parse_qs, unquote, urlparse

import requests
from bs4 import BeautifulSoup

from .config import REQUEST_TIMEOUT, USER_AGENT
from .providers import get_config


def _clean_result(title: str, url: str, snippet: str, query: str) -> dict | None:
    if not url.startswith(("http://", "https://")):
        return None
    return {
        "title": " ".join((title or "Untitled source").split())[:300],
        "url": url[:2000],
        "snippet": " ".join((snippet or "").split())[:900],
        "query": query,
        "retrieved_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
    }


def _search(query: str, provider: str, key: str, limit: int = 5) -> list[dict]:
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    rows = []
    if provider == "tavily":
        r = requests.post("https://api.tavily.com/search", timeout=REQUEST_TIMEOUT,
                          json={"api_key": key, "query": query, "max_results": limit,
                                "search_depth": "advanced"})
        r.raise_for_status()
        rows = [(x.get("title"), x.get("url"), x.get("content")) for x in r.json().get("results", [])]
    elif provider == "brave":
        r = requests.get("https://api.search.brave.com/res/v1/web/search",
                         params={"q": query, "count": limit}, timeout=REQUEST_TIMEOUT,
                         headers={**headers, "X-Subscription-Token": key})
        r.raise_for_status()
        rows = [(x.get("title"), x.get("url"), x.get("description"))
                for x in r.json().get("web", {}).get("results", [])]
    elif provider == "serper":
        r = requests.post("https://google.serper.dev/search", timeout=REQUEST_TIMEOUT,
                          headers={**headers, "X-API-KEY": key}, json={"q": query, "num": limit})
        r.raise_for_status()
        rows = [(x.get("title"), x.get("link"), x.get("snippet"))
                for x in r.json().get("organic", [])]
    else:
        r = requests.get("https://html.duckduckgo.com/html/", params={"q": query},
                         timeout=REQUEST_TIMEOUT, headers={"User-Agent": USER_AGENT})
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for result in soup.select(".result")[:limit]:
            anchor = result.select_one(".result__a")
            if not anchor:
                continue
            url = anchor.get("href", "")
            if "uddg=" in url:
                url = unquote(parse_qs(urlparse(url).query).get("uddg", [url])[0])
            snippet = result.select_one(".result__snippet")
            rows.append((anchor.get_text(" ", strip=True), url,
                         snippet.get_text(" ", strip=True) if snippet else ""))
    cleaned = [_clean_result(t or "", u or "", s or "", query) for t, u, s in rows]
    return [x for x in cleaned if x][:limit]


def research_opportunity(user_id: str, opportunity: dict) -> list[dict]:
    cfg = get_config(user_id, include_keys=True)
    provider = (cfg or {}).get("search_provider", "duckduckgo")
    key = (cfg or {}).get("search_key", "")
    org = opportunity.get("org") or "employer"
    department = opportunity.get("department") or ""
    title = opportunity.get("title") or "role"
    queries = [
        f'"{org}" {department} courses programmes curriculum',
        f'"{org}" {department} research groups strategy facilities',
        f'"{org}" {title} department staff priorities',
    ]
    sources: list[dict] = []
    seen = set()
    for query in queries:
        try:
            for result in _search(query, provider, key, limit=4):
                if result["url"] not in seen:
                    seen.add(result["url"])
                    sources.append(result)
        except Exception as exc:
            sources.append({
                "title": "Search unavailable", "url": "", "snippet": str(exc)[:300],
                "query": query,
                "retrieved_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            })
    return sources[:12]


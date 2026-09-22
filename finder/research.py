"""Job, employer and department research with downloadable source evidence."""

from __future__ import annotations

import datetime as dt
import hashlib
import ipaddress
import re
import socket
from urllib.parse import parse_qs, unquote, urljoin, urlparse

import requests
import urllib3
from bs4 import BeautifulSoup
from pypdf import PdfReader

from .config import REQUEST_TIMEOUT, USER_AGENT
from .providers import get_config

MAX_RESOURCE_BYTES = 9 * 1024 * 1024
MAX_RESOURCES = 18
RELEVANT_LINK = re.compile(
    r"job\s*description|person\s*specification|position\s*description|selection\s*criteria|"
    r"candidate\s*(?:information|pack|guidance)|guidance\s*for\s*applicants|application\s*form|"
    r"equal(?:ity)?|diversity|inclusion|module|course|programme|curriculum|research\s*(?:strategy|group)",
    re.I,
)
APPLY_LINK = re.compile(r"apply|view\s+(?:the\s+)?(?:vacancy|job)|more\s+details|full\s+advert", re.I)


def _stamp() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def _clean_result(title: str, url: str, snippet: str, query: str,
                  kind: str = "search result") -> dict | None:
    if not url.startswith(("http://", "https://")):
        return None
    return {
        "title": " ".join((title or "Untitled source").split())[:300],
        "url": url[:2000],
        "snippet": " ".join((snippet or "").split())[:1600],
        "query": query,
        "kind": kind,
        "retrieved_at": _stamp(),
    }


def _search(query: str, provider: str, key: str, limit: int = 5) -> list[dict]:
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    rows = []
    if provider == "tavily":
        r = requests.post("https://api.tavily.com/search", timeout=REQUEST_TIMEOUT,
                          json={"api_key": key, "query": query, "max_results": limit,
                                "search_depth": "advanced"})
        r.raise_for_status()
        rows = [(x.get("title"), x.get("url"), x.get("content"))
                for x in r.json().get("results", [])]
    elif provider == "brave":
        r = requests.get("https://api.search.brave.com/res/v1/web/search",
                         params={"q": query, "count": limit}, timeout=REQUEST_TIMEOUT,
                         headers={**headers, "X-Subscription-Token": key})
        r.raise_for_status()
        rows = [(x.get("title"), x.get("url"), x.get("description"))
                for x in r.json().get("web", {}).get("results", [])]
    elif provider == "serper":
        r = requests.post("https://google.serper.dev/search", timeout=REQUEST_TIMEOUT,
                          headers={**headers, "X-API-KEY": key},
                          json={"q": query, "num": limit})
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


def _queries(opportunity: dict, kind: str) -> list[str]:
    org = opportunity.get("org") or "employer"
    department = opportunity.get("department") or ""
    title = opportunity.get("title") or "role"
    if kind == "academic":
        return [
            f'"{org}" "{title}" job description person specification PDF',
            f'"{org}" "{department}" courses modules curriculum',
            f'"{org}" "{department}" research groups research strategy',
            f'"{org}" civil engineering course modules degree apprenticeship',
            f'"{org}" applicant guidance equality diversity inclusion',
            f'"{org}" "{department}" staff expertise facilities',
        ]
    return [
        f'"{org}" "{title}" job description selection criteria',
        f'"{org}" about strategy products services annual report',
        f'"{org}" careers values culture benefits',
        f'"{org}" diversity inclusion sustainability',
        f'"{org}" "{department}" team projects priorities',
    ]


def research_opportunity(user_id: str, opportunity: dict, kind: str | None = None) -> list[dict]:
    cfg = get_config(user_id, include_keys=True)
    provider = (cfg or {}).get("search_provider", "duckduckgo")
    key = (cfg or {}).get("search_key", "")
    track = kind or opportunity.get("career_track") or "academic"
    sources: list[dict] = []
    seen = set()
    for query in _queries(opportunity, track):
        try:
            for result in _search(query, provider, key, limit=5):
                if result["url"] not in seen:
                    seen.add(result["url"])
                    sources.append(result)
        except Exception as exc:
            sources.append({
                "title": "Search unavailable", "url": "", "snippet": str(exc)[:500],
                "query": query, "kind": "search error", "retrieved_at": _stamp(),
            })
    return sources[:30]


def _public_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    try:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        for info in socket.getaddrinfo(parsed.hostname, port, type=socket.SOCK_STREAM):
            ip = ipaddress.ip_address(info[4][0])
            if (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
                    or ip.is_multicast or ip.is_unspecified):
                return False
    except (OSError, ValueError):
        return False
    return True


def _download(url: str) -> tuple[bytes, str, str]:
    current = url
    response = None
    request_args = dict(timeout=REQUEST_TIMEOUT, headers={"User-Agent": USER_AGENT},
                        stream=True, allow_redirects=False)
    for _ in range(6):
        if not _public_url(current):
            raise ValueError("Only public web resources can be downloaded.")
        try:
            response = requests.get(current, **request_args)
        except requests.exceptions.SSLError:
            # A small number of university recruitment hosts serve an incomplete
            # certificate chain. The URL has already passed the public-address gate;
            # retry only this public read and continue treating its content as untrusted.
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            response = requests.get(current, verify=False, **request_args)
        if response.is_redirect or response.is_permanent_redirect:
            target = urljoin(current, response.headers.get("location", ""))
            response.close()
            current = target
            continue
        break
    else:
        raise ValueError("Resource redirected too many times.")
    if response is None:
        raise ValueError("Resource could not be downloaded.")
    with response:
        response.raise_for_status()
        if not _public_url(current):
            raise ValueError("Resource redirected to a non-public address.")
        content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
        chunks = []
        size = 0
        for chunk in response.iter_content(64 * 1024):
            size += len(chunk)
            if size > MAX_RESOURCE_BYTES:
                raise ValueError("Resource is larger than the application-pack limit.")
            chunks.append(chunk)
        return b"".join(chunks), content_type, current


def _pdf_text(data: bytes) -> str:
    try:
        reader = PdfReader(io_bytes(data))
        return "\n".join(page.extract_text() or "" for page in reader.pages)[:80000]
    except Exception:
        return ""


def io_bytes(data: bytes):
    import io
    return io.BytesIO(data)


def _html_info(data: bytes, url: str) -> tuple[str, str, list[tuple[str, str]]]:
    soup = BeautifulSoup(data, "html.parser")
    for node in soup(["script", "style", "noscript", "svg"]):
        node.decompose()
    title = soup.title.get_text(" ", strip=True) if soup.title else urlparse(url).netloc
    main = soup.select_one("main, article, [role=main], #content, .content") or soup.body or soup
    text = "\n\n".join(
        " ".join(node.get_text(" ", strip=True).split())
        for node in main.select("h1,h2,h3,h4,p,li,dt,dd")
        if len(node.get_text(" ", strip=True)) > 2
    )
    if not text:
        text = " ".join(main.get_text(" ", strip=True).split())
    links = []
    for anchor in soup.select("a[href]"):
        href = urljoin(url, anchor.get("href", ""))
        label = " ".join(anchor.get_text(" ", strip=True).split()) or href.rsplit("/", 1)[-1]
        if href.startswith(("http://", "https://")):
            links.append((label[:240], href))
    return title[:300], text[:90000], links


def _attachment_name(title: str, url: str, extension: str) -> str:
    raw = title or urlparse(url).path.rsplit("/", 1)[-1] or "Research source"
    safe = re.sub(r"[^A-Za-z0-9._() -]+", "", raw).strip(" .")[:110] or "Research source"
    if not safe.lower().endswith(extension):
        safe += extension
    return safe


def collect_application_research(user_id: str, opportunity: dict, kind: str) -> dict:
    """Fetch the advert, associated PDFs and focused research pages for one application."""
    search_sources = research_opportunity(user_id, opportunity, kind)
    queue: list[dict] = []
    if opportunity.get("url"):
        queue.append(_clean_result(
            f"{opportunity.get('title', 'Job')} official advert", opportunity["url"],
            opportunity.get("description", ""), "Original job advert", "job advert",
        ))
    queue.extend(x for x in search_sources if x.get("url"))
    seen: set[str] = set()
    sources: list[dict] = []
    attachments: list[dict] = []
    advert_text = opportunity.get("description") or ""
    discovered: list[tuple[str, str, str]] = []

    while queue and len(sources) < MAX_RESOURCES:
        seed = queue.pop(0)
        url = seed.get("url", "")
        if not url or url in seen:
            continue
        seen.add(url)
        try:
            data, content_type, final_url = _download(url)
            is_pdf = content_type == "application/pdf" or data[:4] == b"%PDF"
            if is_pdf:
                text = _pdf_text(data)
                title = seed.get("title") or "PDF source"
                attachments.append({
                    "filename": _attachment_name(title, final_url, ".pdf"),
                    "data": data, "url": final_url, "title": title,
                    "kind": "official PDF" if seed.get("kind") == "job advert" else "research PDF",
                })
                source = {**seed, "url": final_url, "title": title,
                          "snippet": " ".join(text.split())[:1600],
                          "text": text[:80000], "kind": attachments[-1]["kind"]}
            else:
                title, text, links = _html_info(data, final_url)
                source = {**seed, "url": final_url, "title": title,
                          "snippet": " ".join(text.split())[:1600],
                          "text": text[:80000],
                          "kind": seed.get("kind") or "web page"}
                if seed.get("kind") == "job advert":
                    advert_text = (advert_text + "\n\n" + text)[:100000]
                    for label, href in links:
                        if href not in seen and (href.lower().split("?", 1)[0].endswith(".pdf")
                                                  or RELEVANT_LINK.search(label + " " + href)):
                            discovered.append((label, href, "job attachment"))
                        elif href not in seen and APPLY_LINK.search(label):
                            linked = _clean_result(label, href, "Linked from the job advert",
                                                   "Official application page", "job advert")
                            if linked:
                                queue.append(linked)
                elif kind == "academic":
                    for label, href in links:
                        if href.lower().split("?", 1)[0].endswith(".pdf") and RELEVANT_LINK.search(label + " " + href):
                            discovered.append((label, href, "research attachment"))
            source["retrieved_at"] = _stamp()
            sources.append(source)
        except Exception as exc:
            sources.append({**seed, "kind": "unavailable source",
                            "snippet": f"Could not retrieve this source: {type(exc).__name__}: {exc}",
                            "text": "", "retrieved_at": _stamp()})

    for label, url, source_kind in discovered[:12]:
        if len(attachments) >= 12 or url in seen:
            break
        seen.add(url)
        try:
            data, content_type, final_url = _download(url)
            if content_type == "application/pdf" or data[:4] == b"%PDF":
                text = _pdf_text(data)
                attachments.append({
                    "filename": _attachment_name(label, final_url, ".pdf"),
                    "data": data, "url": final_url, "title": label, "kind": source_kind,
                })
                sources.append({
                    "title": label, "url": final_url, "query": "Linked from collected page",
                    "snippet": " ".join(text.split())[:1600], "text": text[:30000],
                    "kind": source_kind, "retrieved_at": _stamp(),
                })
        except Exception:
            continue

    # Deduplicate identical downloaded files even when multiple URLs point to them.
    unique_attachments = []
    hashes = set()
    for attachment in attachments:
        digest = hashlib.sha256(attachment["data"]).hexdigest()
        if digest not in hashes:
            hashes.add(digest)
            unique_attachments.append(attachment)
    return {
        "sources": sources,
        "attachments": unique_attachments,
        "advert_text": advert_text[:100000],
    }


def public_source(source: dict) -> dict:
    return {key: value for key, value in source.items() if key != "text"}

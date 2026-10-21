"""Job, employer and department research with downloadable source evidence."""

from __future__ import annotations

import datetime as dt
import hashlib
import ipaddress
import re
import socket
from concurrent.futures import ThreadPoolExecutor
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
JOB_FILE = re.compile(
    r"job|position|vacanc|advert|descript|application|candidate|specification|criteria|brochure|"
    r"further[- ]particulars|information[- ]pack|role[- ]profile", re.I)
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
        if r.status_code == 202 or "anomaly" in r.text[:4000].lower():
            raise RuntimeError(
                "DuckDuckGo declined the automated search. Add a Tavily, Brave or Serper key "
                "in API settings for full web research.")
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
    subject = _subject_of(title, department)
    if kind == "academic":
        return [
            f'"{org}" "{title}" job description person specification PDF',
            f'"{org}" "{department or subject}" courses modules curriculum',
            f'"{org}" "{department or subject}" research groups research strategy',
            f'"{org}" {subject} degree programme modules',
            f'"{org}" applicant guidance equality diversity inclusion',
            f'"{org}" "{department or subject}" staff expertise facilities',
        ]
    return [
        f'"{org}" "{title}" job description selection criteria',
        f'"{org}" about strategy products services annual report',
        f'"{org}" careers values culture benefits',
        f'"{org}" diversity inclusion sustainability',
        f'"{org}" "{department or subject}" team projects priorities',
    ]


_ROLE_WORDS = re.compile(
    r"\b(?:assistant|associate|senior|junior|lead|principal|full|professor|lecturer|reader|"
    r"fellow|postdoctoral|post-doc|postdoc|research|researcher|chair|head|director|manager|"
    r"officer|in|of|and|the|a|an|for|position|post|tenure[- ]track|faculty|open[- ]rank)\b",
    re.I)


def _subject_of(title: str, department: str = "") -> str:
    """The discipline a post is in: 'Assistant Professor of Nursing' -> 'Nursing'."""
    after = re.split(r"\b(?:of|in|for)\b", title, maxsplit=1, flags=re.I)
    candidates = [after[1]] if len(after) > 1 else re.split(r"\s+[-–—|:]\s+|,", title)
    best = ""
    for part in candidates:
        part = re.sub(r"\s*[(].*$", "", part).strip()
        cleaned = " ".join(_ROLE_WORDS.sub(" ", part).split())
        if len(cleaned) > len(best):
            best = cleaned
    return best or department or title


def research_opportunity(user_id: str, opportunity: dict, kind: str | None = None) -> list[dict]:
    cfg = get_config(user_id, include_keys=True)
    provider = (cfg or {}).get("search_provider", "duckduckgo")
    key = (cfg or {}).get("search_key", "")
    track = kind or opportunity.get("career_track") or "academic"
    queries = _queries(opportunity, track)

    def run(query: str):
        try:
            return query, _search(query, provider, key, limit=5), None
        except Exception as exc:
            return query, [], exc

    sources: list[dict] = []
    seen = set()
    failures: list[str] = []
    with ThreadPoolExecutor(max_workers=len(queries) or 1) as pool:
        for query, results, error in pool.map(run, queries):
            if error is not None:
                failures.append(str(error)[:300])
                continue
            for result in results:
                if result["url"] not in seen:
                    seen.add(result["url"])
                    sources.append(result)
    if failures:
        sources.append({
            "title": "Web search unavailable", "url": "",
            "snippet": f"{len(failures)} of {len(queries)} searches failed. {failures[0]}",
            "query": "web search", "kind": "search error", "retrieved_at": _stamp(),
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


GENERIC_LINK_TEXT = {"here", "click here", "download", "pdf", "link", "view", "read more",
                     "details", "more", "this link", "attachment", "document"}


def _attachment_name(title: str, url: str, extension: str) -> str:
    from_url = urlparse(url).path.rsplit("/", 1)[-1].rsplit(".", 1)[0].replace("_", " ").replace("-", " ")
    raw = title if title and title.strip().lower() not in GENERIC_LINK_TEXT else (from_url or "Research source")
    safe = re.sub(r"[^A-Za-z0-9._() -]+", "", raw).strip(" .")[:110] or "Research source"
    if not safe.lower().endswith(extension):
        safe += extension
    return safe


ORG_KINDS = re.compile(
    r"universit|college|institute|school|academy|polytechnic|company|corporation|firm|agency|"
    r"hospital|council|authority|organi[sz]ation|consult|engineering|construction|bank|trust|"
    r"laborator|foundation|group|ltd|limited|inc\b|plc|gmbh|ministry|department", re.I)
SITE_LINK_HINTS = re.compile(
    r"about|research|school|department|faculty|programme|program|course|degree|curricul|"
    r"strategy|mission|values|career|diversity|equality|inclusion|sustainab|people|team|projects?",
    re.I)


def _json(url: str, **params) -> dict:
    response = requests.get(url, params=params or None, timeout=12,
                            headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    response.raise_for_status()
    return response.json()


def _similar(a: str, b: str) -> float:
    import difflib
    norm = lambda x: re.sub(r"[^a-z0-9 ]", "", (x or "").lower())
    return difflib.SequenceMatcher(None, norm(a), norm(b)).ratio()


def official_site(org: str) -> dict:
    """Find an organisation's official website and a Wikipedia summary, key-free.

    Wikidata is a stable public registry: it holds the official website (P856) and
    the English Wikipedia title for most universities and employers. This keeps the
    research step useful when no paid web-search key is configured and the free web
    search engines refuse automated requests.
    """
    result = {"website": "", "summary": None}
    org = (org or "").strip()
    if not org or org.lower() in {"employer", "institution not stated"}:
        return result
    try:
        hits = _json("https://www.wikidata.org/w/api.php", action="wbsearchentities", search=org,
                     language="en", format="json", limit=6, type="item").get("search", [])
    except Exception:
        return result
    sporty = re.compile(r"sports? team|athletic|football|basketball|baseball|soccer|rugby|club", re.I)
    hits = [h for h in hits if not (sporty.search(h.get("description") or "")
                                    and not sporty.search(org))]
    ranked = sorted(
        hits, key=lambda h: (-(1 if ORG_KINDS.search(h.get("description") or "") else 0),
                             -_similar(org, h.get("label", ""))))
    for hit in ranked[:3]:
        if _similar(org, hit.get("label", "")) < 0.85:        # precision over recall: a wrong employer is worse than none
            continue
        qid = hit["id"]
        try:
            entity = _json(f"https://www.wikidata.org/wiki/Special:EntityData/{qid}.json")["entities"][qid]
        except Exception:
            continue
        sites = entity.get("claims", {}).get("P856", [])
        website = ""
        for claim in sites:
            value = claim.get("mainsnak", {}).get("datavalue", {}).get("value")
            if isinstance(value, str) and value.startswith("http"):
                website = value
                break
        title = entity.get("sitelinks", {}).get("enwiki", {}).get("title")
        summary = None
        if title:
            try:
                data = _json("https://en.wikipedia.org/api/rest_v1/page/summary/"
                             + requests.utils.quote(title.replace(" ", "_"), safe=""))
                if data.get("extract"):
                    summary = {
                        "title": f"{data.get('title', title)} - Wikipedia summary",
                        "url": ((data.get("content_urls") or {}).get("desktop") or {}).get("page", ""),
                        "snippet": data["extract"][:1600], "text": data["extract"],
                        "query": f"Wikipedia: {title}", "kind": "encyclopaedia summary",
                        "retrieved_at": _stamp(),
                    }
            except Exception:
                pass
        if website or summary:
            return {"website": website, "summary": summary}
    return result


def _site_follow_ups(home_url: str, links: list[tuple[str, str]], opportunity: dict,
                     limit: int = 4) -> list[dict]:
    """The most relevant same-site pages: department, subject, about, research, careers."""
    host = urlparse(home_url).netloc.lower().removeprefix("www.")
    subject = _subject_of(opportunity.get("title") or "", opportunity.get("department") or "")
    wanted = {w for w in re.findall(r"[a-z]{4,}",
                                    f"{subject} {opportunity.get('department') or ''}".lower())}
    scored = []
    for label, href in links:
        parsed = urlparse(href)
        if parsed.netloc.lower().removeprefix("www.").split(":")[0] != host:
            continue
        if parsed.path.lower().endswith((".jpg", ".png", ".gif", ".zip", ".mp4", ".docx", ".xlsx")):
            continue
        text = f"{label} {parsed.path}".lower()
        score = 3 * sum(1 for w in wanted if w in text) + (1 if SITE_LINK_HINTS.search(text) else 0)
        if score:
            scored.append((score, href, label))
    scored.sort(key=lambda t: -t[0])
    seen, out = set(), []
    for _score, href, label in scored:
        href = href.split("#", 1)[0]
        if href in seen or href.rstrip("/") == home_url.rstrip("/"):
            continue
        seen.add(href)
        seed = _clean_result(label or href, href, "Linked from the organisation's official website",
                             "Official website crawl", "official website")
        if seed:
            out.append(seed)
        if len(out) >= limit:
            break
    return out


def _fetch_source(seed: dict) -> dict:
    """Download one source. Never raises: failures become 'unavailable source' entries."""
    url = seed.get("url", "")
    try:
        data, content_type, final_url = _download(url)
        if content_type == "application/pdf" or data[:4] == b"%PDF":
            text = _pdf_text(data)
            title = seed.get("title") or "PDF source"
            attachment_kind = "official PDF" if seed.get("kind") == "job advert" else "research PDF"
            return {
                "source": {**seed, "url": final_url, "title": title,
                           "snippet": " ".join(text.split())[:1600],
                           "text": text[:80000], "kind": attachment_kind,
                           "retrieved_at": _stamp()},
                "attachment": {"filename": _attachment_name(title, final_url, ".pdf"),
                               "data": data, "url": final_url, "title": title,
                               "kind": attachment_kind},
                "links": [],
            }
        title, text, links = _html_info(data, final_url)
        return {
            "source": {**seed, "url": final_url, "title": title,
                       "snippet": " ".join(text.split())[:1600], "text": text[:80000],
                       "kind": seed.get("kind") or "web page", "retrieved_at": _stamp()},
            "attachment": None, "links": links,
        }
    except Exception as exc:
        return {
            "source": {**seed, "kind": "unavailable source",
                       "snippet": f"Could not retrieve this source: {type(exc).__name__}: {exc}",
                       "text": "", "retrieved_at": _stamp()},
            "attachment": None, "links": [],
        }


def collect_application_research(user_id: str, opportunity: dict, kind: str) -> dict:
    """Fetch the advert, associated PDFs and focused research pages for one application.

    Searches, page downloads and attachment downloads run in parallel; reading
    them one at a time spent minutes waiting on a single slow university server.
    """
    advert_seed = None
    if opportunity.get("url"):
        advert_seed = _clean_result(
            f"{opportunity.get('title', 'Job')} official advert", opportunity["url"],
            opportunity.get("description", ""), "Original job advert", "job advert")
    with ThreadPoolExecutor(max_workers=3) as pool:
        search_future = pool.submit(research_opportunity, user_id, opportunity, kind)
        advert_future = pool.submit(_fetch_source, advert_seed) if advert_seed else None
        site_future = pool.submit(official_site, opportunity.get("org") or "")
        search_sources = search_future.result()
        advert_result = advert_future.result() if advert_future else None
        official = site_future.result()

    seen: set[str] = set()
    sources: list[dict] = []
    attachments: list[dict] = []
    advert_text = opportunity.get("description") or ""
    discovered: list[tuple[str, str, str]] = []
    follow_ups: list[dict] = []

    def absorb(result: dict, from_advert: bool) -> None:
        nonlocal advert_text
        source, attachment = result["source"], result["attachment"]
        sources.append(source)
        if attachment:
            attachments.append(attachment)
        if from_advert:
            if source.get("text"):
                advert_text = (advert_text + "\n\n" + source["text"])[:100000]
            for label, href in result["links"]:
                if href in seen:
                    continue
                is_pdf = href.lower().split("?", 1)[0].endswith(".pdf")
                if RELEVANT_LINK.search(label + " " + href) or (is_pdf and JOB_FILE.search(label + " " + href)):
                    discovered.append((label, href, "job attachment"))
                elif APPLY_LINK.search(label):
                    linked = _clean_result(label, href, "Linked from the job advert",
                                           "Official application page", "job advert")
                    if linked:
                        follow_ups.append(linked)
        elif kind == "academic":
            for label, href in result["links"]:
                if href.lower().split("?", 1)[0].endswith(".pdf") and RELEVANT_LINK.search(label + " " + href):
                    discovered.append((label, href, "research attachment"))

    if advert_result:
        seen.add(advert_seed["url"])
        absorb(advert_result, True)

    if official.get("summary"):
        sources.append(official["summary"])
    if official.get("website"):
        homepage = _clean_result(f"{opportunity.get('org')} official website", official["website"],
                                 "Official website found through Wikidata",
                                 "Wikidata official website", "official website")
        home_result = _fetch_source(homepage) if homepage else None
        if home_result:
            seen.add(homepage["url"])
            sources.append(home_result["source"])
            for extra in _site_follow_ups(home_result["source"].get("url") or official["website"],
                                          home_result["links"], opportunity):
                follow_ups.append(extra)

    unique = []
    for seed in follow_ups[:3] + [x for x in search_sources
                                  if x.get("url") and x.get("kind") != "search error"]:
        if seed["url"] not in seen:
            seen.add(seed["url"])
            unique.append(seed)
    for seed in follow_ups[3:]:
        if seed["url"] not in seen and seed.get("kind") == "official website":
            seen.add(seed["url"])
            unique.append(seed)
    unique = unique[:max(0, MAX_RESOURCES - len(sources))]
    with ThreadPoolExecutor(max_workers=8) as pool:
        for seed, result in zip(unique, pool.map(_fetch_source, unique)):
            absorb(result, seed.get("kind") == "job advert")
    for error in [x for x in search_sources if x.get("kind") == "search error"]:
        sources.append(error)

    def fetch_attachment(entry):
        label, url, source_kind = entry
        try:
            data, content_type, final_url = _download(url)
            if content_type == "application/pdf" or data[:4] == b"%PDF":
                return label, final_url, source_kind, data
        except Exception:
            pass
        return None

    wanted = []
    for label, url, source_kind in discovered:
        if url not in seen and len(wanted) < 12:
            seen.add(url)
            wanted.append((label, url, source_kind))
    with ThreadPoolExecutor(max_workers=6) as pool:
        for found in pool.map(fetch_attachment, wanted):
            if not found or len(attachments) >= 12:
                continue
            label, final_url, source_kind, data = found
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

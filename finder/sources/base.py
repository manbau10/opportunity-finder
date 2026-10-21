# -*- coding: utf-8 -*-
"""Shared HTTP helpers for the source adapters.

Every adapter goes through :func:`get` / :func:`get_json`. They are safe to call
from many threads at once: each host is rate-limited independently, so different
job boards are fetched in parallel while any single board still gets a polite
gap between requests.
"""

from __future__ import annotations

import hashlib
import html
import re
import threading
import time

import requests

from ..config import POLITE_DELAY, REQUEST_TIMEOUT, USER_AGENT

_local = threading.local()
_host_locks: dict[str, threading.Lock] = {}
_host_locks_guard = threading.Lock()
_last_call: dict[str, float] = {}

RETRY_STATUS = {429, 500, 502, 503, 504}


def session() -> requests.Session:
    """One Session per thread: requests.Session is not safe to share."""
    s = getattr(_local, "session", None)
    if s is None:
        s = requests.Session()
        s.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-GB,en;q=0.9",
        })
        adapter = requests.adapters.HTTPAdapter(pool_connections=8, pool_maxsize=8)
        s.mount("https://", adapter)
        s.mount("http://", adapter)
        _local.session = s
    return s


def _host_of(url: str) -> str:
    return re.sub(r"^https?://([^/]+).*$", r"\1", url)


def _host_lock(host: str) -> threading.Lock:
    with _host_locks_guard:
        lock = _host_locks.get(host)
        if lock is None:
            lock = _host_locks[host] = threading.Lock()
        return lock


def _polite(host: str, delay: float) -> None:
    """Block until `delay` seconds have passed since the last call to this host."""
    with _host_lock(host):
        wait = delay - (time.time() - _last_call.get(host, 0.0))
        if wait > 0:
            time.sleep(wait)
        _last_call[host] = time.time()


def get(url: str, retries: int = 1, delay: float | None = None,
        **kwargs) -> requests.Response | None:
    """GET with per-host politeness and one retry. None on failure instead of raising."""
    host = _host_of(url)
    timeout = kwargs.pop("timeout", REQUEST_TIMEOUT)
    pause = POLITE_DELAY if delay is None else delay
    for attempt in range(retries + 1):
        _polite(host, pause)
        try:
            r = session().get(url, timeout=timeout, **kwargs)
        except requests.RequestException:
            if attempt < retries:
                time.sleep(1.2 * (attempt + 1))
                continue
            return None
        if r.status_code in RETRY_STATUS and attempt < retries:
            time.sleep(1.5 * (attempt + 1))
            continue
        if r.status_code != 200:
            return None
        ctype = r.headers.get("content-type", "").lower()
        if "json" in ctype:
            r.encoding = "utf-8"          # JSON is UTF-8 by definition
        elif not r.encoding or r.encoding.lower() in ("iso-8859-1", "ascii"):
            r.encoding = r.apparent_encoding or "utf-8"
        return r
    return None


def get_json(url: str, **kwargs):
    """GET and decode JSON. None on any failure."""
    headers = kwargs.pop("headers", {}) or {}
    headers.setdefault("Accept", "application/json")
    r = get(url, headers=headers, **kwargs)
    if r is None:
        return None
    try:
        return r.json()
    except ValueError:
        return None


_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")


def clean(text: str | None) -> str:
    if not text:
        return ""
    text = _TAG.sub(" ", str(text))
    text = html.unescape(text)
    return _WS.sub(" ", text).strip()


def make_id(source: str, url: str) -> str:
    key = (source + "|" + (url or "")).lower().strip()
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:20]

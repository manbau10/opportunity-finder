# -*- coding: utf-8 -*-
"""Shared HTTP helpers for the source adapters."""

from __future__ import annotations

import hashlib
import html
import re
import time

import requests

from ..config import POLITE_DELAY, REQUEST_TIMEOUT, USER_AGENT

_session = None
_last_call: dict[str, float] = {}


def session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-GB,en;q=0.9",
        })
    return _session


def get(url: str, **kwargs) -> requests.Response | None:
    """GET with per-host politeness. Returns None on failure instead of raising."""
    host = re.sub(r"^https?://([^/]+).*$", r"\1", url)
    wait = POLITE_DELAY - (time.time() - _last_call.get(host, 0.0))
    if wait > 0:
        time.sleep(wait)
    try:
        r = session().get(url, timeout=kwargs.pop("timeout", REQUEST_TIMEOUT), **kwargs)
    except requests.RequestException:
        _last_call[host] = time.time()
        return None
    _last_call[host] = time.time()
    if r.status_code != 200:
        return None
    if not r.encoding or r.encoding.lower() in ("iso-8859-1", "ascii"):
        r.encoding = r.apparent_encoding or "utf-8"
    return r


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

# -*- coding: utf-8 -*-
"""The application secret: signs login cookies and encrypts stored API keys.

A hosted deployment sets SECRET_KEY in its environment. When running on a PC with no
environment set up, a random key is created once and kept beside the database, so
saving API settings works out of the box and is not protected by a key that is public
in the source code.
"""

from __future__ import annotations

import os
import secrets

from .config import DATA_DIR

_cached: str | None = None


def get_secret_key() -> str:
    global _cached
    if _cached:
        return _cached
    value = os.environ.get("SECRET_KEY", "").strip()
    if not value:
        path = os.path.join(DATA_DIR, "secret.key")
        try:
            with open(path, "r", encoding="ascii") as handle:
                value = handle.read().strip()
        except OSError:
            value = ""
        if not value:
            value = secrets.token_hex(32)
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(path, "w", encoding="ascii") as handle:
                handle.write(value)
            try:
                os.chmod(path, 0o600)
            except OSError:
                pass
    _cached = value
    return value

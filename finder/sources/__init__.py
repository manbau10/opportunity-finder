# -*- coding: utf-8 -*-
"""Source adapters. Each exposes fetch(log) -> list[dict]."""

from . import chronicle, euraxess, fellowships, jobsacuk, unijobs

REGISTRY = {
    "unijobs": unijobs,
    "chronicle": chronicle,
    "jobsacuk": jobsacuk,
    "euraxess": euraxess,
    "fellowships": fellowships,
}

# -*- coding: utf-8 -*-
"""Source adapters. Each exposes fetch(log) -> list[dict]."""

from . import (academictransfer, ajo, chronicle, euraxess, fellowships, insidehighered,
               jobsacuk, sciencecareers, unijobs)

REGISTRY = {
    "unijobs": unijobs,
    "chronicle": chronicle,
    "insidehighered": insidehighered,
    "jobsacuk": jobsacuk,
    "sciencecareers": sciencecareers,
    "ajo": ajo,
    "academictransfer": academictransfer,
    "euraxess": euraxess,
    "fellowships": fellowships,
}

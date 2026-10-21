# -*- coding: utf-8 -*-
"""Inside Higher Ed Careers - United States faculty, research and staff posts."""

from __future__ import annotations

from .. import queries
from .madgex import fetch_board

NAME = "Inside Higher Ed"
FEED = "https://careers.insidehighered.com/jobsrss/?keywords="


def fetch(log=print) -> list[dict]:
    return fetch_board(FEED, NAME, "insidehighered", queries.academic_queries(), log,
                       country_hint="United States")

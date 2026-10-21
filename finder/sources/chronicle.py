# -*- coding: utf-8 -*-
"""
The Chronicle of Higher Education job board (jobs.chronicle.com).

Best single source for United States and Canadian faculty and postdoc posts.
"""

from __future__ import annotations

from .. import queries
from .madgex import fetch_board

NAME = "Chronicle of Higher Ed"
FEED = "https://jobs.chronicle.com/jobsrss/?keywords="


def fetch(log=print) -> list[dict]:
    return fetch_board(FEED, NAME, "chronicle", queries.academic_queries(), log,
                       country_hint="United States")

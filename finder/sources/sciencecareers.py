# -*- coding: utf-8 -*-
"""Science Careers (AAAS) - research, postdoctoral and faculty posts in the sciences."""

from __future__ import annotations

from .. import queries
from .madgex import fetch_board

NAME = "Science Careers"
FEED = "https://jobs.sciencecareers.org/jobsrss/?keywords="


def fetch(log=print) -> list[dict]:
    return fetch_board(FEED, NAME, "sciencecareers", queries.academic_queries(), log)

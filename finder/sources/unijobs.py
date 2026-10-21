# -*- coding: utf-8 -*-
"""
Times Higher Education unijobs (timeshighereducation.com/unijobs).

Global coverage with a strong UK / Australia / New Zealand bias. Keyword RSS
returns the newest postings per query.
"""

from __future__ import annotations

from .. import queries
from .madgex import fetch_board

NAME = "THE unijobs"
FEED = "https://www.timeshighereducation.com/unijobs/jobsrss/?keywords="


def fetch(log=print) -> list[dict]:
    return fetch_board(FEED, NAME, "unijobs", queries.academic_queries(), log)

# -*- coding: utf-8 -*-
"""Runtime configuration: where to look and what to look for."""

import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.environ.get("OPPFINDER_DATA_DIR") or os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "opportunities.db")

USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/122.0 Safari/537.36")
REQUEST_TIMEOUT = 25
POLITE_DELAY = 0.45         # seconds between requests to the same host

# Search phrases sent to the keyword-driven sources. Kept deliberately broad;
# the scorer does the fine filtering afterwards.
SEARCH_QUERIES = [
    # core discipline
    "construction management",
    "construction engineering",
    "civil engineering",
    "infrastructure engineering",
    "infrastructure asset management",
    "asset management engineering",
    "built environment",
    "engineering management",
    "project management construction",
    # water
    "water engineering",
    "water infrastructure",
    "water resources",
    "water distribution network",
    "wastewater engineering",
    # adjacent civil sub-fields
    "structural engineering",
    "transport infrastructure",
    "geotechnical engineering",
    "construction materials",
    "environmental engineering",
    "urban infrastructure",
    # digital / methods within the discipline
    "construction informatics",
    "digital construction",
    "building information modelling",
    "digital twin infrastructure",
    "sustainable construction",
    "resilient infrastructure",
    "smart infrastructure",
    # role-shaped phrasings, which several boards index separately
    "postdoctoral civil engineering",
    "postdoctoral construction",
    "postdoctoral water",
    "research fellow infrastructure",
    "assistant professor civil engineering",
    "assistant professor construction",
    "lecturer construction",
    "lecturer civil engineering",
]

# Terms used to keep or drop items from the broad crawl sources (Euraxess),
# which return every discipline.
CRAWL_KEEP_TERMS = [
    "civil", "construction", "infrastructure", "water", "structural",
    "geotechnic", "transport", "pavement", "hydrolog", "hydraulic",
    "built environment", "building", "urban", "asset management",
    "project management", "wastewater", "sewer", "pipeline", "bridge",
    "concrete", "materials engineering", "environmental engineering",
    "sustainab", "resilien", "engineering management", "architectur",
]

# How many result pages to pull per source per refresh.
#
# EURAXESS is walked newest-first, ten postings per page, so 60 pages reach
# back roughly the last week or two of European research posts.
LIMITS = {
    "jobs_ac_uk_pages": 3,       # 25 results per page, per query
    "euraxess_pages": 60,        # ten postings per page, newest first
    "detail_fetch_max": 300,     # detail pages fetched per refresh, for deadlines
    "detail_min_score": 40,      # only open adverts scoring at least this
}

# Anything below this is stored but hidden behind the "show everything" toggle.
DISPLAY_MIN_SCORE = 30

SOURCES_ENABLED = {
    "unijobs": True,      # Times Higher Education unijobs - global
    "chronicle": True,    # Chronicle of Higher Education - US / Canada
    "jobsacuk": True,     # jobs.ac.uk - UK and international
    "euraxess": True,     # EURAXESS - Europe
    "insidehighered": True,   # Inside Higher Ed Careers - US
    "sciencecareers": True,   # Science Careers (AAAS) - sciences, global
    "ajo": True,              # AcademicJobsOnline - US / Canada
    "academictransfer": True, # AcademicTransfer - Netherlands
    "fellowships": True,  # curated register of named fellowship schemes
}

# -*- coding: utf-8 -*-
"""Human-readable list of every job source, for the Sources page."""

from __future__ import annotations

from . import store

ACADEMIC = [
    ("unijobs", "Times Higher Education unijobs", "UK, Australia, New Zealand and worldwide", "https://www.timeshighereducation.com/unijobs"),
    ("jobsacuk", "jobs.ac.uk", "United Kingdom, plus Europe and international", "https://www.jobs.ac.uk"),
    ("chronicle", "Chronicle of Higher Education", "United States and Canada", "https://jobs.chronicle.com"),
    ("insidehighered", "Inside Higher Ed Careers", "United States", "https://careers.insidehighered.com"),
    ("sciencecareers", "Science Careers (AAAS)", "Sciences, worldwide", "https://jobs.sciencecareers.org"),
    ("ajo", "AcademicJobsOnline", "United States and Canada", "https://academicjobsonline.org"),
    ("academictransfer", "AcademicTransfer", "Netherlands", "https://www.academictransfer.com"),
    ("euraxess", "EURAXESS", "Europe (European Commission research portal)", "https://euraxess.ec.europa.eu"),
    ("fellowships", "Fellowship register", "Named fellowship schemes (MSCA, UKRI, Banting, DECRA ...)", ""),
]

INDUSTRY = [
    ("uk_reed", "Reed", "United Kingdom", "https://www.reed.co.uk"),
    ("nhs_jobs", "NHS Jobs (nursing and midwifery)", "United Kingdom", "https://www.jobs.nhs.uk"),
    ("us_govjobs", "GovernmentJobs", "United States (city, county, state, federal)", "https://www.governmentjobs.com"),
    ("ca_jobbank", "Job Bank", "Canada", "https://www.jobbank.gc.ca"),
    ("se_platsbanken", "Platsbanken (Arbetsformedlingen)", "Sweden", "https://arbetsformedlingen.se/platsbanken"),
    ("ch_jobsch", "jobs.ch", "Switzerland", "https://www.jobs.ch"),
    ("arbeitnow", "Arbeitnow", "Germany and the DACH region", "https://www.arbeitnow.com"),
    ("ng_jobberman", "Jobberman", "Nigeria", "https://www.jobberman.com"),
    ("gh_jobberman", "Jobberman Ghana", "Ghana", "https://www.jobberman.com.gh"),
    ("ke_brightermonday", "BrighterMonday", "Kenya", "https://www.brightermonday.co.ke"),
    ("za_careers24", "Careers24", "South Africa", "https://www.careers24.com"),
    ("himalayas", "Himalayas", "Remote jobs, worldwide", "https://himalayas.app"),
    ("remotive", "Remotive", "Remote jobs, worldwide", "https://remotive.com"),
    ("jobicy", "Jobicy", "Remote jobs, by country", "https://jobicy.com"),
    ("workingnomads", "Working Nomads", "Remote jobs, worldwide", "https://www.workingnomads.com"),
    ("remoteok", "Remote OK", "Remote jobs, worldwide", "https://remoteok.com"),
]

OPTIONAL = [
    ("adzuna", "Adzuna", "19 countries (set ADZUNA_APP_ID and ADZUNA_APP_KEY to switch on)", "https://developer.adzuna.com"),
]


def source_status() -> dict:
    """Stored posting counts for every source, grouped by career track."""
    conn = store.connect()
    try:
        rows = conn.execute(
            "SELECT source_key, career_track, COUNT(*) AS n, MAX(last_seen) AS last "
            "FROM opportunities GROUP BY source_key, career_track").fetchall()
    finally:
        conn.close()
    counts: dict[str, dict] = {}
    for row in rows:
        entry = counts.setdefault(row["source_key"], {"n": 0, "last": ""})
        entry["n"] += row["n"]
        entry["last"] = max(entry["last"], row["last"] or "")

    def build(entries, track):
        out = []
        for key, name, coverage, url in entries:
            match = {k: v for k, v in counts.items() if k == key or k.startswith(key + "_")}
            n = sum(v["n"] for v in match.values())
            last = max((v["last"] for v in match.values()), default="")
            out.append({"key": key, "name": name, "coverage": coverage, "url": url,
                        "track": track, "postings": n, "last_seen": last[:10]})
        return out

    return {"academic": build(ACADEMIC, "academic"),
            "industry": build(INDUSTRY + OPTIONAL, "industry")}

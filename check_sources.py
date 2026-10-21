# -*- coding: utf-8 -*-
"""
Live health check of every job source.

    python check_sources.py            quick check (2 searches per board, a few seconds each)
    python check_sources.py --full     exactly what a refresh does, per source

Prints one line per source: OK with the number of postings, EMPTY when the board
answered with nothing, or FAIL with the error. Run it when a board seems to have
gone quiet: it tells you whether the site changed or your connection is at fault.
"""

from __future__ import annotations

import argparse
import sys
import time

from finder import industry_sources, queries
from finder.config import LIMITS
from finder.sources import REGISTRY

QUICK_ACADEMIC = ["civil engineering", "construction management"]
QUICK_TITLES = ["civil engineer", "project manager"]


def _quiet(*_args, **_kwargs) -> None:
    return None


def run(label: str, call) -> tuple[str, int, float]:
    began = time.time()
    try:
        items = call()
    except Exception as exc:                      # report, never crash the whole check
        return f"FAIL  {type(exc).__name__}: {exc}", 0, time.time() - began
    status = "OK   " if items else "EMPTY"
    return status, len(items), time.time() - began


def main() -> int:
    parser = argparse.ArgumentParser(description="Check every job source")
    parser.add_argument("--full", action="store_true", help="use the full refresh settings")
    args = parser.parse_args()

    if not args.full:
        queries.academic_queries = lambda: list(QUICK_ACADEMIC)       # type: ignore[assignment]
        LIMITS["euraxess_pages"] = 5
    titles = QUICK_TITLES if not args.full else (queries.industry_titles() or QUICK_TITLES)

    results = []
    print("\nAcademic boards")
    for key, module in REGISTRY.items():
        status, n, seconds = run(module.NAME, lambda m=module: m.fetch(_quiet))
        print(f"  {status}  {n:5d}  {seconds:5.1f}s  {module.NAME}")
        results.append(status.strip())

    print("\nIndustry boards")
    for key, label, country, fn in industry_sources.SOURCES:
        status, n, seconds = run(label, lambda f=fn: f(titles, _quiet))
        print(f"  {status}  {n:5d}  {seconds:5.1f}s  {label} ({country})")
        results.append(status.strip())

    failed = sum(1 for r in results if r.startswith("FAIL"))
    empty = sum(1 for r in results if r == "EMPTY")
    print(f"\n{len(results) - failed - empty} working, {empty} empty, {failed} failed.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

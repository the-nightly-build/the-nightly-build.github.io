"""Orchestrate one crawl: candidates -> fetched catalogs -> trusted records.

Pure given its inputs: pass the candidate list, the blocklist, and a
fetch_text(url) callable, and get back sorted press and edition records plus a
build report. The real entry point injects a network fetcher; tests inject a
dictionary-backed one, so the whole pipeline runs offline.
"""

from __future__ import annotations

import datetime as dt
import json

from . import ingest, models
from .http import FetchTooLarge
from .ingest import SkipPress
from .report import BuildReport


def crawl(candidates, *, blocked, fetch_text, forks_discovered=0):
    blocked_ids = {entry.strip().lower() for entry in blocked if entry.strip()}
    report = BuildReport(forks_discovered=forks_discovered, candidates=len(candidates))
    presses = []
    editions = []

    for candidate in candidates:
        if candidate.repository.lower() in blocked_ids:
            report.skipped(candidate.repository, models.BLOCKED)
            continue
        try:
            text = fetch_text(ingest.catalog_url(candidate))
        except FetchTooLarge:
            report.skipped(candidate.repository, models.CATALOG_TOO_LARGE)
            continue
        except Exception:
            report.skipped(candidate.repository, models.CATALOG_FETCH_FAILED)
            continue
        try:
            catalog = json.loads(text)
        except ValueError:
            report.skipped(candidate.repository, models.INVALID_CATALOG_JSON)
            continue
        if not isinstance(catalog, dict):
            report.skipped(candidate.repository, models.INVALID_CATALOG_JSON)
            continue
        if ingest.protocol_status(catalog.get("protocol")) == "warn":
            report.warnings += 1
        try:
            press, press_editions = ingest.ingest(candidate, catalog)
        except SkipPress as skip:
            report.skipped(candidate.repository, skip.code)
            continue
        presses.append(press)
        editions.extend(press_editions)
        report.indexed(candidate.repository, len(press_editions))

    # Sort stably: title ascending, then publication date descending, so ties
    # on date fall back to title (doc §38-39). Never popularity (invariant 17).
    presses.sort(key=lambda p: p.title.lower())
    presses.sort(key=lambda p: p.latest_published or dt.date.min, reverse=True)
    editions.sort(key=lambda e: e.title.lower())
    editions.sort(key=lambda e: e.published, reverse=True)
    return presses, editions, report

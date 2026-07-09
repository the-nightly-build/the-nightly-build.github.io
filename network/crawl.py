"""Orchestrate one crawl: candidates -> fetched catalogs -> trusted records.

Pure given its inputs: pass the candidate list, the blocklist, and a
fetch_text(url) callable, and get back sorted press and edition records plus a
build report. The real entry point injects a network fetcher; tests inject a
dictionary-backed one, so the whole pipeline runs offline.
"""

from __future__ import annotations

import json
from dataclasses import replace

from . import ingest, models
from .http import FetchTooLarge
from .ingest import SkipPress
from .report import BuildReport


def crawl(
    candidates, *, blocked, fetch_text, fetch_author_name=None, forks_discovered=0
):
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
        # Enrich with the author's GitHub display name (one extra call per
        # indexed author); falls back to the handle already on the records.
        if fetch_author_name is not None:
            name = fetch_author_name(candidate.owner)
            if name and name != press.author_name:
                press = replace(press, author_name=name)
                press_editions = [replace(e, author_name=name) for e in press_editions]
        presses.append(press)
        editions.extend(press_editions)
        report.indexed(candidate.repository, len(press_editions))

    # Authors are ordered by GitHub stars (the directory's one popularity lens),
    # ties broken by name; articles are strictly chronological, newest first.
    presses.sort(key=lambda p: p.author_name.lower())
    presses.sort(key=lambda p: p.stars, reverse=True)
    editions.sort(key=lambda e: e.title.lower())
    editions.sort(key=lambda e: e.published, reverse=True)
    return presses, editions, report

"""Orchestrate one crawl: candidates -> fetched catalogs -> trusted records.

Pure given its inputs: pass the candidate list, the blocklist, and a
fetch_text(url) callable, and get back sorted author and article records plus a
build report. The real entry point injects a directory fetcher; tests inject a
dictionary-backed one, so the whole pipeline runs offline.
"""

from __future__ import annotations

import json
from dataclasses import replace

from . import ingest, models
from .http import FetchTooLarge
from .ingest import SkipAuthor
from .report import BuildReport


def crawl(
    candidates, *, blocked, fetch_text, fetch_author_name=None, forks_discovered=0
):
    blocked_ids = {entry.strip().lower() for entry in blocked if entry.strip()}
    report = BuildReport(forks_discovered=forks_discovered, candidates=len(candidates))
    authors = []
    articles = []

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
            author, author_articles = ingest.ingest(candidate, catalog)
        except SkipAuthor as skip:
            report.skipped(candidate.repository, skip.code)
            continue
        # Enrich with the author's GitHub display name (one extra call per
        # indexed author); falls back to the handle already on the records.
        if fetch_author_name is not None:
            name = fetch_author_name(candidate.owner)
            if name and name != author.author_name:
                author = replace(author, author_name=name)
                author_articles = [
                    replace(e, author_name=name) for e in author_articles
                ]
        authors.append(author)
        articles.extend(author_articles)
        report.indexed(candidate.repository, len(author_articles))

    # Authors are ordered by GitHub stars (the directory's one popularity lens),
    # ties broken by name; articles are strictly chronological, newest first.
    authors.sort(key=lambda p: p.author_name.lower())
    authors.sort(key=lambda p: p.stars, reverse=True)
    articles.sort(key=lambda e: e.title.lower())
    articles.sort(key=lambda e: e.published, reverse=True)
    return authors, articles, report

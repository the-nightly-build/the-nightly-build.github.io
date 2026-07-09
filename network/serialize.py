"""Serialize trusted records into the network's public JSON outputs.

Three files, all metadata only (never full text, doc invariant 4):
  presses.json  the press directory
  search.json   every indexed edition, for client-side article search
  network.json  build metadata (generated time + counts)

Given already-sorted records the string output is deterministic, so a rebuild
with the same inputs produces byte-identical presses.json / search.json.
"""

from __future__ import annotations

import json


def _iso(value):
    return value.isoformat() if value is not None else None


def press_to_public(press):
    return {
        "owner": press.owner,
        "author_name": press.author_name,
        "description": press.description,
        "url": press.url,
        "stars": press.stars,
        "article_count": press.edition_count,
        "latest_published": _iso(press.latest_published),
    }


def edition_to_search(edition):
    return {
        "title": edition.title,
        "dek": edition.dek,
        "section": edition.section or edition.series_name,
        "author_name": edition.author_name,
        "reading_minutes": edition.reading_minutes,
        "published": _iso(edition.published),
        "url": edition.url,
    }


def _dump(data):
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def presses_json(presses):
    return _dump([press_to_public(p) for p in presses])


def search_json(editions):
    return _dump([edition_to_search(e) for e in editions])


def network_json(report, *, generated):
    data = {"generated": generated, **report.to_dict()}
    return _dump(data)

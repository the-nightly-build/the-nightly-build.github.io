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
        "id": press.id,
        "repository": press.repository,
        "owner": press.owner,
        "title": press.title,
        "description": press.description,
        "url": press.url,
        "series_count": press.series_count,
        "edition_count": press.edition_count,
        "latest_published": _iso(press.latest_published),
        "stars": press.stars,
        "tags": list(press.tags),
    }


def edition_to_search(edition):
    return {
        "title": edition.title,
        "dek": edition.dek,
        "tags": list(edition.tags),
        "series": edition.series_name,
        "section": edition.section,
        "press": edition.press_title,
        "repository": edition.repository,
        "published": _iso(edition.published),
        "reading_minutes": edition.reading_minutes,
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

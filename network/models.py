"""Normalized, trusted internal records for the network directory.

Everything the crawler reads (fork configuration, catalog JSON, titles, deks,
tags) is untrusted until it has been validated and escaped into one of these
records. Rendering consumes records, never raw catalog objects (doc §49).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass


@dataclass(frozen=True)
class PressRecord:
    id: str  # normalized identity, e.g. "github:ryansaxe/the-nightly-build"
    repository: (
        str  # GitHub full name, display casing, e.g. "RyanSaxe/the-nightly-build"
    )
    owner: str  # GitHub handle; the network identity (one fork per user)
    author_name: str  # GitHub display name, falls back to the handle
    title: str
    description: str
    url: str  # public site root, one trailing slash
    protocol: str
    catalog_generated_at: dt.datetime
    series_count: int
    edition_count: int
    latest_published: dt.date | None
    stars: int
    tags: tuple[str, ...]


@dataclass(frozen=True)
class EditionRecord:
    id: str  # "<press_id>:<series_id>/<slug>"
    press_id: str
    repository: str
    author_name: str  # byline on the network
    title: str
    dek: str
    series_id: str
    series_name: str
    section: str | None
    tags: tuple[str, ...]
    published: dt.date
    reading_minutes: int
    url: str  # absolute URL of the original edition on the press's site


# Per-press outcome codes for the build report (doc §28). A press is either
# INDEXED or skipped with exactly one reason. Discovery-level filters
# (archived / disabled / non-fork) are dropped before catalog handling and are
# not press outcomes.
INDEXED = "INDEXED"
BLOCKED = "BLOCKED"
CATALOG_FETCH_FAILED = "CATALOG_FETCH_FAILED"
CATALOG_TOO_LARGE = "CATALOG_TOO_LARGE"
INVALID_CATALOG_JSON = "INVALID_CATALOG_JSON"
UNSUPPORTED_PROTOCOL = "UNSUPPORTED_PROTOCOL"
OPTED_OUT = "OPTED_OUT"
INVALID_CATALOG = "INVALID_CATALOG"

SKIP_REASONS = (
    BLOCKED,
    CATALOG_FETCH_FAILED,
    CATALOG_TOO_LARGE,
    INVALID_CATALOG_JSON,
    UNSUPPORTED_PROTOCOL,
    OPTED_OUT,
    INVALID_CATALOG,
)

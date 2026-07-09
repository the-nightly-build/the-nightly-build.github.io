"""Fetch, validate, and normalize one press's catalog into trusted records.

The catalog is the sole ingestion contract (doc invariant 3). Because the
press's public URL is now *derived* at build time (never configured), the
catalog is self-consistent by construction, so V1 needs no site.yaml fetch and
no url cross-check: we derive the Pages URL from owner/repo, read the catalog
there, and require only that it is opted in and structurally valid.
"""

from __future__ import annotations

import datetime as dt
import re

from . import models
from .discovery import press_id

# Field length ceilings on untrusted strings (defense in depth; rendering also
# escapes). Generous enough for real content, bounded enough to resist abuse.
MAX_TITLE = 200
MAX_DEK = 400
MAX_DESC = 280
MAX_NAME = 100
MAX_SECTION = 80
MAX_TAG = 40
MAX_TAGS_PER_EDITION = 12
MAX_PRESS_TAGS = 8

REQUIRED_TOP_LEVEL = (
    "generated",
    "protocol",
    "site_title",
    "network",
    "series",
    "editions",
)


class SkipPress(Exception):
    """Raised to skip a press with a build-report reason code (models.*)."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def pages_root(candidate):
    # Standard GitHub Pages project URL. Owner is lowercased for the hostname;
    # the repo name keeps its casing in the path. Custom domains are out of
    # scope for V1 auto-discovery.
    return f"https://{candidate.owner.lower()}.github.io/{candidate.name}/"


def catalog_url(candidate):
    return pages_root(candidate) + "catalog.json"


def protocol_status(protocol):
    # Accept 1.x where x >= 2; warn on an unknown-but-compatible higher minor.
    if not isinstance(protocol, str):
        return "unsupported"
    parts = protocol.split(".")
    if len(parts) != 2 or parts[0] != "1":
        return "unsupported"
    try:
        minor = int(parts[1])
    except ValueError:
        return "unsupported"
    if minor < 2:
        return "unsupported"
    if minor in (2, 3):
        return "ok"
    return "warn"


def _clean_str(value, max_len):
    if not isinstance(value, str):
        return ""
    return value.strip()[:max_len]


def _clean_tags(value, *, cap):
    if not isinstance(value, list):
        return ()
    out = []
    seen = set()
    for tag in value:
        if not isinstance(tag, str):
            continue
        norm = tag.strip().lower()[:MAX_TAG]
        if norm and norm not in seen:
            seen.add(norm)
            out.append(norm)
        if len(out) >= cap:
            break
    return tuple(out)


def _parse_date(value):
    if not isinstance(value, str):
        return None
    try:
        return dt.date.fromisoformat(value)
    except ValueError:
        return None


def _parse_generated(value):
    if not isinstance(value, str):
        return None
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


# Every edition link is the derived press root plus this exact local shape.
# The catalog never supplies an absolute URL, and a hostile `path` (scheme,
# traversal, query, fragment) must never leak into an outbound link, so the
# path is validated against the slug charset the protocol already mandates.
_EDITION_PATH = re.compile(r"^/library/[a-z0-9-]+/[a-z0-9-]+\.html$")


def _top_tags(editions_meta):
    counts = {}
    for meta in editions_meta:
        for tag in _clean_tags(meta.get("tags"), cap=MAX_TAGS_PER_EDITION):
            counts[tag] = counts.get(tag, 0) + 1
    ranked = sorted(counts, key=lambda t: (-counts[t], t))
    return tuple(ranked[:MAX_PRESS_TAGS])


def validate_catalog_1_2(candidate, catalog):
    """Validate a protocol-1.2 catalog and return (PressRecord, [EditionRecord]).

    Raises SkipPress(code) on any structural or opt-in failure.
    """
    for key in REQUIRED_TOP_LEVEL:
        if key not in catalog:
            raise SkipPress(models.INVALID_CATALOG)
    if not isinstance(catalog["series"], list) or not isinstance(
        catalog["editions"], list
    ):
        raise SkipPress(models.INVALID_CATALOG)
    if not isinstance(catalog["network"], dict):
        raise SkipPress(models.INVALID_CATALOG)
    # Opt-out: a press is listed unless it explicitly set publish: false.
    if catalog["network"].get("publish") is False:
        raise SkipPress(models.OPTED_OUT)
    generated = _parse_generated(catalog["generated"])
    if generated is None:
        raise SkipPress(models.INVALID_CATALOG)

    pid = press_id(candidate.repository)
    title = _clean_str(catalog["site_title"], MAX_TITLE) or candidate.repository
    # The press root is derived solely from GitHub identity; nothing the catalog
    # says can redirect a reader off the press's own site.
    root = pages_root(candidate)
    series_by_id = {
        s.get("id"): s for s in catalog["series"] if isinstance(s, dict) and s.get("id")
    }

    editions = []
    dates = []
    metas = []
    for ed in catalog["editions"]:
        if not isinstance(ed, dict) or ed.get("draft"):
            continue
        published = _parse_date(ed.get("date"))
        path = ed.get("path")
        series_id = ed.get("series")
        slug = ed.get("slug")
        if published is None or not isinstance(path, str) or not series_id or not slug:
            continue
        if not _EDITION_PATH.match(path):
            continue
        metas.append(ed)
        dates.append(published)
        cfg = series_by_id.get(series_id, {})
        rm = ed.get("reading_minutes")
        editions.append(
            models.EditionRecord(
                id=f"{pid}:{series_id}/{slug}",
                press_id=pid,
                repository=candidate.repository,
                author_name=candidate.owner,
                title=_clean_str(ed.get("title"), MAX_TITLE) or str(slug),
                dek=_clean_str(ed.get("dek"), MAX_DEK),
                series_id=str(series_id),
                series_name=_clean_str(cfg.get("name"), MAX_NAME) or str(series_id),
                section=_clean_str(cfg.get("section"), MAX_SECTION) or None,
                tags=_clean_tags(ed.get("tags"), cap=MAX_TAGS_PER_EDITION),
                published=published,
                reading_minutes=int(rm)
                if isinstance(rm, (int, float)) and rm > 0
                else 1,
                url=root.rstrip("/") + path,
            )
        )

    press = models.PressRecord(
        id=pid,
        repository=candidate.repository,
        owner=candidate.owner,
        author_name=candidate.owner,
        title=title,
        description=_clean_str(catalog["network"].get("description"), MAX_DESC),
        url=root,
        protocol=catalog["protocol"],
        catalog_generated_at=generated,
        series_count=len(catalog["series"]),
        edition_count=len(editions),
        latest_published=max(dates) if dates else None,
        stars=candidate.stars,
        tags=_top_tags(metas),
    )
    return press, editions


PROTOCOL_VALIDATORS = {"1.2": validate_catalog_1_2}


def _normalize_catalog(catalog):
    # Protocol 1.3 renamed the wire fields edition->article and network->
    # directory. Alias the new names onto the ones the 1.2 validator reads so a
    # single code path ingests both 1.2 and 1.3 catalogs during the rollout.
    if "articles" in catalog and "editions" not in catalog:
        catalog = {**catalog, "editions": catalog["articles"]}
    if "directory" in catalog and "network" not in catalog:
        catalog = {**catalog, "network": catalog["directory"]}
    return catalog


def ingest(candidate, catalog):
    """Route a parsed catalog to its protocol validator. Raises SkipPress."""
    status = protocol_status(catalog.get("protocol"))
    if status == "unsupported":
        raise SkipPress(models.UNSUPPORTED_PROTOCOL)
    catalog = _normalize_catalog(catalog)
    # On a higher-but-compatible minor, validate against the newest known schema.
    validator = PROTOCOL_VALIDATORS.get(catalog.get("protocol"), validate_catalog_1_2)
    return validator(candidate, catalog)

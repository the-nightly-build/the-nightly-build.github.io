"""Fetch, validate, and normalize one author's catalog into trusted records.

The catalog is the sole ingestion contract (doc invariant 3). Because the
author's public URL is now *derived* at build time (never configured), the
catalog is self-consistent by construction, so V1 needs no site.yaml fetch and
no url cross-check: we derive the Pages URL from owner/repo, read the catalog
there, and require only that it is opted in and structurally valid.
"""

from __future__ import annotations

import datetime as dt
import re

from . import models
from .discovery import author_id

# Field length ceilings on untrusted strings (defense in depth; rendering also
# escapes). Generous enough for real content, bounded enough to resist abuse.
MAX_TITLE = 200
MAX_DEK = 400
MAX_DESC = 280
MAX_NAME = 100
MAX_SECTION = 80
MAX_TAG = 40
MAX_TAGS_PER_ARTICLE = 12
MAX_AUTHOR_TAGS = 8

REQUIRED_TOP_LEVEL = (
    "generated",
    "protocol",
    "site_title",
    "directory",
    "series",
    "articles",
)


class SkipAuthor(Exception):
    """Raised to skip an author with a build-report reason code (models.*)."""

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


# Every article link is the derived author root plus this exact local shape.
# The catalog never supplies an absolute URL, and a hostile `path` (scheme,
# traversal, query, fragment) must never leak into an outbound link, so the
# path is validated against the slug charset the protocol already mandates.
_ARTICLE_PATH = re.compile(r"^/library/[a-z0-9-]+/[a-z0-9-]+\.html$")


def _top_tags(articles_meta):
    counts = {}
    for meta in articles_meta:
        for tag in _clean_tags(meta.get("tags"), cap=MAX_TAGS_PER_ARTICLE):
            counts[tag] = counts.get(tag, 0) + 1
    ranked = sorted(counts, key=lambda t: (-counts[t], t))
    return tuple(ranked[:MAX_AUTHOR_TAGS])


def validate_catalog_1_2(candidate, catalog):
    """Validate a protocol-1.2 catalog and return (AuthorRecord, [ArticleRecord]).

    Raises SkipAuthor(code) on any structural or opt-in failure.
    """
    for key in REQUIRED_TOP_LEVEL:
        if key not in catalog:
            raise SkipAuthor(models.INVALID_CATALOG)
    if not isinstance(catalog["series"], list) or not isinstance(
        catalog["articles"], list
    ):
        raise SkipAuthor(models.INVALID_CATALOG)
    if not isinstance(catalog["directory"], dict):
        raise SkipAuthor(models.INVALID_CATALOG)
    # Opt-out: an author is listed unless it explicitly set publish: false.
    if catalog["directory"].get("publish") is False:
        raise SkipAuthor(models.OPTED_OUT)
    generated = _parse_generated(catalog["generated"])
    if generated is None:
        raise SkipAuthor(models.INVALID_CATALOG)

    pid = author_id(candidate.repository)
    title = _clean_str(catalog["site_title"], MAX_TITLE) or candidate.repository
    # The author root is derived solely from GitHub identity; nothing the catalog
    # says can redirect a reader off the author's own site.
    root = pages_root(candidate)
    series_by_id = {
        s.get("id"): s for s in catalog["series"] if isinstance(s, dict) and s.get("id")
    }

    articles = []
    dates = []
    metas = []
    for ed in catalog["articles"]:
        if not isinstance(ed, dict) or ed.get("draft"):
            continue
        published = _parse_date(ed.get("date"))
        path = ed.get("path")
        series_id = ed.get("series")
        slug = ed.get("slug")
        if published is None or not isinstance(path, str) or not series_id or not slug:
            continue
        if not _ARTICLE_PATH.match(path):
            continue
        metas.append(ed)
        dates.append(published)
        cfg = series_by_id.get(series_id, {})
        rm = ed.get("reading_minutes")
        articles.append(
            models.ArticleRecord(
                id=f"{pid}:{series_id}/{slug}",
                author_id=pid,
                repository=candidate.repository,
                author_name=candidate.owner,
                title=_clean_str(ed.get("title"), MAX_TITLE) or str(slug),
                dek=_clean_str(ed.get("dek"), MAX_DEK),
                series_id=str(series_id),
                series_name=_clean_str(cfg.get("name"), MAX_NAME) or str(series_id),
                section=_clean_str(cfg.get("section"), MAX_SECTION) or None,
                tags=_clean_tags(ed.get("tags"), cap=MAX_TAGS_PER_ARTICLE),
                published=published,
                reading_minutes=int(rm)
                if isinstance(rm, (int, float)) and rm > 0
                else 1,
                url=root.rstrip("/") + path,
            )
        )

    author = models.AuthorRecord(
        id=pid,
        repository=candidate.repository,
        owner=candidate.owner,
        author_name=candidate.owner,
        title=title,
        description=_clean_str(catalog["directory"].get("description"), MAX_DESC),
        url=root,
        protocol=catalog["protocol"],
        catalog_generated_at=generated,
        series_count=len(catalog["series"]),
        article_count=len(articles),
        latest_published=max(dates) if dates else None,
        stars=candidate.stars,
        tags=_top_tags(metas),
    )
    return author, articles


PROTOCOL_VALIDATORS = {"1.2": validate_catalog_1_2}


def _normalize_catalog(catalog):
    # Protocol 1.2 used the field names edition/network; 1.3 renamed them to
    # article/directory. Alias the old names forward so a single code path
    # ingests both a 1.2 and a 1.3 catalog during (and after) the rollout.
    if "editions" in catalog and "articles" not in catalog:
        catalog = {**catalog, "articles": catalog["editions"]}
    if "network" in catalog and "directory" not in catalog:
        catalog = {**catalog, "directory": catalog["network"]}
    return catalog


def ingest(candidate, catalog):
    """Route a parsed catalog to its protocol validator. Raises SkipAuthor."""
    status = protocol_status(catalog.get("protocol"))
    if status == "unsupported":
        raise SkipAuthor(models.UNSUPPORTED_PROTOCOL)
    catalog = _normalize_catalog(catalog)
    # On a higher-but-compatible minor, validate against the newest known schema.
    validator = PROTOCOL_VALIDATORS.get(catalog.get("protocol"), validate_catalog_1_2)
    return validator(candidate, catalog)

"""Serialize trusted records into the directory's public JSON outputs.

Three files, all metadata only (never full text, doc invariant 4):
  authors.json  the author directory
  search.json   every indexed article, for client-side article search
  directory.json  build metadata (generated time + counts)

Given already-sorted records the string output is deterministic, so a rebuild
with the same inputs produces byte-identical authors.json / search.json.
"""

from __future__ import annotations

import json


def _iso(value):
    return value.isoformat() if value is not None else None


def author_to_public(author):
    return {
        "owner": author.owner,
        "author_name": author.author_name,
        "description": author.description,
        "url": author.url,
        "stars": author.stars,
        "article_count": author.article_count,
        "latest_published": _iso(author.latest_published),
    }


def article_to_search(article):
    return {
        "title": article.title,
        "dek": article.dek,
        "section": article.section or article.series_name,
        "author_name": article.author_name,
        "reading_minutes": article.reading_minutes,
        "published": _iso(article.published),
        "url": article.url,
    }


def _dump(data):
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def authors_json(authors):
    return _dump([author_to_public(p) for p in authors])


def search_json(articles):
    return _dump([article_to_search(e) for e in articles])


def directory_json(report, *, generated):
    data = {"generated": generated, **report.to_dict()}
    return _dump(data)

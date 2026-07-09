#!/usr/bin/env python3
"""Directory crawler test suite, zero framework, fully offline.

The whole pipeline (discovery -> fetch -> validate -> normalize -> report) runs
against injected fork lists and a dictionary-backed catalog fetcher, so no test
touches the directory.

Run: python3 tests/run_tests.py
"""

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from directory import discovery, ingest, models, render, serialize  # noqa: E402
from directory.crawl import crawl  # noqa: E402
from directory.http import FetchTooLarge  # noqa: E402

PASS, FAIL = 0, []


def check(name, cond, *, detail=""):
    global PASS
    if cond:
        PASS += 1
        print(f"  ok   {name}")
    else:
        FAIL.append(name)
        print(f"  FAIL {name} {detail}")


def cand(owner="Alice", name="the-nightly-build", stars=42):
    return discovery.Candidate(f"{owner}/{name}", owner, name, stars)


def valid_catalog(**over):
    cat = {
        "generated": "2026-07-08T09:00:00Z",
        "protocol": "1.2",
        "site_title": "Alice's Nightly Build",
        "directory": {
            "publish": True,
            "description": "Books, law, and the quiet parts of the news.",
            "url": "https://alice.github.io/the-nightly-build/",
        },
        "series": [
            {"id": "docket", "name": "Docket", "section": "Law", "mode": "open"},
        ],
        "articles": [
            {
                "series": "docket",
                "slug": "bartz",
                "title": "Bartz v. Anthropic",
                "date": "2026-07-07",
                "dek": "A landmark ruling.",
                "tags": ["copyright", "fair-use"],
                "reading_minutes": 7,
                "path": "/library/docket/bartz.html",
            },
            {
                "series": "docket",
                "slug": "kadrey",
                "title": "Kadrey v. Meta",
                "date": "2026-07-06",
                "dek": "Market dilution.",
                "tags": ["copyright"],
                "reading_minutes": 5,
                "path": "/library/docket/kadrey.html",
            },
        ],
        "builds": {},
        "tags": {},
    }
    cat.update(over)
    return cat


def fetcher(mapping):
    def fetch(url):
        value = mapping.get(url)
        if value is None:
            raise RuntimeError(f"no catalog at {url}")
        if isinstance(value, Exception):
            raise value
        return value

    return fetch


ALICE_URL = "https://alice.github.io/the-nightly-build/catalog.json"


def run_one(catalog_or_text, *, candidate=None, blocked=()):
    candidate = candidate or cand()
    url = ingest.catalog_url(candidate)
    if callable(catalog_or_text):
        fetch = catalog_or_text
    else:
        text = (
            catalog_or_text
            if isinstance(catalog_or_text, str)
            else json.dumps(catalog_or_text)
        )
        fetch = fetcher({url: text})
    return crawl([candidate], blocked=list(blocked), fetch_text=fetch)


print("== happy crawl ==")
authors, articles, report = run_one(valid_catalog())
check("one author indexed", len(authors) == 1 and report.authors_indexed == 1)
check("both articles indexed", len(articles) == 2 and report.articles_indexed == 2)
p = authors[0] if authors else None
check("author identity normalized", p and p.id == "github:alice/the-nightly-build")
check("author title from catalog", p and p.title == "Alice's Nightly Build")
check(
    "latest_published is newest article",
    p and p.latest_published.isoformat() == "2026-07-07",
)
check("article_count counts real articles", p and p.article_count == 2)
check(
    "author tags ranked by frequency",
    p and p.tags == ("copyright", "fair-use"),
    detail=str(p.tags if p else None),
)
check("stars carried from candidate", p and p.stars == 42)
lead = articles[0] if articles else None
check("articles sorted newest-first", lead and lead.title == "Bartz v. Anthropic")
check(
    "article url is absolute to the author",
    lead
    and lead.url
    == "https://alice.github.io/the-nightly-build/library/docket/bartz.html",
    detail=str(lead.url if lead else None),
)
check(
    "article carries series + section",
    lead and lead.series_name == "Docket" and lead.section == "Law",
)
check("author_name defaults to the handle", p and p.author_name == "Alice")
check("article byline is the author", lead and lead.author_name == "Alice")

pn, en, _ = crawl(
    [cand()],
    blocked=[],
    fetch_text=fetcher({ALICE_URL: json.dumps(valid_catalog())}),
    fetch_author_name=lambda login: "Alice Cooper",
)
check(
    "crawl enriches the display name on author + articles",
    pn[0].author_name == "Alice Cooper" and en[0].author_name == "Alice Cooper",
)

print("== opt-out ==")
_, _, r = run_one(valid_catalog(directory={"publish": False}))
check("publish false -> OPTED_OUT", r.statuses[0].reason == models.OPTED_OUT)
_, _, r = run_one(valid_catalog(directory={}))
check("listed by default when publish is unset", r.authors_indexed == 1)
_, _, r = run_one(valid_catalog(protocol="1.1"))
check(
    "protocol 1.1 -> UNSUPPORTED_PROTOCOL",
    r.statuses[0].reason == models.UNSUPPORTED_PROTOCOL,
)
_, _, r = run_one(valid_catalog(protocol="2.0"))
check(
    "protocol 2.0 -> UNSUPPORTED_PROTOCOL",
    r.statuses[0].reason == models.UNSUPPORTED_PROTOCOL,
)
cat = valid_catalog()
del cat["articles"]
_, _, r = run_one(cat)
check(
    "missing articles -> INVALID_CATALOG",
    r.statuses[0].reason == models.INVALID_CATALOG,
)
_, _, r = run_one("{ not json")
check(
    "bad json -> INVALID_CATALOG_JSON",
    r.statuses[0].reason == models.INVALID_CATALOG_JSON,
)
_, _, r = run_one(fetcher({ALICE_URL: RuntimeError("boom")}))
check(
    "fetch error -> CATALOG_FETCH_FAILED",
    r.statuses[0].reason == models.CATALOG_FETCH_FAILED,
)
_, _, r = run_one(fetcher({ALICE_URL: FetchTooLarge(ALICE_URL)}))
check("oversize -> CATALOG_TOO_LARGE", r.statuses[0].reason == models.CATALOG_TOO_LARGE)
_, _, r = run_one(valid_catalog(), blocked=["alice/the-nightly-build"])
check(
    "blocklist -> BLOCKED, no fetch",
    r.statuses[0].reason == models.BLOCKED and r.blocked == 1,
)

print("== protocol acceptance ==")
_, _, r = run_one(valid_catalog(protocol="1.3"))
check("1.3 accepted cleanly", r.authors_indexed == 1 and r.warnings == 0)
check("protocol_status: 1.2 ok", ingest.protocol_status("1.2") == "ok")
check("protocol_status: 1.3 ok", ingest.protocol_status("1.3") == "ok")
check("protocol_status: 1.9 warn", ingest.protocol_status("1.9") == "warn")
check(
    "protocol_status: 1.1 unsupported", ingest.protocol_status("1.1") == "unsupported"
)
check(
    "protocol_status: junk unsupported",
    ingest.protocol_status("banana") == "unsupported",
)

print("== normalization ==")
cat = valid_catalog()
cat["articles"][0]["title"] = "x" * 500
cat["articles"][1]["draft"] = True
cat["articles"].append(
    {"series": "docket", "slug": "nodate", "title": "No date", "path": "/x.html"}
)
authors, articles, _ = run_one(cat)
check(
    "overlong title truncated to bound",
    articles and len(articles[0].title) == ingest.MAX_TITLE,
)
check("draft and dateless articles dropped", len(articles) == 1)
p = authors[0]
check("article_count reflects dropped articles", p.article_count == 1)

print("== url trust ==")
# The catalog cannot redirect a reader off the derived GitHub Pages root, and a
# hostile article path never leaks into an outbound link.
hostile = valid_catalog(
    directory={
        "publish": True,
        "description": "Books, law, and the quiet parts of the news.",
        "url": "https://evil.example/",
    }
)
hostile["articles"] = [
    {
        "series": "docket",
        "slug": "bartz",
        "title": "Bartz v. Anthropic",
        "date": "2026-07-07",
        "path": "/library/docket/bartz.html",
    },
    {
        "series": "docket",
        "slug": "abs",
        "title": "Absolute URL",
        "date": "2026-07-06",
        "path": "https://evil.example/x",
    },
    {
        "series": "docket",
        "slug": "trav",
        "title": "Traversal",
        "date": "2026-07-05",
        "path": "/library/../../secret.html",
    },
    {
        "series": "docket",
        "slug": "query",
        "title": "Query string",
        "date": "2026-07-04",
        "path": "/library/docket/x.html?to=evil",
    },
]
hp, he, _ = run_one(hostile)
check(
    "declared catalog url ignored; author root derived from GitHub",
    hp and hp[0].url == "https://alice.github.io/the-nightly-build/",
    detail=str(hp[0].url if hp else None),
)
check(
    "only the clean local article path survives, rooted at the author",
    len(he) == 1
    and he[0].url
    == "https://alice.github.io/the-nightly-build/library/docket/bartz.html",
    detail=str([e.url for e in he]),
)

print("== discovery ==")
fork = {
    "full_name": "Bob/the-nightly-build",
    "owner": {"login": "Bob"},
    "name": "the-nightly-build",
    "fork": True,
    "archived": False,
    "disabled": False,
    "stargazers_count": 3,
}
check(
    "a live fork becomes a candidate", discovery._candidate_from_repo(fork) is not None
)
check(
    "archived fork skipped",
    discovery._candidate_from_repo({**fork, "archived": True}) is None,
)
check(
    "disabled fork skipped",
    discovery._candidate_from_repo({**fork, "disabled": True}) is None,
)
check(
    "non-fork skipped", discovery._candidate_from_repo({**fork, "fork": False}) is None
)


def fake_forks(url, token=None):
    page = int(re.search(r"[?&]page=(\d+)", url).group(1))
    return (
        {1: [fork, {**fork, "full_name": "Zoe/x", "archived": True}]}.get(page, []),
        {},
    )


forks = discovery.discover_forks("tok", get_json=fake_forks)
check(
    "discover_forks filters and paginates", len(forks) == 1 and forks[0].owner == "Bob"
)
merged = discovery.merge_candidates([cand("Bob")], [cand("bob")])
check("merge dedups case-insensitively", len(merged) == 1)

print("== json outputs ==")
authors, articles, report = run_one(valid_catalog())
pdata = json.loads(serialize.authors_json(authors))
sdata = json.loads(serialize.search_json(articles))
check(
    "authors.json is a list of one author", isinstance(pdata, list) and len(pdata) == 1
)
check(
    "author public fields present",
    set(pdata[0])
    == {
        "owner",
        "author_name",
        "description",
        "url",
        "stars",
        "article_count",
        "latest_published",
    },
    detail=str(sorted(pdata[0])),
)
check(
    "authors.json omits internal fields",
    "id" not in pdata[0] and "protocol" not in pdata[0] and "title" not in pdata[0],
)
check("search.json carries both articles", len(sdata) == 2)
check(
    "search record is metadata only",
    "text" not in sdata[0] and "tags" not in sdata[0],
)
check("search record carries the author byline", sdata[0]["author_name"] == "Alice")
check(
    "search record links to the original article",
    sdata[0]["url"].endswith("/library/docket/bartz.html"),
)
check(
    "json output is deterministic",
    serialize.authors_json(authors) == serialize.authors_json(authors)
    and serialize.search_json(articles) == serialize.search_json(articles),
)

print("== render ==")
authors, articles, report = run_one(valid_catalog())
home = render.render_home(articles)
check(
    "home leads with the ghost start-your-own card",
    "Start your own" in home and render.CANONICAL in home,
)
check("home server-renders an article card", "Bartz v. Anthropic" in home)
check("home shows the tagline", render.TAGLINE in home)
check(
    "home has the fused search + Articles/Authors toggle",
    'id="q"' in home and 'id="tab-articles"' in home and 'id="tab-authors"' in home,
)
check("home has a live count line", 'id="countline"' in home)
check(
    "footer is a copyright + appearance toggle",
    "© " in home and 'class="appearance"' in home,
)
check(
    "article cards link out safely",
    home.count('target="_blank" rel="noopener noreferrer"') >= len(articles),
)
check("404 renders", "Not found" in render.render_404())

# Untrusted strings are escaped at the render boundary.
evil = valid_catalog()
evil["articles"][0]["title"] = "<script>x</script>"
_, evil_eds, _ = run_one(evil)
ehome = render.render_home(evil_eds)
check(
    "article title is html-escaped",
    "&lt;script&gt;" in ehome and "<script>x" not in ehome,
)

print()
print(f"{PASS} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED:", FAIL)
    sys.exit(1)

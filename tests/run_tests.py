#!/usr/bin/env python3
"""Network crawler test suite, zero framework, fully offline.

The whole pipeline (discovery -> fetch -> validate -> normalize -> report) runs
against injected fork lists and a dictionary-backed catalog fetcher, so no test
touches the network.

Run: python3 tests/run_tests.py
"""

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from network import discovery, ingest, models, serialize  # noqa: E402
from network.crawl import crawl  # noqa: E402
from network.http import FetchTooLarge  # noqa: E402

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
        "network": {
            "publish": True,
            "description": "Books, law, and the quiet parts of the news.",
            "url": "https://alice.github.io/the-nightly-build/",
        },
        "series": [
            {"id": "docket", "name": "Docket", "section": "Law", "mode": "open"},
        ],
        "editions": [
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
presses, editions, report = run_one(valid_catalog())
check("one press indexed", len(presses) == 1 and report.presses_indexed == 1)
check("both editions indexed", len(editions) == 2 and report.editions_indexed == 2)
p = presses[0] if presses else None
check("press identity normalized", p and p.id == "github:alice/the-nightly-build")
check("press title from catalog", p and p.title == "Alice's Nightly Build")
check(
    "latest_published is newest edition",
    p and p.latest_published.isoformat() == "2026-07-07",
)
check("edition_count counts real editions", p and p.edition_count == 2)
check(
    "press tags ranked by frequency",
    p and p.tags == ("copyright", "fair-use"),
    detail=str(p.tags if p else None),
)
check("stars carried from candidate", p and p.stars == 42)
lead = editions[0] if editions else None
check("editions sorted newest-first", lead and lead.title == "Bartz v. Anthropic")
check(
    "edition url is absolute to the press",
    lead
    and lead.url
    == "https://alice.github.io/the-nightly-build/library/docket/bartz.html",
    detail=str(lead.url if lead else None),
)
check(
    "edition carries series + section",
    lead and lead.series_name == "Docket" and lead.section == "Law",
)

print("== skip reasons ==")
_, _, r = run_one(valid_catalog(network={"publish": False}))
check("publish false -> NOT_OPTED_IN", r.statuses[0].reason == models.NOT_OPTED_IN)
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
del cat["editions"]
_, _, r = run_one(cat)
check(
    "missing editions -> INVALID_CATALOG",
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
check("1.3 accepted with a warning", r.presses_indexed == 1 and r.warnings == 1)
check("protocol_status: 1.2 ok", ingest.protocol_status("1.2") == "ok")
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
cat["editions"][0]["title"] = "x" * 500
cat["editions"][1]["draft"] = True
cat["editions"].append(
    {"series": "docket", "slug": "nodate", "title": "No date", "path": "/x.html"}
)
presses, editions, _ = run_one(cat)
check(
    "overlong title truncated to bound",
    editions and len(editions[0].title) == ingest.MAX_TITLE,
)
check("draft and dateless editions dropped", len(editions) == 1)
p = presses[0]
check("edition_count reflects dropped editions", p.edition_count == 1)

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
presses, editions, report = run_one(valid_catalog())
pdata = json.loads(serialize.presses_json(presses))
sdata = json.loads(serialize.search_json(editions))
check(
    "presses.json is a list of one press", isinstance(pdata, list) and len(pdata) == 1
)
check(
    "press public fields present",
    set(pdata[0])
    == {
        "id",
        "repository",
        "owner",
        "title",
        "description",
        "url",
        "series_count",
        "edition_count",
        "latest_published",
        "stars",
        "tags",
    },
    detail=str(sorted(pdata[0])),
)
check(
    "presses.json omits internal fields",
    "protocol" not in pdata[0] and "catalog_generated_at" not in pdata[0],
)
check("search.json carries both editions", len(sdata) == 2)
check("search record has no full text", "text" not in sdata[0])
check(
    "search record links to the original edition",
    sdata[0]["url"].endswith("/library/docket/bartz.html"),
)
check(
    "json output is deterministic",
    serialize.presses_json(presses) == serialize.presses_json(presses)
    and serialize.search_json(editions) == serialize.search_json(editions),
)

print()
print(f"{PASS} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED:", FAIL)
    sys.exit(1)

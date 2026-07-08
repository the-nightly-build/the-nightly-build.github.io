#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml"]
# ///
"""Build the network directory: crawl opted-in presses, emit a static site.

    build_network.py --out dist           # real crawl (needs GITHUB_TOKEN)
    build_network.py --out dist --demo     # offline crawl of built-in fixtures

The crawl is pure given its inputs, so --demo swaps the real GitHub discovery
and HTTP fetch for a built-in fixture set: the same pipeline, no network.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys

from network import discovery, http, moderation, render
from network.crawl import crawl

ROOT = os.path.dirname(os.path.abspath(__file__))


def _demo():
    """A built-in fixture crawl so the site can be built and previewed offline."""

    def catalog(title, desc, owner, editions, series):
        return json.dumps(
            {
                "generated": "2026-07-08T09:00:00Z",
                "protocol": "1.2",
                "site_title": title,
                "network": {
                    "publish": True,
                    "description": desc,
                    "url": f"https://{owner.lower()}.github.io/the-nightly-build/",
                },
                "series": series,
                "editions": editions,
                "builds": {},
                "tags": {},
            }
        )

    presses = {
        "RyanSaxe/the-nightly-build": catalog(
            "Ryan's Nightly Build",
            "AI, markets, engineering, and whatever I cannot stop thinking about.",
            "RyanSaxe",
            [
                {
                    "series": "docket",
                    "slug": "bartz-v-anthropic",
                    "title": "Bartz v. Anthropic: The Line Between Learning and Piracy",
                    "date": "2026-07-07",
                    "dek": "A landmark ruling made training on books fair use; a settlement made pirating them the expensive part.",
                    "tags": ["copyright", "fair-use", "training-data"],
                    "reading_minutes": 7,
                    "path": "/library/docket/bartz-v-anthropic.html",
                },
                {
                    "series": "positions",
                    "slug": "nvidia",
                    "title": "Nvidia: The Widest Moat, the Narrowest Customer List",
                    "date": "2026-07-08",
                    "dek": "A near-monopoly on AI training silicon, priced for durability.",
                    "tags": ["equity", "semiconductors", "ai-infrastructure"],
                    "reading_minutes": 9,
                    "path": "/library/positions/nvidia.html",
                },
            ],
            [
                {
                    "id": "docket",
                    "name": "Docket",
                    "section": "AI & the Law",
                    "mode": "open",
                },
                {
                    "id": "positions",
                    "name": "Positions",
                    "section": "Markets",
                    "mode": "open",
                },
            ],
        ),
        "Dana/the-nightly-build": catalog(
            "Night Desk",
            "A quiet nightly read on cities, transit, and the built environment.",
            "Dana",
            [
                {
                    "series": "transit",
                    "slug": "congestion-pricing",
                    "title": "What Congestion Pricing Actually Priced",
                    "date": "2026-07-06",
                    "dek": "One year of tolls, and the ridership numbers nobody predicted.",
                    "tags": ["cities", "transit", "policy"],
                    "reading_minutes": 6,
                    "path": "/library/transit/congestion-pricing.html",
                }
            ],
            [{"id": "transit", "name": "Transit", "section": "Cities", "mode": "open"}],
        ),
    }
    candidates = [
        discovery.Candidate(repo, repo.split("/")[0], repo.split("/")[1], stars)
        for repo, stars in (
            ("RyanSaxe/the-nightly-build", 128),
            ("Dana/the-nightly-build", 17),
        )
    ]
    urls = {}
    for repo, text in presses.items():
        owner, name = repo.split("/")
        urls[f"https://{owner.lower()}.github.io/{name}/catalog.json"] = text

    def fetch_text(url):
        return urls[url]

    return candidates, fetch_text, len(candidates)


def _real(token):
    forks = discovery.discover_forks(token)
    seeds = discovery.resolve_seeds(moderation.load_seeds(ROOT), token)
    candidates = discovery.merge_candidates(forks, seeds)
    return candidates, http.get_text, len(forks)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build the Nightly Build Network")
    parser.add_argument("--out", default="dist", help="output directory")
    parser.add_argument(
        "--demo", action="store_true", help="build from built-in fixtures, offline"
    )
    args = parser.parse_args(argv)

    if args.demo:
        candidates, fetch_text, forks_discovered = _demo()
    else:
        token = os.getenv("GITHUB_TOKEN")
        if not token:
            sys.stderr.write(
                "GITHUB_TOKEN is required for a real crawl (or use --demo)\n"
            )
            return 2
        candidates, fetch_text, forks_discovered = _real(token)

    blocked = moderation.load_blocked(ROOT)
    presses, editions, report = crawl(
        candidates,
        blocked=blocked,
        fetch_text=fetch_text,
        forks_discovered=forks_discovered,
    )
    generated = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    render.write_site(
        args.out,
        presses,
        editions,
        report,
        assets_dir=os.path.join(ROOT, "assets"),
        generated=generated,
    )

    summary = report.to_markdown()
    print(summary)
    step_summary = os.getenv("GITHUB_STEP_SUMMARY")
    if step_summary:
        with open(step_summary, "a", encoding="utf-8") as fh:
            fh.write(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

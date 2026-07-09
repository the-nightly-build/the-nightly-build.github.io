#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml"]
# ///
"""Build the network directory: crawl listed presses, emit a static site.

    build_network.py --out dist           # real crawl (needs GITHUB_TOKEN)
    build_network.py --out dist --demo     # offline crawl of built-in fixtures

Listing is opt-out: a press is included unless its catalog sets
network.publish: false. The crawl is pure given its inputs, so --demo swaps the
real GitHub discovery, HTTP fetch, and author-name lookup for a built-in fixture
set: the same pipeline, no network.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from dataclasses import dataclass

from network import discovery, http, moderation, render
from network.crawl import crawl

ROOT = os.path.dirname(os.path.abspath(__file__))

# One row per fixture edition: (series_id, series_name, section, slug, title, dek,
# date, reading_minutes).
DemoEdition = tuple[str, str, str, str, str, str, str, int]


@dataclass(frozen=True)
class _DemoAuthor:
    handle: str
    name: str
    desc: str
    stars: int
    editions: list[DemoEdition]


# Fixture authors for the offline demo, close to the design mock.
_DEMO = [
    _DemoAuthor(
        "ryansaxe",
        "Ryan Saxe",
        "AI, markets, engineering, and whatever I cannot stop thinking about.",
        128,
        [
            (
                "positions",
                "Positions",
                "Markets",
                "nvidia",
                "Nvidia: The Widest Moat, the Narrowest Customer List",
                "A near-monopoly on AI training silicon, priced for durability.",
                "2026-07-08",
                9,
            ),
            (
                "docket",
                "Docket",
                "AI & the Law",
                "bartz-v-anthropic",
                "Bartz v. Anthropic: The Line Between Learning and Piracy",
                "A landmark fair-use ruling met a settlement — the difference is provenance.",
                "2026-07-07",
                7,
            ),
        ],
    ),
    _DemoAuthor(
        "mirao",
        "Mira Okonkwo",
        "A working course in machine learning — one lesson a night.",
        73,
        [
            (
                "course",
                "The Course",
                "Course",
                "attention",
                "Why Attention Beat Recurrence",
                "The architecture that ate sequence modeling, from first principles.",
                "2026-07-08",
                15,
            ),
            (
                "course",
                "The Course",
                "Course",
                "gradient-descent",
                "Gradient Descent, Slowly",
                "What actually happens when the loss goes down.",
                "2026-07-06",
                13,
            ),
        ],
    ),
    _DemoAuthor(
        "sellison",
        "Sam Ellison",
        "Essays on time, systems, and the patience they demand.",
        41,
        [
            (
                "essays",
                "Essays",
                "Essay",
                "compounding",
                "The Patience of Compounding Systems",
                "Why the returns that matter arrive after everyone stops watching.",
                "2026-07-08",
                12,
            ),
        ],
    ),
    _DemoAuthor(
        "priyawrites",
        "Priya Nair",
        "Media, culture, and the business of attention.",
        29,
        [
            (
                "beat",
                "The Beat",
                "Media",
                "attention-recession",
                "The Attention Recession",
                "Every feed is fighting over a pie that stopped growing in 2024.",
                "2026-07-07",
                8,
            ),
        ],
    ),
    _DemoAuthor(
        "danalee",
        "Dana Lee",
        "Cities, transit, and the built environment.",
        12,
        [
            (
                "transit",
                "Transit",
                "Cities",
                "congestion-pricing",
                "What Congestion Pricing Actually Priced",
                "One year of tolls, and the ridership numbers nobody predicted.",
                "2026-07-07",
                6,
            ),
        ],
    ),
]


def _demo():
    names = {a.handle: a.name for a in _DEMO}
    candidates = []
    urls = {}
    for a in _DEMO:
        root = f"https://{a.handle}.github.io/the-nightly-build/"
        series = {}
        editions = []
        for sid, sname, section, slug, title, dek, date, minutes in a.editions:
            series[sid] = {"id": sid, "name": sname, "section": section, "mode": "open"}
            editions.append(
                {
                    "series": sid,
                    "slug": slug,
                    "title": title,
                    "dek": dek,
                    "date": date,
                    "reading_minutes": minutes,
                    "path": f"/library/{sid}/{slug}.html",
                }
            )
        urls[root + "catalog.json"] = json.dumps(
            {
                "generated": "2026-07-08T09:00:00Z",
                "protocol": "1.2",
                "site_title": "The Nightly Build",
                "network": {"publish": True, "description": a.desc, "url": root},
                "series": list(series.values()),
                "editions": editions,
                "builds": {},
                "tags": {},
            }
        )
        candidates.append(
            discovery.Candidate(
                f"{a.handle}/the-nightly-build", a.handle, "the-nightly-build", a.stars
            )
        )
    return (
        candidates,
        urls.__getitem__,
        (lambda login: names.get(login, login)),
        len(candidates),
    )


def _real(token):
    forks = discovery.discover_forks(token)
    seeds = discovery.resolve_seeds(moderation.load_seeds(ROOT), token)
    candidates = discovery.merge_candidates(forks, seeds)

    def author_name(login):
        return discovery.fetch_author_name(login, token)

    return candidates, http.get_text, author_name, len(forks)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build the Nightly Build Network")
    parser.add_argument("--out", default="dist", help="output directory")
    parser.add_argument(
        "--demo", action="store_true", help="build from built-in fixtures, offline"
    )
    args = parser.parse_args(argv)

    if args.demo:
        candidates, fetch_text, author_name, forks_discovered = _demo()
    else:
        token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
        if not token:
            sys.stderr.write(
                "GITHUB_TOKEN (or GH_TOKEN) is required for a real crawl (or --demo)\n"
            )
            return 2
        candidates, fetch_text, author_name, forks_discovered = _real(token)

    blocked = moderation.load_blocked(ROOT)
    presses, editions, report = crawl(
        candidates,
        blocked=blocked,
        fetch_text=fetch_text,
        fetch_author_name=author_name,
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

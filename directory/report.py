"""The build report: what the crawl discovered, indexed, and skipped.

Surfaced both as structured data and as a GitHub Actions step summary (doc
§28-29), so a spam wave or a fleet of broken catalogs is visible at a glance.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import models


@dataclass
class AuthorStatus:
    repository: str
    status: str  # "indexed" | "skipped" | "blocked"
    reason: str


@dataclass
class BuildReport:
    forks_discovered: int = 0
    candidates: int = 0
    authors_indexed: int = 0
    authors_skipped: int = 0
    blocked: int = 0
    articles_indexed: int = 0
    warnings: int = 0
    statuses: list[AuthorStatus] = field(default_factory=list)

    def indexed(self, repository, article_count):
        self.authors_indexed += 1
        self.articles_indexed += article_count
        self.statuses.append(AuthorStatus(repository, "indexed", models.INDEXED))

    def skipped(self, repository, reason):
        self.statuses.append(AuthorStatus(repository, "skipped", reason))
        if reason == models.BLOCKED:
            self.blocked += 1
        else:
            self.authors_skipped += 1

    def to_dict(self):
        return {
            "forks_discovered": self.forks_discovered,
            "candidates": self.candidates,
            "authors_indexed": self.authors_indexed,
            "authors_skipped": self.authors_skipped,
            "blocked": self.blocked,
            "articles_indexed": self.articles_indexed,
            "warnings": self.warnings,
        }

    def to_markdown(self):
        d = self.to_dict()
        lines = [
            "# Directory Build",
            f"Forks discovered: {d['forks_discovered']}",
            f"Candidates (forks + seeds): {d['candidates']}",
            f"Authors indexed: {d['authors_indexed']}",
            f"Authors skipped: {d['authors_skipped']}",
            f"Blocked: {d['blocked']}",
            f"Articles indexed: {d['articles_indexed']:,}",
        ]
        # A fork with no site (fetch failed) or no opt-in is simply not
        # participating; only an author with a reachable but broken catalog
        # warrants attention.
        quiet = (models.OPTED_OUT, models.CATALOG_FETCH_FAILED)
        problems = [
            s for s in self.statuses if s.status == "skipped" and s.reason not in quiet
        ]
        if problems:
            lines += ["", "## Skipped authors requiring attention"]
            lines += [f"{s.repository} - {s.reason}" for s in problems]
        indexed = [s.repository for s in self.statuses if s.status == "indexed"]
        if indexed:
            lines += ["", "## Indexed this build"]
            lines += sorted(indexed)
        return "\n".join(lines) + "\n"

"""The build report: what the crawl discovered, indexed, and skipped.

Surfaced both as structured data and as a GitHub Actions step summary (doc
§28-29), so a spam wave or a fleet of broken catalogs is visible at a glance.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import models


@dataclass
class PressStatus:
    repository: str
    status: str  # "indexed" | "skipped" | "blocked"
    reason: str


@dataclass
class BuildReport:
    forks_discovered: int = 0
    candidates: int = 0
    presses_indexed: int = 0
    presses_skipped: int = 0
    blocked: int = 0
    editions_indexed: int = 0
    warnings: int = 0
    statuses: list[PressStatus] = field(default_factory=list)

    def indexed(self, repository, edition_count):
        self.presses_indexed += 1
        self.editions_indexed += edition_count
        self.statuses.append(PressStatus(repository, "indexed", models.INDEXED))

    def skipped(self, repository, reason):
        self.statuses.append(PressStatus(repository, "skipped", reason))
        if reason == models.BLOCKED:
            self.blocked += 1
        else:
            self.presses_skipped += 1

    def to_dict(self):
        return {
            "forks_discovered": self.forks_discovered,
            "candidates": self.candidates,
            "presses_indexed": self.presses_indexed,
            "presses_skipped": self.presses_skipped,
            "blocked": self.blocked,
            "editions_indexed": self.editions_indexed,
            "warnings": self.warnings,
        }

    def to_markdown(self):
        d = self.to_dict()
        lines = [
            "# Network Build",
            f"Forks discovered: {d['forks_discovered']}",
            f"Candidates (forks + seeds): {d['candidates']}",
            f"Presses indexed: {d['presses_indexed']}",
            f"Presses skipped: {d['presses_skipped']}",
            f"Blocked: {d['blocked']}",
            f"Editions indexed: {d['editions_indexed']:,}",
        ]
        problems = [
            s
            for s in self.statuses
            if s.status == "skipped" and s.reason != models.NOT_OPTED_IN
        ]
        if problems:
            lines += ["", "## Skipped presses requiring attention"]
            lines += [f"{s.repository} - {s.reason}" for s in problems]
        indexed = [s.repository for s in self.statuses if s.status == "indexed"]
        if indexed:
            lines += ["", "## Indexed this build"]
            lines += sorted(indexed)
        return "\n".join(lines) + "\n"

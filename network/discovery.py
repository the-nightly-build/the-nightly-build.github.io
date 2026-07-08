"""Discover candidate presses: direct forks of the canonical repo, plus seeds.

V1 discovery is exactly the repositories GitHub returns from the canonical
repo's fork-listing endpoint (doc §16). A fork of a downstream press, or a
manually copied repo, is invisible to auto-discovery, so a small seed list
(moderation/seeds.yaml) covers those gaps by naming repos explicitly.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import http

CANONICAL = "the-nightly-build/the-nightly-build"
FORKS_PER_PAGE = 100
MAX_PAGES = 50  # 5000 forks; a backstop, not an expected limit


@dataclass(frozen=True)
class Candidate:
    repository: str  # GitHub full_name, display casing: "Owner/Repo"
    owner: str
    name: str
    stars: int


def press_id(repository):
    # Case-insensitive identity; display casing is kept on the record itself.
    return f"github:{repository.lower()}"


def _candidate_from_repo(repo):
    # A GitHub repo object -> Candidate, or None if it must be skipped
    # (archived, disabled, or not actually a fork).
    if repo.get("archived") or repo.get("disabled") or not repo.get("fork", False):
        return None
    return Candidate(
        repository=repo["full_name"],
        owner=repo["owner"]["login"],
        name=repo["name"],
        stars=int(repo.get("stargazers_count", 0)),
    )


def discover_forks(token, *, upstream=CANONICAL, get_json=http.get_json):
    """Return viable fork Candidates for the upstream repo, following pagination.

    get_json is injectable so the crawl can be tested without network access.
    """
    candidates = []
    for page in range(1, MAX_PAGES + 1):
        url = (
            f"https://api.github.com/repos/{upstream}/forks"
            f"?per_page={FORKS_PER_PAGE}&page={page}&sort=newest"
        )
        repos, _ = get_json(url, token=token)
        if not repos:
            break
        for repo in repos:
            candidate = _candidate_from_repo(repo)
            if candidate is not None:
                candidates.append(candidate)
        if len(repos) < FORKS_PER_PAGE:
            break
    return candidates


def resolve_seeds(seeds, token, *, get_json=http.get_json):
    """Resolve explicit "owner/repo" seed entries into Candidates.

    Each seed is looked up so its star count and archived/disabled/fork state
    are real rather than assumed. A lookup that fails is skipped silently: a
    broken seed should never break the crawl.
    """
    resolved = []
    for entry in seeds:
        try:
            repo, _ = get_json(f"https://api.github.com/repos/{entry}", token=token)
        except Exception:
            continue
        candidate = _candidate_from_repo(repo)
        if candidate is not None:
            resolved.append(candidate)
    return resolved


def merge_candidates(*groups):
    """Union candidate groups, de-duplicated by case-insensitive identity."""
    seen = {}
    for group in groups:
        for candidate in group:
            seen.setdefault(press_id(candidate.repository), candidate)
    return list(seen.values())

"""Minimal HTTP helpers over stdlib urllib (no third-party deps).

Two needs: authenticated GitHub API JSON (fork listing, repo lookups) and
plain fetches of an author's public catalog.json with a hard size ceiling. The
size ceiling is a security control: an untrusted author must not be able to
exhaust the runner by serving an enormous catalog.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

USER_AGENT = "NightlyBuild-directory/1.0 (+https://github.com/the-nightly-build)"
DEFAULT_TIMEOUT_S = 15
CATALOG_MAX_BYTES = 5_000_000  # 5 MB ceiling on an untrusted catalog


class FetchTooLarge(Exception):
    """The response exceeded the byte ceiling before it finished."""


def get_json(url, *, token=None, timeout=DEFAULT_TIMEOUT_S):
    """Fetch and parse a JSON document, returning (data, headers).

    Raises urllib errors on transport failure and ValueError on bad JSON;
    callers decide how to treat those. Used for the GitHub API.
    """
    headers = {"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode()), dict(resp.headers)


def get_text(url, *, timeout=DEFAULT_TIMEOUT_S, max_bytes=CATALOG_MAX_BYTES):
    """Fetch a text body, enforcing a byte ceiling.

    Returns the decoded text. Raises FetchTooLarge if the body exceeds
    max_bytes, and urllib errors on transport failure.
    """
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read(max_bytes + 1)
    if len(raw) > max_bytes:
        raise FetchTooLarge(url)
    return raw.decode("utf-8", errors="replace")

"""Load the reactive moderation data: the blocklist and the seed list."""

from __future__ import annotations

import os

import yaml


def _load_repositories(path):
    if not os.path.isfile(path):
        return []
    data = yaml.safe_load(open(path, encoding="utf-8")) or {}
    items = data.get("repositories") or []
    return [str(item).strip() for item in items if str(item).strip()]


def load_blocked(root):
    return _load_repositories(os.path.join(root, "moderation", "blocked.yaml"))


def load_seeds(root):
    return _load_repositories(os.path.join(root, "moderation", "seeds.yaml"))

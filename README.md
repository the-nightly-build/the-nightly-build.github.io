# The Nightly Build Network

The discovery directory for [The Nightly Build](https://github.com/the-nightly-build/the-nightly-build).
It crawls opted-in presses (forks of the canonical engine that set
`network.publish: true`), reads each one's public `catalog.json`, and publishes a
static, searchable index at
[the-nightly-build.github.io](https://the-nightly-build.github.io/).

The network is a discovery layer over independently owned presses. It does not
review, endorse, or host their content; every press is external and links out to
its own site. No backend, no database, no accounts: the whole site is rebuilt on
a schedule from public forks plus a blocklist.

## How it works

1. **Discover** — list public forks of the canonical repo (plus any
   `moderation/seeds.yaml` entries).
2. **Ingest** — for each, fetch `catalog.json` from its GitHub Pages URL and
   validate it (protocol, opt-in, structure). Blocked repos are never fetched.
3. **Normalize** — escape and bound every untrusted string into typed records.
4. **Render** — emit `presses.json` / `search.json` and a static site (press
   directory, per-press profiles, article search).

## Development

Python 3.10+ with one dependency (PyYAML). No build step for the crawler.

```sh
python3 tests/run_tests.py       # crawler + render tests, fully offline
python3 build_network.py --help  # crawl and build the site
```

## Moderation

- `moderation/blocked.yaml` — repositories excluded from the network.
- `moderation/seeds.yaml` — presses to include beyond direct forks.

MIT licensed.

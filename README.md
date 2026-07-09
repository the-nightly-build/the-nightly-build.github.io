# The Nightly Build Directory

The discovery directory for [The Nightly Build](https://github.com/the-nightly-build/the-nightly-build).
It crawls published sites (forks of the canonical engine, listed by default
unless they set `network.publish: false`), reads each one's public
`catalog.json`, and publishes a static, searchable index at
[the-nightly-build.github.io](https://the-nightly-build.github.io/).

The directory is a discovery layer over independently owned sites. It does not
review, endorse, or host their content; every site is external, and the
directory links out to it. No backend, no database, no accounts: the whole site
is rebuilt on a schedule from public forks plus a blocklist.

## How it works

1. **Discover** — list public forks of the canonical repo (plus any
   `moderation/seeds.yaml` entries).
2. **Ingest** — for each, fetch `catalog.json` from its GitHub Pages URL and
   validate it (protocol, opt-out, structure). Blocked repos are never fetched.
3. **Normalize** — escape and bound every untrusted string into typed records.
4. **Render** — emit `presses.json` / `search.json` and a static single-page
   site with combined article and author search.

## Development

Python 3.10+ with one dependency (PyYAML). No build step for the crawler.

```sh
python3 tests/run_tests.py       # crawler + render tests, fully offline
python3 build_network.py --help  # crawl and build the site
```

## Moderation

- `moderation/blocked.yaml` — repositories excluded from the directory.
- `moderation/seeds.yaml` — sites to include beyond direct forks.

MIT licensed.

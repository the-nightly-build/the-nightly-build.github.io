"""Render the single-page directory: hero, fused search/scope, ruled card grid.

The Articles grid is server-rendered so the page reads with no JavaScript;
net.js hydrates the Articles/Authors toggle, live search, and the Authors view
from presses.json / search.json. There are no per-author or search sub-pages —
every card links out to the real article or the author's own site. Untrusted
strings are HTML-escaped here at the trust boundary.
"""

from __future__ import annotations

import datetime as dt
import os
from html import escape as esc

from . import serialize

CANONICAL = "https://github.com/the-nightly-build/the-nightly-build"
NETWORK_TITLE = "The Nightly Build"
TAGLINE = "A decentralized, AI-generated newspaper."
FOOTER = "The Nightly Build"

FONTS = (
    "https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@"
    "0,6..72,400..700;1,6..72,400..700&family=Inter:wght@400;500;600"
    "&family=IBM+Plex+Mono:wght@400;500&display=swap"
)
APPEARANCE_BOOTSTRAP = (
    "<script>try{var m=localStorage.getItem('nb-appearance');"
    "if(m==='light'||m==='dark')"
    "document.documentElement.setAttribute('data-mode',m);}catch(e){}</script>"
)


def _nice_date(value):
    return f"{value:%b} {value.day}" if value is not None else ""


def ghost_cell():
    return (
        f'<a class="cell ghost" href="{CANONICAL}" target="_blank" '
        'rel="noopener noreferrer"><span class="ghost-plus">＋</span>'
        '<span class="ghost-title">Start your own</span>'
        '<span class="ghost-sub">Fork the repo and ask your agent to set you up ↗</span></a>'
    )


def article_cell(edition):
    kicker = edition.section or edition.series_name
    dek = f'<p class="dek">{esc(edition.dek)}</p>' if edition.dek else ""
    return (
        f'<a class="cell" href="{esc(edition.url)}" target="_blank" '
        f'rel="noopener noreferrer"><span class="eyebrow">{esc(kicker)}</span>'
        f"<h3>{esc(edition.title)}</h3>{dek}"
        f'<div class="cardfoot"><span class="left">{esc(edition.author_name)}</span>'
        f'<span class="right">{edition.reading_minutes} min · '
        f"{_nice_date(edition.published)}</span></div></a>"
    )


def page(body):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(NETWORK_TITLE)}</title>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="{FONTS}" rel="stylesheet">
<link rel="stylesheet" href="/assets/theme.css">
<link rel="stylesheet" href="/assets/net.css">
{APPEARANCE_BOOTSTRAP}
<script defer src="/assets/net.js"></script>
</head>
<body>
{body}
<footer class="foot"><div class="foot-in">
  <span>© {dt.date.today().year} {esc(FOOTER)}</span>
  <button class="appearance" type="button">◐ auto</button>
</div></footer>
</body></html>"""


def render_home(editions):
    count = len(editions)
    cells = ghost_cell() + "".join(article_cell(e) for e in editions)
    if not editions:
        cells = ghost_cell()
    body = (
        '<div class="container">'
        '<section class="hero">'
        f'<h1>The Nightly Build<span class="dot">.</span></h1>'
        f'<p class="tag">{esc(TAGLINE)}</p></section>'
        '<div class="searchbar"><div class="field">'
        '<input id="q" type="search" placeholder="Search" autocomplete="off" '
        'aria-label="Search"></div>'
        '<span class="seg" role="tablist">'
        '<button id="tab-articles" role="tab" aria-selected="true">Articles</button>'
        '<button id="tab-authors" role="tab" aria-selected="false">Authors</button>'
        "</span></div>"
        f'<div class="countline" id="countline">{count} '
        f"{'article' if count == 1 else 'articles'}</div>"
        f'<div class="grid" id="grid">{cells}</div>'
        "</div>"
    )
    return page(body)


def render_404():
    body = (
        '<div class="container"><section class="hero">'
        "<h1>Not found</h1>"
        '<p class="tag">That page is not part of the network. '
        '<a href="/" style="color:var(--accent)">Back to the front page →</a>'
        "</p></section></div>"
    )
    return page(body)


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def write_site(out, presses, editions, report, *, assets_dir, generated):
    """Emit the single-page site + JSON outputs into `out`."""
    _write(os.path.join(out, "index.html"), render_home(editions))
    _write(os.path.join(out, "404.html"), render_404())
    _write(os.path.join(out, "presses.json"), serialize.presses_json(presses))
    _write(os.path.join(out, "search.json"), serialize.search_json(editions))
    _write(
        os.path.join(out, "network.json"),
        serialize.network_json(report, generated=generated),
    )
    dest = os.path.join(out, "assets")
    os.makedirs(dest, exist_ok=True)
    for name in ("theme.css", "net.css", "net.js"):
        with open(os.path.join(assets_dir, name), encoding="utf-8") as src:
            _write(os.path.join(dest, name), src.read())

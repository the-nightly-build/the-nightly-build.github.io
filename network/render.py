"""Render the static directory site: home, per-press profiles, 404.

Every untrusted string is HTML-escaped here at the trust boundary; the client
search does the same when it builds result rows. Pages are absolute-path rooted
(the site is served at the domain root), share the engine's theme tokens, and
degrade to a clean static press directory with no JavaScript.
"""

from __future__ import annotations

import datetime as dt
import os
from html import escape as esc

from . import serialize

CANONICAL = "the-nightly-build/the-nightly-build"
NETWORK_TITLE = "The Nightly Build Network"
TAGLINE = "Independent newspapers, researched by agents and owned by their readers."
FOOTER_LINE = "Independent presses, indexed not reviewed."
PROFILE_EDITION_LIMIT = 20

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


def nice_date(value):
    if value is None:
        return ""
    return f"{value:%b} {value.day}, {value.year}"


def profile_path(press):
    return f"/presses/{press.owner.lower()}/{press.repository.split('/')[1].lower()}/"


def _facts(press):
    editions = f"{press.edition_count} edition{'s' if press.edition_count != 1 else ''}"
    desks = f"{press.series_count} desk{'s' if press.series_count != 1 else ''}"
    parts = [editions, desks]
    if press.latest_published:
        parts.append(f"latest {nice_date(press.latest_published)}")
    facts = " · ".join(parts)
    return f'{facts} · <span class="net-star">★ {press.stars}</span>'


def _tags(tags):
    if not tags:
        return ""
    spans = "".join(f"<span>#{esc(t)}</span>" for t in tags)
    return f'<div class="net-tags">{spans}</div>'


def page(title, body):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(title)}</title>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="{FONTS}" rel="stylesheet">
<link rel="stylesheet" href="/assets/theme.css">
<link rel="stylesheet" href="/assets/net.css">
{APPEARANCE_BOOTSTRAP}
<script defer src="/assets/net.js"></script>
</head>
<body>
<header class="net-bar"><div class="net-bar-in">
  <a class="net-wordmark" href="/">The Nightly Build <span class="net-sub">Network</span></a>
  <nav class="net-nav"><a href="https://github.com/{CANONICAL}" target="_blank" rel="noopener noreferrer">Make a press ↗</a></nav>
</div></header>
<main class="net-shell">
{body}
</main>
<footer class="net-footer"><div class="net-footer-in">
  <span>{esc(FOOTER_LINE)}</span>
  <button class="net-appearance" type="button">◐ auto</button>
</div></footer>
</body></html>"""


def press_card(press):
    return (
        f'<a class="net-press" href="{profile_path(press)}">'
        f"<h3>{esc(press.title)}</h3>"
        + (
            f'<p class="net-press-desc">{esc(press.description)}</p>'
            if press.description
            else ""
        )
        + f'<div class="net-facts">{_facts(press)}</div>'
        + _tags(press.tags)
        + "</a>"
    )


def edition_row(edition, *, show_press):
    kicker = edition.section or edition.series_name
    meta = f"{edition.reading_minutes} min · {nice_date(edition.published)}"
    if show_press:
        meta = f"{esc(edition.press_title)} · {meta}"
    else:
        meta = esc(meta)
    return (
        f'<a class="net-item" href="{esc(edition.url)}" target="_blank" rel="noopener noreferrer">'
        f'<span class="net-kicker">{esc(kicker)}</span>'
        f"<h3>{esc(edition.title)}</h3>"
        + (f'<p class="net-dek">{esc(edition.dek)}</p>' if edition.dek else "")
        + f'<span class="net-meta">{meta}</span></a>'
    )


def render_home(presses):
    if presses:
        cards = "".join(press_card(p) for p in presses)
        count = f"{len(presses)} press{'es' if len(presses) != 1 else ''}"
        directory = f'<span class="net-section-label">{count}</span>{cards}'
    else:
        directory = (
            '<div class="net-empty">No presses yet. '
            f'<a class="net-visit" href="https://github.com/{CANONICAL}" '
            'target="_blank" rel="noopener noreferrer">Make the first one ↗</a></div>'
        )
    body = (
        '<div class="net-hero">'
        f"<h1>{esc(NETWORK_TITLE)}</h1>"
        f'<p class="net-tagline">{esc(TAGLINE)}</p></div>'
        '<div class="net-searchbox">'
        '<input id="net-q" type="search" placeholder="Search every edition…" '
        'aria-label="Search editions" autocomplete="off"></div>'
        '<div class="net-count" id="net-count"></div>'
        '<div class="net-results" id="net-results" hidden></div>'
        f'<div class="net-presses" id="net-presses">{directory}</div>'
    )
    return page(NETWORK_TITLE, body)


def render_profile(press, editions):
    recent = editions[:PROFILE_EDITION_LIMIT]
    rows = "".join(edition_row(e, show_press=False) for e in recent)
    listing = rows or '<div class="net-empty">No published editions yet.</div>'
    body = (
        f'<div class="net-pagehead"><h1>{esc(press.title)}</h1></div>'
        + (
            f'<p class="net-tagline">{esc(press.description)}</p>'
            if press.description
            else ""
        )
        + f'<a class="net-visit" href="{esc(press.url)}" target="_blank" rel="noopener noreferrer">Visit this press →</a>'
        + f'<div class="net-facts">{_facts(press)}</div>'
        + _tags(press.tags)
        + '<span class="net-section-label">Recent editions</span>'
        + f'<div class="net-list">{listing}</div>'
    )
    return page(f"{press.title} — {NETWORK_TITLE}", body)


def render_404():
    body = (
        '<div class="net-pagehead"><h1>Not found</h1></div>'
        '<p class="net-tagline">That page is not part of the network. '
        '<a class="net-visit" href="/">Back to the directory →</a></p>'
    )
    return page(f"Not found — {NETWORK_TITLE}", body)


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def write_site(out, presses, editions, report, *, assets_dir, generated):
    """Emit the full static site + JSON outputs into `out`."""
    by_press = {}
    for edition in editions:
        by_press.setdefault(edition.press_id, []).append(edition)

    _write(os.path.join(out, "index.html"), render_home(presses))
    _write(os.path.join(out, "404.html"), render_404())
    for press in presses:
        profile = render_profile(press, by_press.get(press.id, []))
        _write(os.path.join(out, profile_path(press).strip("/"), "index.html"), profile)

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


def _default_now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

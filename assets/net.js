/* The Nightly Build Network runtime.
 *   1. Appearance: ◐ auto → ○ light → ● dark, persisted in localStorage.
 *   2. One page: an Articles/Authors toggle fused into the search box, a live
 *      hit count, and a ruled card grid rendered from /search.json (articles)
 *      and /presses.json (authors). Ghost "start your own" card is always first.
 * Progressive enhancement: the Articles grid is server-rendered, so the page
 * reads with no JavaScript; this hydrates the toggle, search, and Authors view.
 */
(function () {
  "use strict";

  var CANONICAL = "https://github.com/the-nightly-build/the-nightly-build";
  var APPEARANCE_KEY = "nb-appearance";
  var MODES = ["auto", "light", "dark"];
  var GLYPHS = { auto: "◐ auto", light: "○ light", dark: "● dark" };

  /* ---------------------------------------------------------- appearance */
  function getMode() {
    try {
      var v = localStorage.getItem(APPEARANCE_KEY);
      return MODES.indexOf(v) >= 0 ? v : "auto";
    } catch {
      return "auto";
    }
  }
  function applyMode(mode) {
    var root = document.documentElement;
    if (mode === "auto") root.removeAttribute("data-mode");
    else root.setAttribute("data-mode", mode);
    document.querySelectorAll(".appearance").forEach(function (btn) {
      btn.textContent = GLYPHS[mode];
      btn.setAttribute("aria-label", "appearance: " + mode);
    });
  }
  applyMode(getMode());
  document.addEventListener("click", function (e) {
    if (!e.target.closest(".appearance")) return;
    var next = MODES[(MODES.indexOf(getMode()) + 1) % MODES.length];
    try {
      localStorage.setItem(APPEARANCE_KEY, next);
    } catch {
      /* private mode: still toggles for this page */
    }
    applyMode(next);
  });

  /* -------------------------------------------------------------- directory */
  function esc(s) {
    return (s || "").replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }
  function has(hay, needle) {
    return (hay || "").toLowerCase().indexOf(needle) >= 0;
  }
  function niceDate(iso) {
    var m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso || "");
    if (!m) return "";
    var months = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(" ");
    return months[parseInt(m[2], 10) - 1] + " " + parseInt(m[3], 10);
  }

  function ghostCell() {
    return (
      '<a class="cell ghost" href="' +
      CANONICAL +
      '" target="_blank" rel="noopener noreferrer">' +
      '<span class="ghost-plus">＋</span>' +
      '<span class="ghost-title">Start your own</span>' +
      '<span class="ghost-sub">Fork the repo, run your night shift ↗</span></a>'
    );
  }
  function articleCell(a) {
    return (
      '<a class="cell" href="' +
      esc(a.url) +
      '" target="_blank" rel="noopener noreferrer">' +
      '<span class="eyebrow">' +
      esc(a.section) +
      "</span><h3>" +
      esc(a.title) +
      "</h3>" +
      (a.dek ? '<p class="dek">' + esc(a.dek) + "</p>" : "") +
      '<div class="cardfoot"><span class="left">' +
      esc(a.author_name) +
      '</span><span class="right">' +
      a.reading_minutes +
      " min · " +
      niceDate(a.published) +
      "</span></div></a>"
    );
  }
  function authorCell(s) {
    return (
      '<a class="cell" href="' +
      esc(s.url) +
      '" target="_blank" rel="noopener noreferrer">' +
      '<span class="eyebrow at">@' +
      esc(s.owner) +
      "</span><h3>" +
      esc(s.author_name) +
      "</h3>" +
      (s.description ? '<p class="dek">' + esc(s.description) + "</p>" : "") +
      '<div class="cardfoot"><span class="left">' +
      s.article_count +
      " articles · latest " +
      niceDate(s.latest_published) +
      '</span><span class="right star">★ ' +
      s.stars +
      "</span></div></a>"
    );
  }

  var mode = "articles";
  var articles = [];
  var authors = [];
  var loaded = false;
  var grid = document.getElementById("grid");
  var countLine = document.getElementById("countline");
  var input = document.getElementById("q");
  var wide = window.matchMedia("(min-width: 680px)");

  function paint(cells) {
    if (wide.matches && cells.length % 2 === 1) {
      cells.push('<div class="cell filler" aria-hidden="true"></div>');
    }
    grid.innerHTML = cells.join("");
  }
  function render() {
    if (!loaded) return;
    var q = input.value.trim().toLowerCase();
    if (mode === "articles") {
      var list = articles.filter(function (a) {
        return (
          !q || has(a.title, q) || has(a.dek, q) || has(a.section, q) || has(a.author_name, q)
        );
      });
      countLine.textContent = list.length + (list.length === 1 ? " article" : " articles");
      if (!list.length) return void (grid.innerHTML = empty(q));
      paint([ghostCell()].concat(list.map(articleCell)));
    } else {
      var alist = authors.filter(function (s) {
        return !q || has(s.author_name, q) || has(s.owner, q) || has(s.description, q);
      });
      countLine.textContent = alist.length + (alist.length === 1 ? " author" : " authors");
      if (!alist.length) return void (grid.innerHTML = empty(q));
      paint([ghostCell()].concat(alist.map(authorCell)));
    }
  }
  function empty(q) {
    return '<div class="empty">Nothing matches “' + esc(q) + "”.</div>";
  }
  function setMode(m) {
    mode = m;
    var ta = document.getElementById("tab-articles");
    var tu = document.getElementById("tab-authors");
    if (ta) ta.setAttribute("aria-selected", String(m === "articles"));
    if (tu) tu.setAttribute("aria-selected", String(m === "authors"));
    render();
  }

  function wire() {
    if (!grid || !input) return;
    var ta = document.getElementById("tab-articles");
    var tu = document.getElementById("tab-authors");
    if (ta) ta.addEventListener("click", function () { setMode("articles"); });
    if (tu) tu.addEventListener("click", function () { setMode("authors"); });
    input.addEventListener("input", render);
    wide.addEventListener("change", render);
    Promise.all([
      fetch("/search.json").then(function (r) { return r.ok ? r.json() : []; }),
      fetch("/presses.json").then(function (r) { return r.ok ? r.json() : []; }),
    ]).then(function (data) {
      articles = data[0] || [];
      authors = data[1] || [];
      loaded = true;
      render();
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", wire);
  } else {
    wire();
  }
})();

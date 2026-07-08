/* The Nightly Build Network runtime.
 *   1. Appearance: ◐ auto -> ○ light -> ● dark, persisted in localStorage.
 *   2. Article search: deterministic weighted token match over /search.json
 *      (metadata only; no popularity, no stars, no embeddings — doc §46).
 * Degrades gracefully: with no JS the press directory is a clean static list.
 */
(function () {
  "use strict";

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
    document.querySelectorAll(".net-appearance").forEach(function (btn) {
      btn.textContent = GLYPHS[mode];
      btn.setAttribute("aria-label", "appearance: " + mode);
    });
  }

  function cycleMode() {
    var next = MODES[(MODES.indexOf(getMode()) + 1) % MODES.length];
    try {
      localStorage.setItem(APPEARANCE_KEY, next);
    } catch {
      /* private mode: the toggle still works for this page */
    }
    applyMode(next);
  }

  applyMode(getMode());
  document.addEventListener("click", function (e) {
    if (e.target.closest(".net-appearance")) cycleMode();
  });

  /* -------------------------------------------------------------- search */
  var MAX_RESULTS = 100;
  var FIRST_PAGE = 50;

  function esc(s) {
    return (s || "").replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }

  function tokenize(q) {
    return q
      .toLowerCase()
      .split(/\s+/)
      .filter(function (t) {
        return t.length > 0;
      });
  }

  function prepare(rec) {
    return {
      rec: rec,
      title: (rec.title || "").toLowerCase(),
      dek: (rec.dek || "").toLowerCase(),
      press: (rec.press || "").toLowerCase(),
      series: (rec.series || "").toLowerCase(),
      section: (rec.section || "").toLowerCase(),
      tags: (rec.tags || []).map(function (t) {
        return String(t).toLowerCase();
      }),
    };
  }

  function score(d, q, tokens) {
    var s = 0;
    if (d.title.indexOf(q) >= 0) s += 100; // exact normalized title phrase
    if (
      tokens.every(function (t) {
        return d.title.indexOf(t) >= 0;
      })
    ) {
      s += 60; // all query tokens in the title
    }
    tokens.forEach(function (t) {
      if (d.title.indexOf(t) >= 0) s += 15;
      if (d.tags.indexOf(t) >= 0) s += 25;
      else if (
        d.tags.some(function (tag) {
          return tag.indexOf(t) >= 0;
        })
      ) {
        s += 10;
      }
      if (d.press.indexOf(t) >= 0) s += 12;
      if (d.series.indexOf(t) >= 0) s += 10;
      if (d.section.indexOf(t) >= 0) s += 8;
      if (d.dek.indexOf(t) >= 0) s += 4;
    });
    return s;
  }

  function niceDate(iso) {
    var m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso || "");
    if (!m) return iso || "";
    var months = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(" ");
    return (
      months[parseInt(m[2], 10) - 1] + " " + parseInt(m[3], 10) + ", " + m[1]
    );
  }

  function rankAll(docs, q) {
    var tokens = tokenize(q);
    if (!tokens.length) return [];
    var hits = [];
    for (var i = 0; i < docs.length; i++) {
      var s = score(docs[i], q.toLowerCase(), tokens);
      if (s > 0) hits.push({ d: docs[i], s: s });
    }
    hits.sort(function (a, b) {
      if (b.s !== a.s) return b.s - a.s; // score desc
      var da = a.d.rec.published || "";
      var db = b.d.rec.published || "";
      if (da !== db) return db < da ? -1 : 1; // date desc
      return a.d.title < b.d.title ? -1 : 1; // title asc
    });
    return hits.slice(0, MAX_RESULTS).map(function (h) {
      return h.d.rec;
    });
  }

  function resultRow(rec) {
    var kicker = esc(rec.section || rec.series || "");
    var meta =
      esc(rec.press) +
      " · " +
      rec.reading_minutes +
      " min · " +
      esc(niceDate(rec.published));
    return (
      '<a class="net-item" href="' +
      esc(rec.url) +
      '" target="_blank" rel="noopener noreferrer">' +
      '<span class="net-kicker">' +
      kicker +
      "</span><h3>" +
      esc(rec.title) +
      "</h3>" +
      (rec.dek ? '<p class="net-dek">' + esc(rec.dek) + "</p>" : "") +
      '<span class="net-meta">' +
      meta +
      "</span></a>"
    );
  }

  function wireSearch() {
    var input = document.getElementById("net-q");
    if (!input) return;
    var results = document.getElementById("net-results");
    var directory = document.getElementById("net-presses");
    var count = document.getElementById("net-count");
    var docs = [];
    var shown = FIRST_PAGE;

    function render() {
      var q = input.value.trim();
      if (!q) {
        results.hidden = true;
        results.innerHTML = "";
        if (count) count.textContent = "";
        if (directory) directory.hidden = false;
        return;
      }
      if (directory) directory.hidden = true;
      results.hidden = false;
      var ranked = rankAll(docs, q);
      if (count) {
        count.textContent = ranked.length
          ? ranked.length + (ranked.length === 1 ? " edition" : " editions")
          : "";
      }
      if (!ranked.length) {
        results.innerHTML =
          '<div class="net-empty">No editions match “' + esc(q) + "”.</div>";
        return;
      }
      var html = ranked.slice(0, shown).map(resultRow).join("");
      if (ranked.length > shown) {
        html +=
          '<button class="net-more" type="button" id="net-more">Show more</button>';
      }
      results.innerHTML = html;
      var more = document.getElementById("net-more");
      if (more) {
        more.addEventListener("click", function () {
          shown += FIRST_PAGE;
          render();
        });
      }
    }

    fetch("/search.json")
      .then(function (r) {
        return r.ok ? r.json() : [];
      })
      .then(function (index) {
        docs = index.map(prepare);
        render();
      });

    input.addEventListener("input", function () {
      shown = FIRST_PAGE;
      render();
    });

    var params = new URLSearchParams(location.search);
    if (params.get("q")) {
      input.value = params.get("q");
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", wireSearch);
  } else {
    wireSearch();
  }
})();

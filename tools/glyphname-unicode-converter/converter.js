/*
 * converter.js — UI glue for the LankaGlyphset ⇄ Unicode converter.
 * Uses the shared engine on `window.LankaGlyphset` (lankaglyphset-map.js).
 */
(function () {
  "use strict";
  var L = window.LankaGlyphset;

  var SAMPLE_UNI = ["ක", "කි", "ක්", "ක්‍ර", "ක්‍ෂ", "ක්‍රි", "දා", "ඤා", "රැ",
    "කර්‍", "න්‍ද්‍ර", "ර්‍", "අ", "ා", "ඉ"].join("\n");
  var SAMPLE_NAME = ["ka-sinh", "kI-sinh", "k-sinh", "kRa-sinh", "kSsa-sinh",
    "kRI-sinh", "daa._c-sinh", "nyaa._c-sinh", "rAe-sinh", "ka_repha-sinh",
    "nDRa-sinh", "repha-sinh", "a-sinh", "aasign-sinh"].join("\n");

  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }

  function toast(msg) {
    var t = document.getElementById("toast");
    t.textContent = msg; t.classList.add("show");
    clearTimeout(toast._t);
    toast._t = setTimeout(function () { t.classList.remove("show"); }, 1400);
  }

  function copy(text, label) {
    if (!text) { toast("Nothing to copy"); return; }
    navigator.clipboard.writeText(text).then(
      function () { toast((label || "Copied") + " ✓"); },
      function () { toast("Copy failed"); }
    );
  }

  function badge(kind, tier) {
    if (kind === "canon") return '<span class="badge canon">' + esc(tier || "canonical") + '</span>';
    if (kind === "flag") return '<span class="badge flag">derived</span>';
    return '<span class="badge err">unresolved</span>';
  }

  // Split free-form input into entries. Whitespace/commas separate tokens; inside a
  // token, greedy longest-match against the engine splits unseparated runs
  // (e.g. "කකිදා" or "kakIdaa"). `ok(str)` says whether the engine resolves it.
  function segment(raw, ok, maxLen) {
    var out = [];
    raw.split(/[\s,;،、]+/).forEach(function (tok) {
      if (!tok) return;
      var chars = Array.from(tok), i = 0;
      if (ok(tok)) { out.push(tok); return; }
      while (i < chars.length) {
        var n = Math.min(maxLen, chars.length - i), took = 0;
        for (; n > 0; n--) {
          if (ok(chars.slice(i, i + n).join(""))) { took = n; break; }
        }
        if (!took) took = 1;
        out.push(chars.slice(i, i + took).join(""));
        i += took;
      }
    });
    return out;
  }
  function okUni(s) { return !L.unicodeToName(s).error; }
  function okName(s) { return !L.nameToUnicode(s).error; }

  // ---- Unicode -> Name ----
  var uniResults = [];   // resolved names for "copy all"
  function runUni() {
    var raw = document.getElementById("in-uni").value;
    var lines = segment(raw, okUni, 10);
    var rows = [], nCanon = 0, nFlag = 0, nErr = 0;
    uniResults = [];
    lines.forEach(function (line) {
      var s = line.trim();
      if (s === "") return;
      var r = L.unicodeToName(s);
      if (r.error) {
        nErr++;
        rows.push('<tr><td class="glyph">' + esc(s) + '</td><td class="cp">' +
          esc(r.hex || L.hex(s)) + '</td><td>' + badge("err") +
          '</td><td class="note">no name rule matched</td></tr>');
      } else {
        r.canonical ? nCanon++ : nFlag++;
        uniResults.push(r.name);
        rows.push('<tr class="copyable" data-copy="' + esc(r.name) + '">' +
          '<td class="glyph">' + esc(s) + '</td>' +
          '<td class="cp">' + esc(L.hex(s)) + '</td>' +
          '<td><span class="name">' + esc(r.name) + '</span> ' +
          badge(r.canonical ? "canon" : "flag", r.tier) + '</td>' +
          '<td class="note">' + esc(r.note || "") + '</td></tr>');
      }
    });
    var out = document.getElementById("out-uni");
    if (!rows.length) { out.innerHTML = '<div class="empty">Type or paste Sinhala text above.</div>'; }
    else {
      out.innerHTML = '<table><thead><tr><th>Glyph</th><th class="mono">Codepoints</th>' +
        '<th>LankaGlyphset name</th><th>Note</th></tr></thead><tbody>' +
        rows.join("") + '</tbody></table>';
    }
    document.getElementById("sum-uni").innerHTML =
      '<b>' + uniResults.length + '</b> resolved · <b>' + nCanon + '</b> canonical · <b>' +
      nFlag + '</b> flagged · <b>' + nErr + '</b> unresolved';
  }

  // ---- Name -> Unicode ----
  var nameResults = [];
  function runName() {
    var lines = segment(document.getElementById("in-name").value, okName, 40);
    var rows = [], ok = 0, nErr = 0;
    nameResults = [];
    lines.forEach(function (line) {
      var s = line.trim();
      if (s === "") return;
      var r = L.nameToUnicode(s);
      if (r.error) {
        nErr++;
        rows.push('<tr><td>' + esc(s) + '</td><td class="glyph">—</td>' +
          '<td class="cp"></td><td>' + badge("err") + '</td></tr>');
      } else {
        ok++;
        nameResults.push(r.unicode);
        rows.push('<tr class="copyable" data-copy="' + esc(r.unicode) + '">' +
          '<td class="name">' + esc(s) + '</td>' +
          '<td class="glyph">' + esc(r.unicode) + '</td>' +
          '<td class="cp">' + esc(r.hex) + '</td>' +
          '<td>' + badge(r.canonical ? "canon" : "flag", r.tier) + '</td></tr>');
      }
    });
    var out = document.getElementById("out-name");
    if (!rows.length) { out.innerHTML = '<div class="empty">Type or paste glyph names above.</div>'; }
    else {
      out.innerHTML = '<table><thead><tr><th>Name</th><th>Glyph</th>' +
        '<th class="mono">Codepoints</th><th>Status</th></tr></thead><tbody>' +
        rows.join("") + '</tbody></table>';
    }
    document.getElementById("sum-name").innerHTML =
      '<b>' + ok + '</b> resolved · <b>' + nErr + '</b> unresolved';
  }

  // ---- wiring ----
  document.querySelectorAll(".tab").forEach(function (tab) {
    tab.addEventListener("click", function () {
      document.querySelectorAll(".tab").forEach(function (t) { t.classList.remove("active"); });
      document.querySelectorAll(".panel").forEach(function (p) { p.classList.remove("active"); });
      tab.classList.add("active");
      document.getElementById("panel-" + tab.dataset.mode).classList.add("active");
    });
  });

  document.getElementById("in-uni").addEventListener("input", runUni);
  document.getElementById("in-name").addEventListener("input", runName);

  document.querySelectorAll("[data-sample]").forEach(function (b) {
    b.addEventListener("click", function () {
      if (b.dataset.sample === "uni") { document.getElementById("in-uni").value = SAMPLE_UNI; runUni(); }
      else { document.getElementById("in-name").value = SAMPLE_NAME; runName(); }
    });
  });

  document.querySelectorAll("[data-copy]").forEach(function (b) {
    b.addEventListener("click", function () {
      if (b.dataset.copy === "names") copy(uniResults.join("\n"), uniResults.length + " names copied");
      else if (b.dataset.copy === "strings") copy(nameResults.join("\n"), nameResults.length + " strings copied");
    });
  });

  // Row click-to-copy (delegated).
  document.body.addEventListener("click", function (e) {
    var tr = e.target.closest("tr.copyable");
    if (tr && tr.dataset.copy) copy(tr.dataset.copy, "Copied");
  });

  runUni(); runName();
})();

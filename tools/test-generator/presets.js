/*
 * presets.js — grapheme sets for "what a font has reached" by a design stage or
 * a glyphset level, read from sinhala-design-stages/stages.json.
 *
 *   Presets.build(stagesJson) -> {
 *     stages: [{ n, name, items }],       // cumulative: everything up to stage n
 *     levels: [{ n, label, items }]       // Kernel (0), Core (1)
 *   }
 *
 * `items` are single characters (letters, vowel signs, ං ඃ) and glyph names for
 * the conjunct pieces (rasign-sinh, yasign-sinh, repha-sinh) plus ක්‍ෂ — feed
 * them to SinhalaGraphemes.parseList. A set is meant to be used with "build from
 * parts" on: it lists bases and signs, not every combination.
 *
 * Plus and Pro levels are not offered: stages.json carries no glyph lists for them.
 *
 * Browser: attaches `Presets`. Node: module.exports.
 */
(function (root) {
  "use strict";

  var LETTER_TYPES = { base: 1, vowel: 1, mark: 1, composite: 1, sign: 1 };
  var CONJ = { rakaransaya: "rasign-sinh", yansaya: "yasign-sinh", repaya: "repha-sinh", ksha: "ක්‍ෂ" };

  function collect(data, pred) {
    var rows = [];
    Object.keys(data.glyphs).forEach(function (k) {
      var v = data.glyphs[k];
      if (!pred(v)) return;
      var item = null;
      if (LETTER_TYPES[v.type] && Array.from(k).length === 1 && k !== "෴") item = k;   // ෴ is punctuation
      else if (CONJ[k]) item = CONJ[k];
      if (item) rows.push([v.stage || 0, v.order || 0, item]);
    });
    rows.sort(function (a, b) { return a[0] - b[0] || a[1] - b[1]; });
    return rows.map(function (r) { return r[2]; });
  }

  function build(data) {
    var level = function (v) { return v.level ? parseInt(v.level.split("-")[1], 10) : 99; };
    return {
      stages: data.stages.filter(function (st) { return st.n; }).map(function (st) {
        return { n: st.n, name: st.name, items: collect(data, function (v) { return v.stage <= st.n; }) };
      }),
      levels: [["Kernel", 0], ["Core", 1]].map(function (L) {
        return { n: L[1], label: L[0], items: collect(data, function (v) { return level(v) <= L[1]; }) };
      })
    };
  }

  var api = { build: build };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.Presets = api;
})(typeof globalThis !== "undefined" ? globalThis : this);

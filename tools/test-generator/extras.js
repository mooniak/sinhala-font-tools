/*
 * extras.js — numerals, punctuation, dates and times for generated text.
 *
 * Real Sinhala text is full of figures and marks the corpus words do not
 * supply. Extras makes those items and drops them into a TextGen result,
 * either as lines of their own between sentences or inside a sentence after a
 * word. Items use only digits and punctuation, never letters, so they cannot
 * break a grapheme set. Browser: attaches `Extras`. Node: module.exports.
 */
(function (root) {
  "use strict";

  var SINHALA_DIGITS = "෦෧෨෩෪෫෬෭෮෯";   // U+0DE6..U+0DEF, Sinhala Lith Illakkam

  // marks that appear in running Sinhala text
  var PUNCT = [",", ".", ";", ":", "!", "?", "-", "–", "—", "…", "/", "%", "(", ")", "“”", "‘’"];

  var KINDS = ["number", "date", "time", "punct"];

  function pick(arr, rand) { return arr[Math.floor(rand() * arr.length)]; }
  function int(lo, hi, rand) { return lo + Math.floor(rand() * (hi - lo + 1)); }
  function pad(n) { return n < 10 ? "0" + n : "" + n; }

  /** Western digits to the chosen script: "latin", "sinhala" or "mixed" (per item). */
  function digits(text, script, rand) {
    if (script === "mixed") script = rand() < 0.5 ? "sinhala" : "latin";
    if (script !== "sinhala") return text;
    return text.replace(/[0-9]/g, function (d) { return SINHALA_DIGITS.charAt(+d); });
  }

  function group(n) { return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ","); }

  function number(rand) {
    var r = rand();
    if (r < 0.3) return String(int(0, 99, rand));
    if (r < 0.55) return String(int(100, 9999, rand));
    if (r < 0.75) return group(int(10000, 9999999, rand));
    if (r < 0.9) return int(0, 999, rand) + "." + pad(int(0, 99, rand));
    return int(1, 100, rand) + "%";
  }

  function date(rand) {
    var y = int(1950, 2035, rand), m = int(1, 12, rand), d = int(1, [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1], rand);
    switch (int(0, 3, rand)) {
      case 0: return y + "-" + pad(m) + "-" + pad(d);
      case 1: return pad(d) + "/" + pad(m) + "/" + y;
      case 2: return y + "." + pad(m) + "." + pad(d);
      default: return d + "-" + m + "-" + y;
    }
  }

  function time(rand) {
    var h = int(0, 23, rand), m = int(0, 59, rand);
    switch (int(0, 2, rand)) {
      case 0: return pad(h) + ":" + pad(m);
      case 1: return (h % 12 || 12) + "." + pad(m);
      default: return pad(h) + ":" + pad(m) + ":" + pad(int(0, 59, rand));
    }
  }

  function punct(rand) { return pick(PUNCT, rand); }

  var MAKERS = { number: number, date: date, time: time, punct: punct };

  /**
   * One item. opts.kinds: subset of KINDS (default all); opts.script:
   * "latin" (default), "sinhala" or "mixed". Punctuation is never converted.
   */
  function item(opts, rand) {
    var kinds = (opts.kinds || KINDS).filter(function (k) { return MAKERS[k]; });
    if (!kinds.length) return "";
    var kind = pick(kinds, rand);
    var text = MAKERS[kind](rand);
    return kind === "punct" ? text : digits(text, opts.script || "latin", rand);
  }

  /**
   * Add items to a TextGen result (sentences: arrays of { t, w, inv } pieces),
   * returning a new result; the input is untouched. Options:
   *   kinds    which of number / date / time / punct to draw from (none = no-op)
   *   script   digit script: latin, sinhala or mixed
   *   rate     0..1 share of sentences that get an item
   *   place    "between" (an item on its own, after a sentence; own line in the
   *            one-per-line layout) or "within" (inside the sentence, after a
   *            word)
   *   seed     for a repeatable result
   */
  function apply(result, opts) {
    var kinds = (opts && opts.kinds || []).filter(function (k) { return MAKERS[k]; });
    var rate = opts && opts.rate != null ? opts.rate : 0.5;
    if (!kinds.length || rate <= 0 || !result.sentences.length || result.mode === "pseudo") return result;
    var rand = require_rng()(((opts.seed >>> 0) ^ 0x9e3779b9) >>> 0);
    var place = opts.place === "within" ? "within" : "between";
    var out = [];
    result.sentences.forEach(function (sent) {
      if (rand() >= rate) { out.push(sent); return; }
      var text = item({ kinds: kinds, script: opts.script }, rand);
      if (place === "between") {
        out.push(sent);
        out.push([{ t: text, w: false, inv: false }]);
        return;
      }
      var slots = [];   // positions right after a word
      sent.forEach(function (p, i) { if (p.w) slots.push(i + 1); });
      var at = slots.length ? pick(slots, rand) : sent.length;
      var copy = sent.slice();
      copy.splice(at, 0, { t: " " + text, w: false, inv: false });
      out.push(copy);
    });
    return Object.assign({}, result, { sentences: out });
  }

  function require_rng() {
    if (root.TextGen) return root.TextGen.rng;
    return require("./textgen.js").rng;
  }

  var api = { apply: apply, item: item, digits: digits, KINDS: KINDS, SINHALA_DIGITS: SINHALA_DIGITS };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.Extras = api;
})(typeof globalThis !== "undefined" ? globalThis : this);

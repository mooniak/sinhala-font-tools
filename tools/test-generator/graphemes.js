/*
 * graphemes.js — Sinhala visual-grapheme segmentation and matching.
 *
 * A grapheme here is the unit a type designer draws or composes: a consonant
 * with its virama / vowel signs (ටු, කෝ, ක්), a ZWJ conjunct with its signs
 * (ක්‍ෂ, ක්‍රි, ර්‍කා), an independent vowel, or a spacing sign standing on
 * its own (ං, ඃ). Whether a font draws ටු as one glyph or composes it from
 * ට + ු does not matter: ටු is one grapheme either way.
 *
 * Graphemes are identified by their (NFC) Unicode string. Names come from the
 * LankaGlyphset converter (../glyphname-unicode-converter/lankaglyphset-map.js)
 * and are labels only.
 *
 * Pure vanilla JS. Browser: attaches `SinhalaGraphemes`. Node: module.exports.
 */
(function (root) {
  "use strict";

  var AL = 0x0dca, ZWJ = 0x200d, ZWNJ = 0x200c, RA = 0x0dbb, YA = 0x0dba;
  var RASIGN = "්‍ර";   // ්‍ර  rakaransaya
  var YASIGN = "්‍ය";   // ්‍ය  yansaya
  var REPHA = "ර්‍";    // ර්‍  repaya

  // Parts that are not plain code points get their own names.
  var PART_NAMES = {};
  PART_NAMES[RASIGN] = "rasign-sinh";
  PART_NAMES[YASIGN] = "yasign-sinh";
  PART_NAMES[REPHA] = "repha-sinh";

  function isCons(c) {
    return c >= 0x0d9a && c <= 0x0dc6 && c !== 0x0db2 && c !== 0x0dbc &&
      c !== 0x0dbe && c !== 0x0dbf;
  }
  function isIndepVowel(c) { return c >= 0x0d85 && c <= 0x0d96; }
  function isVowelSign(c) {
    return (c >= 0x0dcf && c <= 0x0dd4) || c === 0x0dd6 ||
      (c >= 0x0dd8 && c <= 0x0ddf) || c === 0x0df2 || c === 0x0df3;
  }
  function isSinhala(c) { return (c >= 0x0d80 && c <= 0x0dff) || (c >= 0x111e1 && c <= 0x111f4); }

  function cpsOf(str) {
    var out = [];
    for (var ch of str) out.push(ch.codePointAt(0));
    return out;
  }
  function str(cps) { return String.fromCodePoint.apply(null, cps); }

  /**
   * Split text into graphemes. Returns [{ g: string, parts: [string], sinhala: bool }].
   * `parts` is the grapheme broken into the pieces a font may compose it from:
   * base consonant / conjunct pieces first, then each sign.
   */
  function segment(text) {
    var cps = cpsOf(String(text).normalize("NFC"));
    var out = [];
    var i = 0, n = cps.length;
    while (i < n) {
      var c = cps[i];
      if (c === ZWJ || c === ZWNJ) { i++; continue; }

      if (isCons(c) || isIndepVowel(c)) {
        var g = [c];
        var parts = [];
        var base = [c];
        i++;
        if (isCons(c)) {
          // ZWJ conjunct links: C ් ZWJ C (also tolerate the old C ZWJ ් C order).
          for (;;) {
            var link = null;
            if (cps[i] === AL && cps[i + 1] === ZWJ && isCons(cps[i + 2])) link = cps[i + 2];
            else if (cps[i] === ZWJ && cps[i + 1] === AL && isCons(cps[i + 2])) link = cps[i + 2];
            if (link === null) break;
            g.push(AL, ZWJ, link);
            if (link === RA || link === YA) {
              // rakaransaya / yansaya: a sign piece of its own.
              parts.push(str(base));
              base = [];
              parts.push(link === RA ? RASIGN : YASIGN);
            } else if (base.length === 1 && base[0] === RA && parts.length === 0) {
              // leading ර්‍ : repaya over the next consonant.
              parts.push(REPHA);
              base = [link];
            } else {
              base.push(AL, ZWJ, link);
            }
            i += 3;
          }
        }
        if (base.length) parts.push(str(base));
        // virama (bare, or a word-final ්‍ with nothing to join to)
        if (cps[i] === AL) {
          g.push(AL); parts.push("්"); i++;
          if (cps[i] === ZWJ) i++;
        }
        while (i < n && (isVowelSign(cps[i]) || cps[i] === AL)) {
          g.push(cps[i]); parts.push(str([cps[i]])); i++;
        }
        out.push({ g: str(g), parts: parts, sinhala: true });
        continue;
      }

      // Anything else stands alone: ං ඃ, a stray sign, a numeral, a non-Sinhala char.
      out.push({ g: str([c]), parts: [str([c])], sinhala: isSinhala(c) });
      i++;
    }
    return out;
  }

  // ---- names ----------------------------------------------------------

  var conv = root.LankaGlyphset || (typeof require === "function" ? safeRequire() : null);
  function safeRequire() {
    try { return require("../glyphname-unicode-converter/lankaglyphset-map.js"); } catch (e) { return null; }
  }

  var nameCache = new Map();
  var byName = new Map();   // name -> grapheme string (filled as graphemes are named)

  function hex(s) {
    return cpsOf(s).map(function (c) { return "U+" + c.toString(16).toUpperCase().padStart(4, "0"); }).join(" ");
  }

  /** LankaGlyphset-style name for a grapheme string. */
  function nameOf(g) {
    if (nameCache.has(g)) return nameCache.get(g);
    var name = PART_NAMES[g] || null;
    if (!name && conv) {
      var r = conv.unicodeToName(g);
      if (r && r.name) name = r.name;
    }
    if (!name) {
      var cps = cpsOf(g);
      name = cps.length === 1 && cps[0] < 0x80 ? g : "uni" + cps.map(function (c) {
        return c.toString(16).toUpperCase().padStart(4, "0");
      }).join("_");
    }
    nameCache.set(g, name);
    if (!byName.has(name)) byName.set(name, g);
    return name;
  }

  /** Grapheme string for a name, or null. Accepts names with or without "-sinh". */
  function fromName(name) {
    var cands = /-sinh$/.test(name) ? [name] : [name + "-sinh", name];
    for (var k = 0; k < cands.length; k++) {
      if (byName.has(cands[k])) return byName.get(cands[k]);
      for (var p in PART_NAMES) if (PART_NAMES[p] === cands[k]) return p;
      if (conv) {
        var r = conv.nameToUnicode(cands[k]);
        if (r && r.unicode) return r.unicode.normalize("NFC");
      }
    }
    return null;
  }

  /**
   * Parse a free-form grapheme list: glyph names ("ttI-sinh", "ka") and/or
   * Sinhala text (segmented into graphemes). Returns { graphemes: [string], unknown: [string] }.
   */
  function parseList(text) {
    var seen = new Set(), list = [], unknown = [];
    function add(g) { if (!seen.has(g)) { seen.add(g); list.push(g); } }
    String(text).split(/[\s,;]+/).forEach(function (tok) {
      if (!tok) return;
      if (/^[A-Za-z][A-Za-z0-9._-]*$/.test(tok)) {
        var g = fromName(tok);
        if (g) add(g); else unknown.push(tok);
      } else {
        segment(tok).forEach(function (s) { if (s.sinhala) add(s.g); });
      }
    });
    return { graphemes: list, unknown: unknown };
  }

  // ---- matching -------------------------------------------------------

  /**
   * Is grapheme `seg` available from `set` (a Set of grapheme strings)?
   * exact: only the grapheme itself counts.
   * fromParts: it may also be assembled from listed pieces — any split of its
   *   parts into contiguous runs that are each in the set (ක්‍රි = ක්‍ර + ි or ක + ්‍ර + ි).
   * Returns "exact", "parts", or "".
   */
  function availability(seg, set, fromParts) {
    if (set.has(seg.g)) return "exact";
    if (!fromParts || seg.parts.length < 2) return "";
    var p = seg.parts, n = p.length, ok = [true];
    for (var e = 1; e <= n; e++) {
      ok[e] = false;
      var piece = "";
      for (var s = e - 1; s >= 0; s--) {
        piece = p[s] + piece;
        if (ok[s] && set.has(piece)) { ok[e] = true; break; }
      }
    }
    return ok[n] ? "parts" : "";
  }

  // ---- decomposition --------------------------------------------------

  var SIGN_PARTS = new Set("ා ැ ෑ ි ී ු ූ ෘ ෲ ෟ ෳ ෙ ේ ෛ ො ෝ ෞ ්".split(" "));

  /**
   * Split one grapheme into its base and the sign it carries:
   *   { base, sign, kind }  kind: "C" consonant/conjunct, "V" independent vowel,
   *   "M" a spacing mark standing alone (ං ඃ). `sign` is "" for a bare base, so
   *   ට → {ට, ""}, ටු → {ට, ු}, ක්‍රි → {ක්‍ර, ි}, ක් → {ක, ්}.
   */
  function decompose(g) {
    var c = g.codePointAt(0);
    if (g === "ං" || g === "ඃ") return { base: "", sign: g, kind: "M" };
    if (c >= 0x0d85 && c <= 0x0d96) return { base: g, sign: "", kind: "V" };
    var seg = segment(g)[0], p = seg ? seg.parts : [g], i = p.length - 1, sign = "";
    while (i > 0 && SIGN_PARTS.has(p[i])) { sign = p[i] + sign; i--; }
    return { base: p.slice(0, i + 1).join(""), sign: sign, kind: "C" };
  }

  var api = {
    segment: segment,
    decompose: decompose,
    nameOf: nameOf,
    fromName: fromName,
    parseList: parseList,
    availability: availability,
    hex: hex,
    isSinhala: isSinhala
  };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.SinhalaGraphemes = api;
})(typeof globalThis !== "undefined" ? globalThis : this);

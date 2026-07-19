/*
 * lankaglyphset-map.js
 * =====================
 * Bidirectional converter between LankaGlyphset glyph names (the "-sinh"
 * naming standard) and the Sinhala Unicode string each name renders.
 *
 *   unicodeToName("කි")  -> "kI-sinh"        (U+0D9A U+0DD2)
 *   nameToUnicode("kRa-sinh") -> "ක්‍ර"     (U+0D9A U+0DCA U+200D U+0DBB)
 *
 * The naming rules follow the LankaGlyphset standard (glyphset YAMLs at
 *   glyphsets/sinhala-{0-kernel,1-core,2-plus,3-pro}.yaml; see
 *   docs/naming-standard.md and docs/adopting-the-standard.md);
 * the codepoint tables mirror tools/font-coverage/font_coverage.py.
 *
 * Pure vanilla JS. Works in the browser (attaches `LankaGlyphset` to the global
 * scope) and under Node (module.exports at the bottom).
 */
(function (root) {
  "use strict";

  var NS = "-sinh";
  var AL = 0x0dca;   // al-lakuna / virama  ්
  var ZWJ = 0x200d;  // zero-width joiner   ‍
  var RA = 0x0dbb;   // ර
  var YA = 0x0dba;   // ය

  // Consonant codepoint -> virama-form stem (name without inherent 'a').
  var CONS_STEM = {
    0x0d9a: "k",  0x0d9b: "kh", 0x0d9c: "g",  0x0d9d: "gh", 0x0d9e: "ng",
    0x0d9f: "nng", 0x0da0: "c", 0x0da1: "ch", 0x0da2: "j",  0x0da3: "jh",
    0x0da4: "ny", 0x0da5: "jny", 0x0da6: "nyj",
    0x0da7: "tt", 0x0da8: "tth", 0x0da9: "dd", 0x0daa: "ddh", 0x0dab: "nn",
    0x0dac: "nndd",
    0x0dad: "t",  0x0dae: "th", 0x0daf: "d",  0x0db0: "dh", 0x0db1: "n",
    0x0db3: "nd",
    0x0db4: "p",  0x0db5: "ph", 0x0db6: "b",  0x0db7: "bh", 0x0db8: "m",
    0x0db9: "mb",
    0x0dba: "y",  0x0dbb: "r",  0x0dbd: "l",  0x0dc0: "v",
    0x0dc1: "sh", 0x0dc2: "ss", 0x0dc3: "s",  0x0dc4: "h",  0x0dc5: "ll",
    0x0dc6: "f"
  };

  // Independent vowel codepoint -> name.
  var INDEP_VOWEL = {
    0x0d85: "a", 0x0d86: "aa", 0x0d87: "ae", 0x0d88: "aae",
    0x0d89: "i", 0x0d8a: "ii", 0x0d8b: "u", 0x0d8c: "uu",
    0x0d8d: "vocalicr", 0x0d8e: "vocalicrr",
    0x0d8f: "vocalicl", 0x0d90: "vocalicll",
    0x0d91: "e", 0x0d92: "ee", 0x0d93: "ai",
    0x0d94: "o", 0x0d95: "oo", 0x0d96: "au"
  };

  // Vowel signs that ligate above/below for every consonant -> capital suffix.
  var VSIGN_LIG = { 0x0dd2: "I", 0x0dd3: "Ii", 0x0dd4: "U", 0x0dd6: "Uu" };

  // "Below/spacing" vowel signs -> (lowercase word, capitalised suffix).
  // lowercase word used in ._c below-base forms; capital used for ra ligatures.
  var VSIGN_BELOW = {
    0x0dcf: ["aa", "Aa"], 0x0dd0: ["ae", "Ae"], 0x0dd1: ["aae", "Aae"],
    0x0dd8: ["vocalicr", "Vocalicr"], 0x0df2: ["vocalicrr", "Vocalicrr"],
    0x0ddf: ["vocalicl", "Vocalicl"], 0x0df3: ["vocalicll", "Vocalicll"],
    0x0dd9: ["e", "E"], 0x0dda: ["ee", "Ee"], 0x0ddb: ["ai", "Ai"],
    0x0ddc: ["o", "O"], 0x0ddd: ["oo", "Oo"], 0x0dde: ["au", "Au"]
  };

  // A vowel sign standing on its own -> its sign glyph name.
  var SIGN_ALONE = {
    0x0dcf: "aasign", 0x0dd0: "aesign", 0x0dd1: "aaesign",
    0x0dd2: "isign", 0x0dd3: "iisign", 0x0dd4: "usign", 0x0dd6: "uusign",
    0x0dd8: "vocalicrsign", 0x0df2: "vocalicrrsign",
    0x0ddf: "vocaliclsign", 0x0df3: "vocalicllsign",
    0x0dd9: "esign", 0x0dda: "eesign", 0x0ddb: "aisign",
    0x0ddc: "osign", 0x0ddd: "oosign", 0x0dde: "ausign",
    0x0dca: "virama",
    0x0d82: "anusvaraya", 0x0d83: "visargaya", 0x0df4: "kunddaliya"
  };

  // Consonants whose cluster takes the below-base "._c" form when a
  // below/spacing vowel sign attaches. Keyed by the LEADING consonant.
  var DA_SHAPE_FIRST = { 0x0daf: 1, 0x0da4: 1, 0x0da5: 1, 0x0db3: 1 };

  function dropA(s) { return s.charAt(s.length - 1) === "a" ? s.slice(0, -1) : s; }
  function cap(s) { return s.charAt(0).toUpperCase() + s.slice(1); }
  function baseA(cp) { return CONS_STEM[cp] + "a"; }
  function isCons(cp) { return CONS_STEM.hasOwnProperty(cp); }

  function toCps(str) {
    var out = [];
    for (var i = 0; i < str.length; ) {
      var cp = str.codePointAt(i);
      out.push(cp);
      i += cp > 0xffff ? 2 : 1;
    }
    return out;
  }

  function hex(str) {
    return toCps(str).map(function (c) {
      return "U+" + c.toString(16).toUpperCase().padStart(4, "0");
    }).join(" ");
  }

  // Collapse FM two-part encodings: vocalicrr written as two vocalicr signs
  // (ෘෘ -> ෟ 0DF2), and aisign written as two esign / kombu (ෙෙ -> ෛ 0DDB).
  function normalizeCps(cps) {
    var out = [];
    for (var i = 0; i < cps.length; i++) {
      if (cps[i] === 0x0dd8 && cps[i + 1] === 0x0dd8) { out.push(0x0df2); i++; }
      else if (cps[i] === 0x0dd9 && cps[i + 1] === 0x0dd9) { out.push(0x0ddb); i++; }
      else out.push(cps[i]);
    }
    return out;
  }

  /* -------- Unicode string -> LankaGlyphset name -------------------------- */

  // Returns { name, canonical, note } or { error }.
  function unicodeToName(str) {
    if (str == null) return { error: "empty" };
    // Drop trailing whitespace and spreadsheet annotations like " (Alt)".
    str = String(str).replace(/\s+\(.*\)\s*$/, "").replace(/\s+$/, "");
    if (str === "") return { error: "empty" };
    var cps = normalizeCps(toCps(str));
    var r = _clusterName(cps);
    if (!r) return { error: "unresolved", hex: hex(str) };
    var f = _finalize(r.stem);
    f.note = r.note || "";
    return f;
  }

  // Turn a bare stem into the final glyph name, applying the namespace rule
  // (Punctuation / Format-control glyphs carry no "-sinh") and looking up the
  // authoritative glyphset tier. Names the engine forms by rule but which the
  // glyphset does not enumerate are tagged tier:"derived" (valid ligatures).
  function _finalize(stem) {
    var withNs = stem + NS;
    if (GLYPHSET[withNs])
      return { name: withNs, tier: GLYPHSET[withNs].tier, canonical: true };
    if (GLYPHSET[stem])   // e.g. kunddaliya (Punctuation, no namespace)
      return { name: stem, tier: GLYPHSET[stem].tier, canonical: true };
    return { name: withNs, tier: "derived", canonical: false };
  }

  // Core assembler. Returns { stem, note } or null if unparseable.
  function _clusterName(cps) {
    if (cps.length === 0) return null;

    // Single standalone sign / independent vowel.
    if (cps.length === 1) {
      if (SIGN_ALONE[cps[0]]) return { stem: SIGN_ALONE[cps[0]] };
      if (INDEP_VOWEL[cps[0]]) return { stem: INDEP_VOWEL[cps[0]] };
    }
    // Standalone repaya sign  ර්‍  (ra + virama + ZWJ).
    if (cps.length === 3 && cps[0] === RA && cps[1] === AL && cps[2] === ZWJ)
      return { stem: "repha", note: "repaya sign" };
    // Standalone vowel sign + virama  (ා්  ->  aasign_virama).
    if (cps.length === 2 && SIGN_ALONE[cps[0]] && cps[1] === AL && cps[0] !== AL) {
      if (VSIGN_BELOW[cps[0]] || VSIGN_LIG[cps[0]])
        return { stem: SIGN_ALONE[cps[0]] + "_virama", note: "sign + virama" };
    }
    if (INDEP_VOWEL[cps[0]] && cps.length === 1) return { stem: INDEP_VOWEL[cps[0]] };

    // Leading yansaya:  ්‍ය …   (AL ZWJ ya …)
    if (cps[0] === AL && cps[1] === ZWJ && cps[2] === YA)
      return _yansaAlone(cps);

    // Must start with a consonant from here on.
    if (!isCons(cps[0])) return null;

    // 1. Read the stacked consonant cluster (conjuncts / rakaransaya / yansaya).
    var consList = [cps[0]];
    var i = 1;
    var special = [];            // per stacked consonant: "R", "y", or "conj"
    while (cps[i] === AL && cps[i + 1] === ZWJ && isCons(cps[i + 2])) {
      var c = cps[i + 2];
      consList.push(c);
      special.push(c === RA ? "R" : (c === YA ? "y" : "conj"));
      i += 3;
    }

    // 2. Consume the modifiers — vowel sign, repaya (ra AL ZWJ) and a trailing
    //    virama — in whatever order they appear (repaya may follow the vowel,
    //    e.g. දුර්‍ = da + usign + repaya).
    var repaya = false, vowel = null, trailingVirama = false;
    while (i < cps.length) {
      if (!repaya && cps[i] === RA && cps[i + 1] === AL && cps[i + 2] === ZWJ) {
        repaya = true; i += 3; continue;
      }
      if (!vowel && (VSIGN_LIG[cps[i]] || VSIGN_BELOW[cps[i]])) {
        vowel = cps[i]; i++; continue;
      }
      if (!trailingVirama && cps[i] === AL) { trailingVirama = true; i++; continue; }
      break;
    }
    if (i !== cps.length) return null;   // leftover -> unparseable

    // ---- Build the core cluster string (normally ends in inherent 'a'). ----
    var core = baseA(consList[0]);
    for (var k = 1; k < consList.length; k++) {
      if (special[k - 1] === "R") core = dropA(core) + "Ra";
      else if (special[k - 1] === "y") core = dropA(core) + "ya";
      else core = dropA(core) + cap(baseA(consList[k]));
    }

    var daShape = _isDaShape(consList);
    var raBase = consList.length === 1 && consList[0] === RA;
    var note = "";
    var stem, belowDa = false;

    // Apply the vowel sign (or bare / virama form).
    if (vowel && VSIGN_LIG[vowel]) {
      stem = dropA(core) + VSIGN_LIG[vowel];
    } else if (vowel && VSIGN_BELOW[vowel]) {
      var low = VSIGN_BELOW[vowel][0], capv = VSIGN_BELOW[vowel][1];
      if (daShape) { stem = dropA(core) + low; belowDa = true; note = "below-base da-form"; }
      else if (raBase) { stem = dropA(core) + capv; note = "ra vowel ligature"; }
      else { stem = dropA(core) + capv; note = "spacing-vowel ligature (verify)"; }
    } else {
      stem = trailingVirama ? dropA(core) : core;
    }

    // A trailing virama that sits AFTER a vowel sign (e.g. daa් -> daa_virama).
    if (vowel && trailingVirama) stem += "_virama";
    // Below-base da-forms carry the "._c" wrapper (after any _virama).
    if (belowDa) stem += "._c";
    // Repaya joins the whole cluster with an underscore.
    if (repaya) { stem += "_repha"; note = note ? note + "+repaya" : "repaya"; }

    return { stem: stem, note: note };
  }

  function _isDaShape(consList) {
    if (DA_SHAPE_FIRST[consList[0]]) return true;
    // nDa conjunct: n + da
    if (consList[0] === 0x0db1 && consList[1] === 0x0daf) return true;
    return false;
  }

  // Standalone yansaya:  ්‍ය …
  function _yansaAlone(cps) {
    var i = 3;                       // past AL ZWJ ya
    var stem = "yasign", note = "yansaya";
    // repaya after ya
    if (cps[i] === RA && cps[i + 1] === AL && cps[i + 2] === ZWJ) {
      stem += "_repha"; i += 3;
    }
    if (VSIGN_LIG[cps[i]]) { stem += "_" + SIGN_ALONE[cps[i]]; i++; }
    else if (VSIGN_BELOW[cps[i]]) { stem += "_" + SIGN_ALONE[cps[i]]; i++; }
    if (cps[i] === AL) { stem += "_virama"; i++; }
    if (i !== cps.length) return null;
    return { stem: stem, note: note };
  }

  /* -------- LankaGlyphset name -> Unicode string -------------------------- */
  // Built by inverting unicodeToName over a generated candidate set + the FM
  // corpus (see buildIndex). Direct-parse fallback covers simple names.

  var _forward = null;   // name -> unicode string

  function _ensureIndex() {
    if (_forward) return;
    _forward = {};
    var seqs = _candidateSequences();
    for (var s = 0; s < seqs.length; s++) {
      var seq = seqs[s];
      var r = unicodeToName(seq);
      if (r.name && !(r.name in _forward)) _forward[r.name] = seq;
    }
  }

  // Generate the productive Sinhala orthographic sequences from the standard's
  // own building blocks (no external corpus) so every well-formed LankaGlyphset
  // name — bases, virama forms, vowel ligatures, rakaransaya, repaya, yansaya
  // and the two-consonant conjuncts — is resolvable name->unicode.
  var _AL = String.fromCodePoint(AL), _ZWJ = String.fromCodePoint(ZWJ);
  var _RA = String.fromCodePoint(RA), _YA = String.fromCodePoint(YA);
  var _LIG = [0x0dd2, 0x0dd3, 0x0dd4, 0x0dd6];                 // I Ii U Uu
  var _BELOW = [0x0dcf, 0x0dd0, 0x0dd1, 0x0dd8, 0x0df2];       // aa ae aae vocalicr vocalicrr

  function _candidateSequences() {
    var out = [], cp, k;
    for (cp in INDEP_VOWEL) out.push(String.fromCodePoint(+cp));
    for (cp in SIGN_ALONE) out.push(String.fromCodePoint(+cp));
    // standalone repaya / yansaya signs and yansaya + vowels
    out.push(_RA + _AL + _ZWJ);                                 // repha
    _pushCluster(out, _AL + _ZWJ + _YA);                        // yasign …

    var cons = Object.keys(CONS_STEM).map(Number);
    for (var a = 0; a < cons.length; a++) {
      var ch = String.fromCodePoint(cons[a]);
      _pushCluster(out, ch);                                    // base + all modifiers
      out.push(ch + _RA + _AL + _ZWJ);                          // repaya  C ර ් ‍
      _pushCluster(out, ch + _AL + _ZWJ + _RA);                 // rakaransaya  C ් ‍ ර …
      _pushCluster(out, ch + _AL + _ZWJ + _YA);                 // yansaya      C ් ‍ ය …
      // two-consonant conjuncts  C ් ‍ C …
      for (var b = 0; b < cons.length; b++) {
        var base = ch + _AL + _ZWJ + String.fromCodePoint(cons[b]);
        _pushCluster(out, base);
        _pushCluster(out, base + _AL + _ZWJ + _RA);             // conjunct + rakaransaya
      }
    }
    if (_corpus) for (k = 0; k < _corpus.length; k++) out.push(_corpus[k]);
    return out;
  }

  // Emit a cluster prefix plus its bare / virama / vowel-sign variants (and the
  // vowel+virama forms the below-base "._c" glyphs use).
  function _pushCluster(out, prefix) {
    out.push(prefix);
    out.push(prefix + _AL);
    var i;
    for (i = 0; i < _LIG.length; i++) out.push(prefix + String.fromCodePoint(_LIG[i]));
    for (i = 0; i < _BELOW.length; i++) {
      out.push(prefix + String.fromCodePoint(_BELOW[i]));
      out.push(prefix + String.fromCodePoint(_BELOW[i]) + _AL);
    }
  }

  var _corpus = null;
  // Optional: feed extra attested Unicode strings so their names also resolve
  // name->unicode. Not required — the generator above covers the standard.
  function registerCorpus(list) { _corpus = (list || []).slice(); _forward = null; }

  function nameToUnicode(name) {
    if (name == null) return { error: "empty" };
    name = String(name).trim();
    if (name === "") return { error: "empty" };
    // Accept names with or without the "-sinh" namespace; punctuation glyphs
    // (kunddaliya) live in the glyphset under their bare name.
    var lookup = name;
    if (!(lookup in GLYPHSET) && !/-(taml|sinh)$/.test(lookup) &&
        (lookup + NS in GLYPHSET || true)) {
      if (!(lookup in GLYPHSET)) lookup = name + NS;
    }
    var tier = GLYPHSET[lookup] ? GLYPHSET[lookup].tier
             : (GLYPHSET[name] ? GLYPHSET[name].tier : "derived");
    var canonical = (lookup in GLYPHSET) || (name in GLYPHSET);
    _ensureIndex();
    var seq = _forward[lookup] || _forward[name];
    if (seq != null)
      return { unicode: seq, hex: hex(seq), canonical: canonical, tier: tier };
    return { error: "unresolved", canonical: canonical, tier: tier };
  }

  /* -------- Glyphset (authoritative name -> {tier, unicode, ...}) ---------
   * Generated from glyphsets/sinhala-{0-kernel,1-core,2-plus,3-pro}.yaml. Keys are the
   * full glyph names (with the "-sinh" namespace, except Punctuation / Format
   * controls). Regenerate with build-glyphset.js when the YAML changes. */
  var GLYPHSET = {"space":{"tier":"kernel","category":"Format controls"},"zerowidthjoiner":{"tier":"kernel","category":"Format controls","unicode":"U+200D"},"exclam":{"tier":"kernel","category":"Punctuation"},"quotedbl":{"tier":"kernel","category":"Punctuation"},"numbersign":{"tier":"kernel","category":"Punctuation"},"percent":{"tier":"kernel","category":"Punctuation"},"quotesingle":{"tier":"kernel","category":"Punctuation"},"parenleft":{"tier":"kernel","category":"Punctuation"},"parenright":{"tier":"kernel","category":"Punctuation"},"asterisk":{"tier":"kernel","category":"Punctuation"},"plus":{"tier":"kernel","category":"Punctuation"},"comma":{"tier":"kernel","category":"Punctuation"},"hyphen":{"tier":"kernel","category":"Punctuation"},"period":{"tier":"kernel","category":"Punctuation"},"slash":{"tier":"kernel","category":"Punctuation"},"colon":{"tier":"kernel","category":"Punctuation"},"semicolon":{"tier":"kernel","category":"Punctuation"},"less":{"tier":"kernel","category":"Punctuation"},"equal":{"tier":"kernel","category":"Punctuation"},"greater":{"tier":"kernel","category":"Punctuation"},"question":{"tier":"kernel","category":"Punctuation"},"bracketleft":{"tier":"kernel","category":"Punctuation"},"backslash":{"tier":"kernel","category":"Punctuation"},"bracketright":{"tier":"kernel","category":"Punctuation"},"underscore":{"tier":"kernel","category":"Punctuation"},"periodcentered":{"tier":"kernel","category":"Punctuation"},"multiply":{"tier":"kernel","category":"Punctuation"},"divide":{"tier":"kernel","category":"Punctuation"},"endash":{"tier":"kernel","category":"Punctuation"},"emdash":{"tier":"kernel","category":"Punctuation"},"quoteleft":{"tier":"kernel","category":"Punctuation"},"quoteright":{"tier":"kernel","category":"Punctuation"},"quotedblleft":{"tier":"kernel","category":"Punctuation"},"quotedblright":{"tier":"kernel","category":"Punctuation"},"bullet":{"tier":"kernel","category":"Punctuation"},"a-sinh":{"tier":"kernel","category":"Letters","unicode":"U+0D85"},"aa-sinh":{"tier":"kernel","category":"Letters","unicode":"U+0D86","decompose":["a","aasign"]},"ae-sinh":{"tier":"kernel","category":"Letters","unicode":"U+0D87","decompose":["a","aesign"]},"aae-sinh":{"tier":"kernel","category":"Letters","unicode":"U+0D88","decompose":["a","aaesign"]},"i-sinh":{"tier":"kernel","category":"Letters","unicode":"U+0D89"},"ii-sinh":{"tier":"kernel","category":"Letters","unicode":"U+0D8A"},"u-sinh":{"tier":"kernel","category":"Letters","unicode":"U+0D8B"},"uu-sinh":{"tier":"kernel","category":"Letters","unicode":"U+0D8C","decompose":["u","vocaliclsign"]},"e-sinh":{"tier":"kernel","category":"Letters","unicode":"U+0D91"},"ee-sinh":{"tier":"kernel","category":"Letters","unicode":"U+0D92","decompose":["e","virama"]},"ai-sinh":{"tier":"kernel","category":"Letters","unicode":"U+0D93","decompose":["esign","e"]},"o-sinh":{"tier":"kernel","category":"Letters","unicode":"U+0D94"},"oo-sinh":{"tier":"kernel","category":"Letters","unicode":"U+0D95"},"au-sinh":{"tier":"kernel","category":"Letters","unicode":"U+0D96","decompose":["o","vocaliclsign"]},"ka-sinh":{"tier":"kernel","category":"Letters","unicode":"U+0D9A"},"kha-sinh":{"tier":"kernel","category":"Letters","unicode":"U+0D9B"},"ga-sinh":{"tier":"kernel","category":"Letters","unicode":"U+0D9C"},"gha-sinh":{"tier":"kernel","category":"Letters","unicode":"U+0D9D"},"nga-sinh":{"tier":"kernel","category":"Letters","unicode":"U+0D9E"},"nnga-sinh":{"tier":"kernel","category":"Letters","unicode":"U+0D9F"},"ca-sinh":{"tier":"kernel","category":"Letters","unicode":"U+0DA0"},"cha-sinh":{"tier":"kernel","category":"Letters","unicode":"U+0DA1"},"ja-sinh":{"tier":"kernel","category":"Letters","unicode":"U+0DA2"},"jha-sinh":{"tier":"kernel","category":"Letters","unicode":"U+0DA3"},"nya-sinh":{"tier":"kernel","category":"Letters","unicode":"U+0DA4"},"tta-sinh":{"tier":"kernel","category":"Letters","unicode":"U+0DA7"},"ttha-sinh":{"tier":"kernel","category":"Letters","unicode":"U+0DA8"},"dda-sinh":{"tier":"kernel","category":"Letters","unicode":"U+0DA9"},"ddha-sinh":{"tier":"kernel","category":"Letters","unicode":"U+0DAA"},"nna-sinh":{"tier":"kernel","category":"Letters","unicode":"U+0DAB"},"nndda-sinh":{"tier":"kernel","category":"Letters","unicode":"U+0DAC"},"ta-sinh":{"tier":"kernel","category":"Letters","unicode":"U+0DAD"},"tha-sinh":{"tier":"kernel","category":"Letters","unicode":"U+0DAE"},"da-sinh":{"tier":"kernel","category":"Letters","unicode":"U+0DAF"},"dha-sinh":{"tier":"kernel","category":"Letters","unicode":"U+0DB0"},"na-sinh":{"tier":"kernel","category":"Letters","unicode":"U+0DB1"},"nda-sinh":{"tier":"kernel","category":"Letters","unicode":"U+0DB3"},"pa-sinh":{"tier":"kernel","category":"Letters","unicode":"U+0DB4"},"pha-sinh":{"tier":"kernel","category":"Letters","unicode":"U+0DB5"},"ba-sinh":{"tier":"kernel","category":"Letters","unicode":"U+0DB6"},"bha-sinh":{"tier":"kernel","category":"Letters","unicode":"U+0DB7"},"ma-sinh":{"tier":"kernel","category":"Letters","unicode":"U+0DB8"},"mba-sinh":{"tier":"kernel","category":"Letters","unicode":"U+0DB9"},"ya-sinh":{"tier":"kernel","category":"Letters","unicode":"U+0DBA"},"ra-sinh":{"tier":"kernel","category":"Letters","unicode":"U+0DBB"},"la-sinh":{"tier":"kernel","category":"Letters","unicode":"U+0DBD"},"va-sinh":{"tier":"kernel","category":"Letters","unicode":"U+0DC0"},"sha-sinh":{"tier":"kernel","category":"Letters","unicode":"U+0DC1"},"ssa-sinh":{"tier":"kernel","category":"Letters","unicode":"U+0DC2"},"sa-sinh":{"tier":"kernel","category":"Letters","unicode":"U+0DC3"},"ha-sinh":{"tier":"kernel","category":"Letters","unicode":"U+0DC4"},"lla-sinh":{"tier":"kernel","category":"Letters","unicode":"U+0DC5"},"fa-sinh":{"tier":"kernel","category":"Letters","unicode":"U+0DC6"},"aasign-sinh":{"tier":"kernel","category":"Signs","unicode":"U+0DCF"},"aesign-sinh":{"tier":"kernel","category":"Signs","unicode":"U+0DD0"},"aaesign-sinh":{"tier":"kernel","category":"Signs","unicode":"U+0DD1"},"isign-sinh":{"tier":"kernel","category":"Signs","unicode":"U+0DD2"},"iisign-sinh":{"tier":"kernel","category":"Signs","unicode":"U+0DD3"},"usign-sinh":{"tier":"kernel","category":"Signs","unicode":"U+0DD4"},"uusign-sinh":{"tier":"kernel","category":"Signs","unicode":"U+0DD6"},"vocalicrsign-sinh":{"tier":"kernel","category":"Signs","unicode":"U+0DD8"},"vocalicllsign-sinh":{"tier":"kernel","category":"Signs","unicode":"U+0DF3"},"vocaliclsign-sinh":{"tier":"kernel","category":"Signs","unicode":"U+0DDF"},"vocalicrrsign-sinh":{"tier":"kernel","category":"Signs","unicode":"U+0DF2"},"esign-sinh":{"tier":"kernel","category":"Signs","unicode":"U+0DD9"},"eesign-sinh":{"tier":"kernel","category":"Signs","unicode":"U+0DDA","decompose":["esign","esign"]},"osign-sinh":{"tier":"kernel","category":"Signs","unicode":"U+0DDC"},"oosign-sinh":{"tier":"kernel","category":"Signs","unicode":"U+0DDD"},"aisign-sinh":{"tier":"kernel","category":"Signs","unicode":"U+0DDB"},"ausign-sinh":{"tier":"kernel","category":"Signs","unicode":"U+0DDE","decompose":["esign","vocaliclsign"]},"virama-sinh":{"tier":"kernel","category":"Signs","unicode":"U+0DCA"},"anusvaraya-sinh":{"tier":"kernel","category":"Signs","unicode":"U+0D82"},"visargaya-sinh":{"tier":"kernel","category":"Signs","unicode":"U+0D83"},"rasign-sinh":{"tier":"kernel","category":"Signs"},"repha-sinh":{"tier":"kernel","category":"Signs"},"yasign-sinh":{"tier":"kernel","category":"Signs"},"usign.rasign-sinh":{"tier":"kernel","category":"Signs"},"uusign.rasign-sinh":{"tier":"kernel","category":"Signs"},"kh-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"ng-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"c-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"ch-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"j-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"jh-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"tt-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"tth-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"dd-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"ddh-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"nndd-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"th-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"dh-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"ph-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"b-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"m-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"mb-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"r-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"v-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"khI-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"ngI-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"cI-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"chI-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"jI-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"jhI-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"ttI-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"tthI-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"ddI-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"ddhI-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"nnddI-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"thI-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"dhI-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"phI-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"bI-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"mI-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"mbI-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"rI-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"vI-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"khIi-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"ngIi-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"cIi-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"chIi-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"jIi-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"jhIi-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"ttIi-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"tthIi-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"ddIi-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"ddhIi-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"nnddIi-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"thIi-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"dhIi-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"phIi-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"bIi-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"mIi-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"mbIi-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"rIi-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"vIi-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"kU-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"gU-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"ngU-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"nyU-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"tU-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"dU-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"ndU-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"bhU-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"rU-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"lU-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"shU-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"llU-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"kUu-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"gUu-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"ngUu-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"nyUu-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"tUu-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"dUu-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"ndUu-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"bhUu-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"rUu-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"lUu-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"shUu-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"llUu-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"rAe-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"rAae-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"nyRa-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"dRa-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"nDRa-sinh":{"tier":"kernel","category":"Orthographical conjuncts"},"kunddaliya":{"tier":"core","category":"Punctuation","unicode":"U+0DF4"},"vocalicr-sinh":{"tier":"core","category":"Letters","unicode":"U+0D8D"},"vocalicrr-sinh":{"tier":"core","category":"Letters","unicode":"U+0D8E","decompose":["vocalicrr","vocalicrsign"]},"vocalicl-sinh":{"tier":"core","category":"Letters","unicode":"U+0D8F"},"vocalicll-sinh":{"tier":"core","category":"Letters","unicode":"U+0D90","decompose":["vocalicl","vocaliclsign"]},"jnya-sinh":{"tier":"core","category":"Letters","unicode":"U+0DA5"},"nyja-sinh":{"tier":"core","category":"Letters","unicode":"U+0DA6"},"kSsa-sinh":{"tier":"core","category":"Ligated consonant conjuncts"},"jny-sinh":{"tier":"core","category":"Orthographical conjuncts"},"jnyI-sinh":{"tier":"core","category":"Orthographical conjuncts"},"jnyIi-sinh":{"tier":"core","category":"Orthographical conjuncts"},"jnyU-sinh":{"tier":"core","category":"Orthographical conjuncts"},"jnyUu-sinh":{"tier":"core","category":"Orthographical conjuncts"},"nyj-sinh":{"tier":"core","category":"Orthographical conjuncts"},"nyjI-sinh":{"tier":"core","category":"Orthographical conjuncts"},"nyjIi-sinh":{"tier":"core","category":"Orthographical conjuncts"},"nyjU-sinh":{"tier":"core","category":"Orthographical conjuncts"},"nyjUu-sinh":{"tier":"core","category":"Orthographical conjuncts"},"kVa-sinh":{"tier":"plus","category":"Ligated consonant conjuncts"},"tTha-sinh":{"tier":"plus","category":"Ligated consonant conjuncts"},"tVa-sinh":{"tier":"plus","category":"Ligated consonant conjuncts"},"nTha-sinh":{"tier":"plus","category":"Ligated consonant conjuncts"},"nDa-sinh":{"tier":"plus","category":"Ligated consonant conjuncts"},"nDha-sinh":{"tier":"plus","category":"Ligated consonant conjuncts"},"kV-sinh":{"tier":"plus","category":"Orthographical conjuncts"},"kVI-sinh":{"tier":"plus","category":"Orthographical conjuncts"},"kVIi-sinh":{"tier":"plus","category":"Orthographical conjuncts"},"tThI-sinh":{"tier":"plus","category":"Orthographical conjuncts"},"tThIi-sinh":{"tier":"plus","category":"Orthographical conjuncts"},"tVI-sinh":{"tier":"plus","category":"Orthographical conjuncts"},"tVIi-sinh":{"tier":"plus","category":"Orthographical conjuncts"},"nThI-sinh":{"tier":"plus","category":"Orthographical conjuncts"},"nThIi-sinh":{"tier":"plus","category":"Orthographical conjuncts"},"nDI-sinh":{"tier":"plus","category":"Orthographical conjuncts"},"nDIi-sinh":{"tier":"plus","category":"Orthographical conjuncts"},"nDhI-sinh":{"tier":"plus","category":"Orthographical conjuncts"},"nDhIi-sinh":{"tier":"plus","category":"Orthographical conjuncts"},"candrabindu-sinh":{"tier":"pro","category":"Signs"},"lithzero-sinh":{"tier":"pro","category":"Sinhala numerals"},"lithone-sinh":{"tier":"pro","category":"Sinhala numerals"},"lithtwo-sinh":{"tier":"pro","category":"Sinhala numerals"},"liththree-sinh":{"tier":"pro","category":"Sinhala numerals"},"lithfour-sinh":{"tier":"pro","category":"Sinhala numerals"},"lithfive-sinh":{"tier":"pro","category":"Sinhala numerals"},"lithsix-sinh":{"tier":"pro","category":"Sinhala numerals"},"lithseven-sinh":{"tier":"pro","category":"Sinhala numerals"},"litheight-sinh":{"tier":"pro","category":"Sinhala numerals"},"lithnine-sinh":{"tier":"pro","category":"Sinhala numerals"},"archaicone-sinh":{"tier":"pro","category":"Sinhala numerals"},"archaictwo-sinh":{"tier":"pro","category":"Sinhala numerals"},"archaicthree-sinh":{"tier":"pro","category":"Sinhala numerals"},"archaicfour-sinh":{"tier":"pro","category":"Sinhala numerals"},"archaicfive-sinh":{"tier":"pro","category":"Sinhala numerals"},"archaicsix-sinh":{"tier":"pro","category":"Sinhala numerals"},"archaicseven-sinh":{"tier":"pro","category":"Sinhala numerals"},"archaiceight-sinh":{"tier":"pro","category":"Sinhala numerals"},"archaicnine-sinh":{"tier":"pro","category":"Sinhala numerals"},"archaicten-sinh":{"tier":"pro","category":"Sinhala numerals"},"archaictwenty-sinh":{"tier":"pro","category":"Sinhala numerals"},"archaicthirty-sinh":{"tier":"pro","category":"Sinhala numerals"},"archaicforty-sinh":{"tier":"pro","category":"Sinhala numerals"},"archaicfifty-sinh":{"tier":"pro","category":"Sinhala numerals"},"archaicsixty-sinh":{"tier":"pro","category":"Sinhala numerals"},"archaicseventy-sinh":{"tier":"pro","category":"Sinhala numerals"},"archaiceighty-sinh":{"tier":"pro","category":"Sinhala numerals"},"archaicninety-sinh":{"tier":"pro","category":"Sinhala numerals"},"archaiconehundred-sinh":{"tier":"pro","category":"Sinhala numerals"},"archaiconethousand-sinh":{"tier":"pro","category":"Sinhala numerals"},"ngDha-sinh":{"tier":"pro","category":"Ligated consonant conjuncts"},"ttTtha-sinh":{"tier":"pro","category":"Ligated consonant conjuncts"},"ddDha-sinh":{"tier":"pro","category":"Ligated consonant conjuncts"},"dVa-sinh":{"tier":"pro","category":"Ligated consonant conjuncts"},"nVa-sinh":{"tier":"pro","category":"Ligated consonant conjuncts"},"nyCa-sinh":{"tier":"pro","category":"Ligated consonant conjuncts"},"nyCha-sinh":{"tier":"pro","category":"Ligated consonant conjuncts"},"nyJa-sinh":{"tier":"pro","category":"Ligated consonant conjuncts"},"nnDda-sinh":{"tier":"pro","category":"Ligated consonant conjuncts"},"anusvarayaSha-sinh":{"tier":"pro","category":"Ligated consonant conjuncts"},"daa._c-sinh":{"tier":"pro","category":"Stylistic alternates"},"daa_virama._c-sinh":{"tier":"pro","category":"Stylistic alternates"},"dae._c-sinh":{"tier":"pro","category":"Stylistic alternates"},"daae._c-sinh":{"tier":"pro","category":"Stylistic alternates"},"dvocalicr._c-sinh":{"tier":"pro","category":"Stylistic alternates"},"dvocalicrr._c-sinh":{"tier":"pro","category":"Stylistic alternates"},"dya._c-sinh":{"tier":"pro","category":"Stylistic alternates"},"dy._c-sinh":{"tier":"pro","category":"Stylistic alternates"},"dyaa._c-sinh":{"tier":"pro","category":"Stylistic alternates"},"dyaa_virama._c-sinh":{"tier":"pro","category":"Stylistic alternates"},"dyU._c-sinh":{"tier":"pro","category":"Stylistic alternates"},"dyUu._c-sinh":{"tier":"pro","category":"Stylistic alternates"},"nDaa._c-sinh":{"tier":"pro","category":"Stylistic alternates"},"nDaa_virama._c-sinh":{"tier":"pro","category":"Stylistic alternates"},"nDae._c-sinh":{"tier":"pro","category":"Stylistic alternates"},"nDaae._c-sinh":{"tier":"pro","category":"Stylistic alternates"},"nDvocalicr._c-sinh":{"tier":"pro","category":"Stylistic alternates"},"nDvocalicrr._c-sinh":{"tier":"pro","category":"Stylistic alternates"},"nyaa._c-sinh":{"tier":"pro","category":"Stylistic alternates"},"nyaa_virama._c-sinh":{"tier":"pro","category":"Stylistic alternates"},"nyae._c-sinh":{"tier":"pro","category":"Stylistic alternates"},"nyaae._c-sinh":{"tier":"pro","category":"Stylistic alternates"},"nyJaa._c-sinh":{"tier":"pro","category":"Stylistic alternates"},"nyJaa_virama._c-sinh":{"tier":"pro","category":"Stylistic alternates"},"nyJae._c-sinh":{"tier":"pro","category":"Stylistic alternates"},"nyJaae._c-sinh":{"tier":"pro","category":"Stylistic alternates"},"dRaa._c-sinh":{"tier":"pro","category":"Stylistic alternates"},"nDRaa._c-sinh":{"tier":"pro","category":"Stylistic alternates"},"fPa-sinh":{"tier":"pro","category":"ss02 Fa"},"fPI-sinh":{"tier":"pro","category":"ss02 Fa"},"fPIi-sinh":{"tier":"pro","category":"ss02 Fa"},"esign._ui-sinh":{"tier":"pro","category":"ss03 Historical forms"}};
  var CANONICAL_LIST = Object.keys(GLYPHSET);
  var CANONICAL = new Set(CANONICAL_LIST);

  var api = {
    unicodeToName: unicodeToName,
    nameToUnicode: nameToUnicode,
    registerCorpus: registerCorpus,
    toCps: toCps,
    hex: hex,
    CANONICAL: CANONICAL,
    CANONICAL_LIST: CANONICAL_LIST,
    GLYPHSET: GLYPHSET
  };

  root.LankaGlyphset = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof globalThis !== "undefined" ? globalThis : this);

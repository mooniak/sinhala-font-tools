/*
 * app.js — Sinhala test-text generator (adhesiontext-style).
 *
 * Pick the graphemes a font has so far; get text that uses only those
 * graphemes. Template sentences, running text, real sentences, targeted
 * sentences and invented words come from the TextGen engine (textgen.js; extras.js adds numerals, punctuation, dates and times; data
 * from test-texts/corpus-build). Word list, Lines of words and the Unlock / Coverage
 * / Corpus panels work on the corpus's word list. Depends on graphemes.js
 * (SinhalaGraphemes) and textgen.js (TextGen).
 */
(function () {
  "use strict";

  var G = window.SinhalaGraphemes;
  var TG = window.TextGen;
  var EX = window.Extras;
  var DATA = "data/";
  var STAGES = "../../sinhala-design-stages/stages.json";
  var STORE_KEY = "test-generator:v2";
  var DEFAULT_SET = "සට සසඩඪ ටසඩි ඪිටඩසට ඩඪඩි පට පස ටුසු ඩුසු පුසු වට එය පය සුව";

  // format -> label, count label, default count; engine formats come from TextGen
  var FORMATS = {
    templates: { label: "Template sentences", unit: "Sentences", count: 8, engine: true },
    chain:     { label: "Running text", unit: "Words", count: 80, engine: true },
    sentences: { label: "Real sentences", unit: "Sentences", count: 10, engine: true, real: true },
    targeted:  { label: "Targeted sentences", unit: "Sentences", count: 10, engine: true, real: true },
    pseudo:    { label: "Invented words", unit: "Words", count: 40, engine: true },
    lines:     { label: "Lines of words", unit: "Words", count: 80 },
    list:      { label: "Word list", unit: "Words (0 = all)", count: 0 }
  };

  var $ = function (id) { return document.getElementById(id); };
  var el = {};
  [
    "corpusInfo", "corpusInput", "corpusReset", "fontInput", "fontName", "size", "sizeOut", "leading",
    "preset", "presetInfo", "setInput", "unknown", "fromParts", "partsHint", "chips", "mustInput", "mustMode",
    "format", "count", "countLabel", "layout", "perLine", "sort", "minLen", "maxLen", "coverage", "coverageOut",
    "inventMode", "inventPct", "inventOut", "cover", "coverLabel", "markInv", "showNames", "regen", "seedOut",
    "exNumber", "exDate", "exTime", "exPunct", "exScript", "exPlace", "exRate", "exRateOut",
    "srcNews", "srcOther", "srcHeads", "srcNames", "srcDict", "srcLatin", "srcZwnj",
    "stats", "copyBtn", "downloadBtn", "output", "unlockList", "coverageList",
    "corpusFilter", "corpusCount", "corpusList", "analyseInput", "analyseUse", "analyseNames",
    "analyseCount", "analyseList", "toast"
  ].forEach(function (id) { el[id] = $(id); });

  Object.keys(FORMATS).forEach(function (k) {
    var o = document.createElement("option");
    o.value = k;
    o.textContent = FORMATS[k].label;
    el.format.appendChild(o);
  });

  // ---- word list (Word list, Lines, Unlock, Coverage, Corpus panels) ---

  // distinct: [{ g, parts, name, words }]; words: [string]; segs: [[gid]]
  var corpus = { label: "", words: [], segs: [], distinct: [], gidOf: new Map() };
  var userCorpus = false;

  function tokenize(text) {
    return text.replace(/^﻿/, "").split(/[^඀-෿‌‍]+/).filter(function (w) {
      return /[අ-ෆ]/.test(w);
    });
  }

  function buildCorpus(texts, label) {
    var seen = new Set(), words = [];
    texts.forEach(function (t) {
      tokenize(t).forEach(function (w) {
        w = w.normalize("NFC").replace(/^[‌‍]+|[‌‍]+$/g, "");
        if (w && !seen.has(w)) { seen.add(w); words.push(w); }
      });
    });
    var distinct = [], gidOf = new Map(), segs = [];
    words.forEach(function (w) {
      var ids = G.segment(w).map(function (s) {
        var id = gidOf.get(s.g);
        if (id === undefined) {
          id = distinct.length;
          gidOf.set(s.g, id);
          distinct.push({ g: s.g, parts: s.parts, name: G.nameOf(s.g), words: 0 });
        }
        return id;
      });
      new Set(ids).forEach(function (id) { distinct[id].words++; });
      segs.push(ids);
    });
    corpus = { label: label, words: words, segs: segs, distinct: distinct, gidOf: gidOf };
    el.corpusInfo.textContent = label + " · " + words.length.toLocaleString() + " words · " +
      distinct.length.toLocaleString() + " graphemes";
    update();
  }

  function bundleWords() {
    userCorpus = false;
    el.corpusReset.hidden = true;
    if (!engine) return;
    // words seen at least 3 times in news text, or listed by a dictionary / name list; no explicit ZWNJ
    var words = engine.words.filter(function (w) {
      return (w.run >= 3 || w.mask) && w.w.indexOf("‌") === -1;
    }).map(function (w) { return w.w; });
    buildCorpus([words.join("\n")], "data bundle");
  }

  function readFiles(files) {
    return Promise.all(Array.prototype.map.call(files, function (f) { return f.text(); }));
  }

  function useOwnWords(texts, names) {
    userCorpus = true;
    buildCorpus(texts, names);
    el.corpusReset.hidden = false;
  }

  // ---- text engine ----------------------------------------------------

  var engine = null;
  var engineError = "";

  function reader(rel) {
    return fetch(DATA + rel).then(function (r) {
      if (!r.ok) throw new Error(rel + ": HTTP " + r.status);
      return r.text();
    });
  }

  function loadEngine() {
    el.corpusInfo.textContent = "loading data bundle…";
    TG.load(reader).then(function (e) {
      engine = e;
      engineError = "";
      if (!userCorpus) bundleWords(); else update();
    }).catch(function (err) {
      engineError = "Could not load data/ (" + err.message + "). Serve the repo over HTTP, and build the bundle with: node test-texts/corpus-build/build.js";
      el.corpusInfo.textContent = "no data bundle";
      update();
    });
  }

  var sess = null, sessKey = "";
  function getSession(s, setList) {
    var key = [setList.join(" "), s.fromParts, s.srcNames, s.srcDict, s.srcZwnj].join("|");
    if (key !== sessKey) {
      sess = engine.session(setList, {
        fromParts: s.fromParts,
        zwnj: s.srcZwnj,
        sources: { running: true, names: s.srcNames, dict: s.srcDict }
      });
      sess.ready = null;
      sessKey = key;
    }
    return sess;
  }

  // ---- presets: what a font has reached by a stage or a level -----------

  var presets = {};
  function loadPresets() {
    fetch(STAGES).then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); }).then(function (data) {
      var built = window.Presets.build(data);
      var sg = document.createElement("optgroup"), lg = document.createElement("optgroup");
      sg.label = "Design stage (cumulative)";
      lg.label = "Glyphset level";
      function add(group, key, label, items) {
        presets[key] = items;
        var o = document.createElement("option");
        o.value = key;
        o.textContent = label;
        group.appendChild(o);
      }
      built.stages.forEach(function (st) { add(sg, "stage" + st.n, "Stage " + st.n + " — " + st.name, st.items); });
      built.levels.forEach(function (lv) { add(lg, "level" + lv.n, lv.label + " (level " + lv.n + ")", lv.items); });
      el.preset.appendChild(sg);
      el.preset.appendChild(lg);
    }).catch(function () { el.preset.hidden = true; });
  }

  // ---- state ----------------------------------------------------------

  var seed = (Math.random() * 0xffffffff) >>> 0;
  var result = null;     // last word-list match state
  var counts = {};       // count per format
  var runId = 0;

  Object.keys(FORMATS).forEach(function (k) { counts[k] = FORMATS[k].count; });

  function settings() {
    var f = el.format.value;
    counts[f] = Math.max(0, parseInt(el.count.value, 10) || 0);
    return {
      set: el.setInput.value,
      fromParts: el.fromParts.checked,
      must: el.mustInput.value,
      mustMode: el.mustMode.value,
      format: f,
      counts: counts,
      count: counts[f],
      layout: el.layout.value,
      perLine: Math.max(1, parseInt(el.perLine.value, 10) || 1),
      sort: el.sort.value,
      minLen: Math.max(1, parseInt(el.minLen.value, 10) || 1),
      maxLen: Math.max(1, parseInt(el.maxLen.value, 10) || 99),
      coverage: (+el.coverage.value) / 100,
      inventMode: el.inventMode.value,
      inventPct: (+el.inventPct.value) / 100,
      cover: el.cover.checked,
      markInv: el.markInv.checked,
      showNames: el.showNames.checked,
      srcNews: el.srcNews.checked, srcOther: el.srcOther.checked, srcHeads: el.srcHeads.checked,
      srcNames: el.srcNames.checked, srcDict: el.srcDict.checked,
      srcLatin: el.srcLatin.checked, srcZwnj: el.srcZwnj.checked,
      exNumber: el.exNumber.checked, exDate: el.exDate.checked, exTime: el.exTime.checked, exPunct: el.exPunct.checked,
      exScript: el.exScript.value, exPlace: el.exPlace.value, exRate: (+el.exRate.value) / 100,
      size: el.size.value,
      leading: el.leading.value
    };
  }

  function save() {
    try { localStorage.setItem(STORE_KEY, JSON.stringify(settings())); } catch (e) { /* storage blocked */ }
  }

  function restore() {
    var s = null;
    try { s = JSON.parse(localStorage.getItem(STORE_KEY)); } catch (e) { s = null; }
    s = s || {};
    var bool = function (id, v, d) { el[id].checked = v == null ? d : !!v; };
    el.setInput.value = s.set != null ? s.set : DEFAULT_SET;
    el.fromParts.checked = !!s.fromParts;
    el.mustInput.value = s.must || "";
    if (s.mustMode) el.mustMode.value = s.mustMode;
    if (s.counts) Object.keys(s.counts).forEach(function (k) { if (k in counts) counts[k] = s.counts[k]; });
    el.format.value = FORMATS[s.format] ? s.format : "templates";
    el.count.value = counts[el.format.value];
    if (s.layout) el.layout.value = s.layout;
    if (s.perLine) el.perLine.value = s.perLine;
    if (s.sort) el.sort.value = s.sort;
    if (s.minLen) el.minLen.value = s.minLen;
    if (s.maxLen) el.maxLen.value = s.maxLen;
    if (s.coverage != null) el.coverage.value = Math.round(s.coverage * 100);
    if (s.inventMode) el.inventMode.value = s.inventMode;
    if (s.inventPct != null) el.inventPct.value = Math.round(s.inventPct * 100);
    bool("cover", s.cover, true);
    bool("markInv", s.markInv, true);
    bool("showNames", s.showNames, false);
    bool("srcNews", s.srcNews, true); bool("srcOther", s.srcOther, true); bool("srcHeads", s.srcHeads, true);
    bool("srcNames", s.srcNames, true); bool("srcDict", s.srcDict, true);
    bool("srcLatin", s.srcLatin, false); bool("srcZwnj", s.srcZwnj, false);
    bool("exNumber", s.exNumber, false); bool("exDate", s.exDate, false);
    bool("exTime", s.exTime, false); bool("exPunct", s.exPunct, false);
    if (s.exScript) el.exScript.value = s.exScript;
    if (s.exPlace) el.exPlace.value = s.exPlace;
    if (s.exRate != null) el.exRate.value = Math.round(s.exRate * 100);
    if (s.size) el.size.value = s.size;
    if (s.leading) el.leading.value = s.leading;
  }

  // ---- word-list matching ---------------------------------------------

  function contains(d, t) { return d.g === t || d.parts.indexOf(t) !== -1; }

  function compute(s) {
    var parsed = G.parseList(s.set);
    var setList = parsed.graphemes;
    var set = new Set(setList);
    var must = G.parseList(s.must).graphemes;
    var D = corpus.distinct;

    var avail = D.map(function (d) { return G.availability(d, set, s.fromParts); });
    var mustHit = must.map(function (t) { return D.map(function (d) { return contains(d, t); }); });

    var matches = [], unlock = new Map();
    corpus.segs.forEach(function (ids, wi) {
      var missing = -1, nMissing = 0;
      for (var k = 0; k < ids.length; k++) {
        if (!avail[ids[k]] && ids[k] !== missing) {
          nMissing++;
          missing = ids[k];
          if (nMissing > 1) return;
        }
      }
      if (must.length) {
        var hits = mustHit.map(function (row) { return ids.some(function (id) { return row[id]; }); });
        var ok = s.mustMode === "all" ? hits.every(Boolean) : hits.some(Boolean);
        if (!ok) return;
      }
      if (nMissing === 0) {
        if (ids.length >= s.minLen && ids.length <= s.maxLen) matches.push(wi);
      } else if (ids.length >= s.minLen && ids.length <= s.maxLen) {
        unlock.set(missing, (unlock.get(missing) || 0) + 1);
      }
    });

    // Which listed graphemes each matching word exercises.
    var uses = new Map();   // set grapheme -> [word index]
    setList.forEach(function (g) { uses.set(g, []); });
    matches.forEach(function (wi) {
      var hit = new Set();
      corpus.segs[wi].forEach(function (id) {
        var d = D[id];
        if (set.has(d.g)) hit.add(d.g);
        if (avail[id] === "parts") d.parts.forEach(function (p) { if (set.has(p)) hit.add(p); });
      });
      hit.forEach(function (g) { uses.get(g).push(wi); });
    });

    return { set: set, setList: setList, unknown: parsed.unknown, avail: avail, matches: matches, unlock: unlock, uses: uses };
  }

  // ---- word-list generation (Lines of words, Word list) ----------------

  function generate(s, r) {
    var rand = TG.rng(seed);
    var pool = r.matches;
    if (!pool.length) return [];
    var segLen = function (wi) { return corpus.segs[wi].length; };
    var word = function (wi) { return corpus.words[wi]; };

    if (s.format === "list") {
      var list = TG.shuffle(pool.slice(), rand);
      if (s.count) list = list.slice(0, s.count);
      if (s.sort === "alpha") list.sort(function (a, b) { return word(a).localeCompare(word(b), "si"); });
      if (s.sort === "length") list.sort(function (a, b) { return segLen(a) - segLen(b) || word(a).localeCompare(word(b), "si"); });
      return list;
    }

    var n = s.count || 80;
    var seq = [];
    if (s.cover) {
      var covered = new Set();
      TG.shuffle(r.setList.slice(), rand).forEach(function (g) {
        if (covered.has(g) || seq.length >= n) return;
        var cands = r.uses.get(g);
        if (!cands || !cands.length) return;
        var wi = cands[Math.floor(rand() * cands.length)];
        seq.push(wi);
        r.uses.forEach(function (ws, h) { if (ws.indexOf(wi) !== -1) covered.add(h); });
      });
    }
    var recent = Math.min(pool.length - 1, 8);
    while (seq.length < n) {
      var pick, tries = 0;
      do { pick = pool[Math.floor(rand() * pool.length)]; tries++; }
      while (tries < 20 && seq.slice(-recent).indexOf(pick) !== -1);
      seq.push(pick);
    }
    TG.shuffle(seq, rand);
    for (var i = 1; i < seq.length; i++) {   // no word twice in a row
      if (seq[i] === seq[i - 1]) {
        for (var j = i + 1; j < seq.length; j++) {
          if (seq[j] !== seq[i] && seq[j] !== seq[i - 1]) { var t = seq[i]; seq[i] = seq[j]; seq[j] = t; break; }
        }
      }
    }
    return seq;
  }

  // ---- rendering ------------------------------------------------------

  function short(name) { return name.replace(/-sinh$/, ""); }
  function namesOf(text) {
    return G.segment(text).filter(function (x) { return x.sinhala; }).map(function (x) { return short(G.nameOf(x.g)); }).join(" ");
  }
  function wordNames(wi) {
    return corpus.segs[wi].map(function (id) { return short(corpus.distinct[id].name); }).join(" ");
  }

  var last = { kind: "", seq: [], format: "", result: null, sep: " " };

  function prepareOutput(s) {
    var out = el.output;
    out.innerHTML = "";
    out.classList.toggle("list", s.format === "list" || s.format === "pseudo");
    out.style.fontSize = s.size + "px";
    out.style.lineHeight = s.leading;
    return out;
  }

  function message(text) {
    var out = el.output;
    out.innerHTML = "";
    out.classList.remove("list");
    var m = document.createElement("span");
    m.className = "empty";
    m.textContent = text;
    out.appendChild(m);
  }

  function wordNode(text, names, inv, s) {
    var span = document.createElement("span");
    span.className = "w" + (inv && s.markInv ? " inv" : "");
    span.title = (inv ? "invented · " : "") + names;
    if (s.showNames && s.format !== "list" && s.format !== "pseudo") {
      var ruby = document.createElement("ruby");
      ruby.textContent = text;
      var rt = document.createElement("rt");
      rt.textContent = names;
      ruby.appendChild(rt);
      span.appendChild(ruby);
    } else {
      span.textContent = text;
    }
    return span;
  }

  // word-list formats
  function renderOutput(s, seq) {
    last = { kind: "words", seq: seq, format: s.format, result: null, sep: " " };
    var out = prepareOutput(s);
    if (!corpus.words.length) { message("No words loaded."); return; }
    if (!seq.length) {
      message("No words match. Add graphemes (see Unlock below), relax the length limits, or turn on “also build from parts”.");
      return;
    }
    var frag = document.createDocumentFragment();
    if (s.format === "list") {
      seq.forEach(function (wi) {
        var item = document.createElement("div");
        item.className = "item";
        item.appendChild(wordNode(corpus.words[wi], wordNames(wi), false, s));
        if (s.showNames) {
          var nm = document.createElement("span");
          nm.className = "names";
          nm.textContent = wordNames(wi);
          item.appendChild(nm);
        }
        frag.appendChild(item);
      });
    } else {
      seq.forEach(function (wi, i) {
        if (i > 0) frag.appendChild(document.createTextNode(i % s.perLine === 0 ? "\n" : " "));
        frag.appendChild(wordNode(corpus.words[wi], wordNames(wi), false, s));
      });
    }
    out.appendChild(frag);
  }

  // engine formats
  function renderResult(res, s) {
    var lines = s.layout === "lines" || res.mode === "pseudo";
    last = { kind: "engine", seq: [], format: s.format, result: res, sep: lines ? "\n" : " " };
    var out = prepareOutput(s);
    var frag = document.createDocumentFragment();
    res.sentences.forEach(function (sent) {
      if (res.mode === "pseudo") {
        var item = document.createElement("div");
        item.className = "item";
        item.appendChild(wordNode(sent[0].t, namesOf(sent[0].t), sent[0].inv, s));
        if (s.showNames) {
          var nm = document.createElement("span");
          nm.className = "names";
          nm.textContent = namesOf(sent[0].t);
          item.appendChild(nm);
        }
        frag.appendChild(item);
        return;
      }
      var box = document.createElement(lines ? "div" : "span");
      box.className = "sent";
      sent.forEach(function (p) {
        box.appendChild(p.w ? wordNode(p.t, namesOf(p.t), p.inv, s) : document.createTextNode(p.t));
      });
      frag.appendChild(box);
      if (!lines) frag.appendChild(document.createTextNode(" "));
    });
    out.appendChild(frag);
  }

  function plainText() {
    var s = settings();
    if (last.kind === "engine") return TG.render(last.result, { sep: last.sep });
    if (last.format === "list") {
      return last.seq.map(function (wi) {
        return corpus.words[wi] + (s.showNames ? "\t" + wordNames(wi) : "");
      }).join("\n");
    }
    return last.seq.map(function (wi, i) {
      return (i > 0 ? (i % s.perLine === 0 ? "\n" : " ") : "") + corpus.words[wi];
    }).join("");
  }

  function cell(g, name, n, cls, onClick, title) {
    var c = document.createElement("div");
    c.className = "gcell" + (cls ? " " + cls : "");
    c.title = title || (name + "  " + G.hex(g));
    c.innerHTML = '<span class="g"></span><span class="meta"><span class="name"></span><span class="n"></span></span>';
    c.querySelector(".g").textContent = g;
    c.querySelector(".name").textContent = short(name);
    c.querySelector(".n").textContent = n;
    if (onClick) c.addEventListener("click", onClick);
    return c;
  }

  function renderChips(r) {
    el.chips.innerHTML = "";
    r.setList.forEach(function (g) {
      var n = r.uses.get(g).length;
      var c = document.createElement("span");
      c.className = "chip" + (n ? "" : " zero");
      c.title = G.nameOf(g) + "  " + G.hex(g) + "\n" + n + " matching words — click to remove";
      c.innerHTML = '<span class="g"></span><span class="nm"></span>';
      c.querySelector(".g").textContent = g;
      c.querySelector(".nm").textContent = short(G.nameOf(g)) + " " + n;
      c.addEventListener("click", function () { removeFromSet(g); });
      el.chips.appendChild(c);
    });
    el.unknown.hidden = !r.unknown.length;
    el.unknown.textContent = r.unknown.length ? "Unknown names: " + r.unknown.join(", ") : "";

    var signsOnly = r.setList.filter(function (g) { return /^[්-ෟෲෳ]$|‍/.test(g); });
    el.partsHint.hidden = el.fromParts.checked || !signsOnly.length;
    el.partsHint.textContent = signsOnly.length
      ? "The set lists " + signsOnly.length + " sign(s) on their own (" + signsOnly.map(function (g) { return short(G.nameOf(g)); }).join(", ") +
        "). They only combine with bases when “also build from parts” is on."
      : "";
  }

  function renderUnlock(r) {
    el.unlockList.innerHTML = "";
    var rows = Array.from(r.unlock.entries()).sort(function (a, b) { return b[1] - a[1]; }).slice(0, 60);
    if (!rows.length) { el.unlockList.innerHTML = '<span class="muted">Nothing is one grapheme away.</span>'; return; }
    rows.forEach(function (row) {
      var d = corpus.distinct[row[0]];
      el.unlockList.appendChild(cell(d.g, d.name, "+" + row[1].toLocaleString() + " words", "", function () { addToSet(d.g); }));
    });
  }

  function renderCoverage(r) {
    el.coverageList.innerHTML = "";
    r.setList.slice().sort(function (a, b) { return r.uses.get(a).length - r.uses.get(b).length; }).forEach(function (g) {
      var n = r.uses.get(g).length;
      el.coverageList.appendChild(cell(g, G.nameOf(g), n.toLocaleString() + " words", n ? "exact" : "zero", function () {
        el.mustInput.value = short(G.nameOf(g));
        update();
      }, "Click to use " + G.nameOf(g) + " as the must-include / target"));
    });
  }

  function renderCorpus(r) {
    var q = el.corpusFilter.value.trim();
    var D = corpus.distinct;
    var ids = D.map(function (_, i) { return i; }).filter(function (i) {
      return !q || D[i].name.indexOf(q) !== -1 || D[i].g.indexOf(q.normalize("NFC")) !== -1;
    }).sort(function (a, b) { return D[b].words - D[a].words; });
    el.corpusCount.textContent = ids.length.toLocaleString() + " graphemes" + (ids.length > 400 ? " (top 400 shown)" : "");
    el.corpusList.innerHTML = "";
    ids.slice(0, 400).forEach(function (i) {
      var d = D[i], a = r.avail[i];
      el.corpusList.appendChild(cell(d.g, d.name, d.words.toLocaleString() + " words", a, function () {
        if (r.set.has(d.g)) removeFromSet(d.g); else addToSet(d.g);
      }));
    });
  }

  function renderAnalyse() {
    var counts = new Map();
    G.segment(el.analyseInput.value).forEach(function (s) {
      if (s.sinhala) counts.set(s.g, (counts.get(s.g) || 0) + 1);
    });
    el.analyseList.innerHTML = "";
    counts.forEach(function (n, g) {
      el.analyseList.appendChild(cell(g, G.nameOf(g), "× " + n, "", function () { addToSet(g); }));
    });
    el.analyseCount.textContent = counts.size ? counts.size + " distinct graphemes" : "";
    return Array.from(counts.keys());
  }

  // ---- set editing ----------------------------------------------------

  function addToSet(g) {
    var v = el.setInput.value.replace(/\s+$/, "");
    el.setInput.value = (v ? v + " " : "") + G.nameOf(g);
    update();
    toast("added " + G.nameOf(g));
  }
  function removeFromSet(g) {
    var list = G.parseList(el.setInput.value).graphemes.filter(function (x) { return x !== g; });
    el.setInput.value = list.map(G.nameOf).join(" ");
    update();
    toast("removed " + G.nameOf(g));
  }

  // ---- engine output --------------------------------------------------

  /** Targets from the Must include field: class keywords, bare signs, graphemes. */
  function parseTarget(text) {
    var spec = { graphemes: [], signs: [], classes: [] }, any = false;
    text.split(/[\s,;]+/).filter(Boolean).forEach(function (tok) {
      if (/^(rakar|yansa|repha|conjunct)$/.test(tok)) { spec.classes.push(tok); any = true; return; }
      G.parseList(tok).graphemes.forEach(function (g) {
        any = true;
        if (/^[්-ෟෲෳ]$/.test(g)) spec.signs.push(g); else spec.graphemes.push(g);
      });
    });
    return any ? spec : null;
  }

  function sentenceFilter(s) {
    return {
      exclude: (s.srcLatin ? "" : "l") + (s.srcZwnj ? "" : "n") + (s.srcHeads ? "" : "h"),
      sources: (s.srcNews ? "12" : "") + (s.srcOther ? "peg" : "")
    };
  }

  function engineStats(res, s, sess) {
    var st = res.stats, bits = [];
    if (s.format === "sentences" || s.format === "targeted") {
      bits.push(res.sentences.length + " sentence" + (res.sentences.length === 1 ? "" : "s"));
      if (s.format === "targeted" && res.matching != null) bits.push(res.matching.toLocaleString() + " contain the target");
      else if (res.available != null) bits.push(res.available.toLocaleString() + " available for this set");
    } else {
      bits.push(st.words.toLocaleString() + " words");
      bits.push(st.invented + " invented (" + Math.round(st.inventedPct * 100) + "%)");
    }
    var real = s.format === "sentences" || s.format === "targeted";   // a few sentences cannot show every grapheme
    bits.push(real ? st.shown + " distinct graphemes shown" : st.shown + " of " + st.graphemes + " graphemes shown");
    el.stats.textContent = bits.join(" · ");
    el.stats.title = !real && st.missing.length ? "Not shown: " + st.missing.join(" ") : "";
    if (!real && st.missing.length) el.stats.textContent += " (" + st.missing.length + " missing)";
  }

  function runEngine(s, r, id) {
    var f = FORMATS[s.format];
    if (engineError) { message(engineError); el.stats.textContent = ""; return; }
    if (!engine) { message("Loading the data bundle…"); return; }
    if (!r.setList.length) { message("Add graphemes to the set."); el.stats.textContent = ""; return; }
    var sess = getSession(s, r.setList);
    var inv = s.inventMode === "share" ? { mode: "ratio", ratio: s.inventPct } : { mode: "auto", max: s.inventPct };
    var filt = sentenceFilter(s);
    var common = { seed: seed, coverage: s.coverage, invent: inv, cover: s.cover, exclude: filt.exclude, sources: filt.sources };
    var done = function (res) {
      if (id !== runId) return;
      if (!res.sentences.length) {
        el.stats.textContent = "";
        if (s.format === "targeted") message("No sentence has that target. Check the Must include field, or add graphemes.");
        else if (f.real) message("No complete real sentence uses only these graphemes (" + sess.pool.length + " usable of the shipped set). Real sentences need roughly 90 common letters, signs and combinations — Template sentences work for smaller sets.");
        else message("Nothing could be built from this set.");
        return;
      }
      res = EX.apply(res, {
        kinds: [s.exNumber && "number", s.exDate && "date", s.exTime && "time", s.exPunct && "punct"].filter(Boolean),
        script: s.exScript, place: s.exPlace, rate: s.exRate, seed: seed
      });
      renderResult(res, s);
      engineStats(res, s, sess);
    };
    var fail = function (e) { if (id === runId) { message("Error: " + e.message); } };

    if (f.real) {
      if (s.format === "targeted" && !parseTarget(s.must)) {
        message("Targeted sentences need a target: put graphemes, a sign (usign) or rakar / yansa / repha / conjunct in Must include.");
        el.stats.textContent = "";
        return;
      }
      if (!sess.ready) {
        message("Loading real sentences…");
        sess.ready = sess.loadSentences(function (n, of) {
          if (id === runId) el.stats.textContent = "loading real sentences " + n + " / " + of + " shards";
        });
      }
      sess.ready.then(function () {
        if (id !== runId) return;
        if (s.format === "targeted") done(sess.targeted(parseTarget(s.must), Object.assign({ count: s.count }, common)));
        else done(sess.sentences(Object.assign({ count: s.count }, common)));
      }).catch(fail);
    } else if (s.format === "templates") {
      sess.templates(Object.assign({ count: s.count }, common)).then(done).catch(fail);
    } else if (s.format === "chain") {
      done(sess.chain(Object.assign({ words: s.count }, common)));
    } else {
      done(sess.pseudo({ seed: seed, count: s.count, coverage: s.coverage, cover: s.cover, contains: G.parseList(s.must).graphemes }));
    }
  }

  // ---- main loop ------------------------------------------------------

  function update() {
    var s = settings();
    save();
    var f = FORMATS[s.format];
    el.sizeOut.textContent = s.size;
    el.seedOut.textContent = seed.toString(16);
    el.coverageOut.textContent = el.coverage.value;
    el.inventOut.textContent = el.inventPct.value;
    el.exRateOut.textContent = el.exRate.value;
    el.countLabel.textContent = f.unit;
    el.coverLabel.textContent = f.engine ? "show every grapheme at least once" : "start with a word for every grapheme";
    document.querySelectorAll("[data-for]").forEach(function (n) {
      n.hidden = n.dataset.for.split(" ").indexOf(s.format) === -1;
    });

    result = compute(s);
    var id = ++runId;
    if (f.engine) {
      runEngine(s, result, id);
    } else {
      renderOutput(s, generate(s, result));
      var inCorpus = result.setList.filter(function (g) { return corpus.gidOf.has(g); }).length;
      el.stats.title = "";
      el.stats.textContent = result.matches.length.toLocaleString() + " of " + corpus.words.length.toLocaleString() +
        " words match · " + result.setList.length + " graphemes listed (" + inCorpus + " occur in the corpus)";
    }
    renderChips(result);
    renderUnlock(result);
    renderCoverage(result);
    renderCorpus(result);
  }

  var timer = null;
  function debounced() { clearTimeout(timer); timer = setTimeout(update, 150); }

  var toastTimer = null;
  function toast(msg) {
    el.toast.textContent = msg;
    el.toast.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { el.toast.hidden = true; }, 1400);
  }

  // ---- font -----------------------------------------------------------

  var fontFace = null;
  function loadFont(file) {
    file.arrayBuffer().then(function (buf) {
      var face = new FontFace("GraphemeFont", buf);
      return face.load().then(function () {
        if (fontFace) document.fonts.delete(fontFace);
        document.fonts.add(face);
        fontFace = face;
        el.fontName.textContent = file.name;
      });
    }).catch(function (e) { toast("could not load font: " + e.message); });
  }

  // ---- wiring ---------------------------------------------------------

  restore();

  ["setInput", "mustInput", "count", "perLine", "minLen", "maxLen", "coverage", "inventPct", "exRate"].forEach(function (id) {
    el[id].addEventListener("input", debounced);
  });
  ["fromParts", "mustMode", "layout", "sort", "inventMode", "cover", "markInv", "showNames",
   "exNumber", "exDate", "exTime", "exPunct", "exScript", "exPlace",
   "srcNews", "srcOther", "srcHeads", "srcNames", "srcDict", "srcLatin", "srcZwnj"].forEach(function (id) {
    el[id].addEventListener("change", update);
  });
  el.format.addEventListener("change", function () {
    el.count.value = counts[el.format.value];
    update();
  });
  el.preset.addEventListener("change", function () {
    var set = presets[el.preset.value];
    if (!set) { el.presetInfo.textContent = ""; return; }
    var gs = G.parseList(set.join(" ")).graphemes;
    el.setInput.value = gs.map(G.nameOf).join(" ");
    el.fromParts.checked = true;
    el.presetInfo.textContent = gs.length + " letters and signs · built from parts";
    update();
  });
  ["size", "leading"].forEach(function (id) {
    el[id].addEventListener("input", function () {
      el.output.style.fontSize = el.size.value + "px";
      el.output.style.lineHeight = el.leading.value;
      el.sizeOut.textContent = el.size.value;
      save();
    });
  });
  el.regen.addEventListener("click", function () { seed = (Math.random() * 0xffffffff) >>> 0; update(); });
  el.corpusFilter.addEventListener("input", function () { if (result) renderCorpus(result); });

  el.copyBtn.addEventListener("click", function () {
    var text = last.kind === "engine" ? TG.render(last.result, { sep: last.sep === "\n" ? "\n" : " " })
      : last.seq.map(function (wi) { return corpus.words[wi]; }).join(" ");
    navigator.clipboard.writeText(text).then(function () { toast("copied"); }, function () { toast("copy failed"); });
  });
  el.downloadBtn.addEventListener("click", function () {
    var a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([plainText() + "\n"], { type: "text/plain;charset=utf-8" }));
    a.download = "test-generator-" + last.format + ".txt";
    a.click();
    setTimeout(function () { URL.revokeObjectURL(a.href); }, 1000);
  });

  document.querySelectorAll(".tabs button").forEach(function (b) {
    b.addEventListener("click", function () {
      document.querySelectorAll(".tabs button").forEach(function (x) { x.classList.toggle("active", x === b); });
      document.querySelectorAll(".panel").forEach(function (p) { p.hidden = p.dataset.panel !== b.dataset.tab; });
    });
  });

  el.analyseInput.addEventListener("input", renderAnalyse);
  el.analyseUse.addEventListener("click", function () {
    var gs = renderAnalyse();
    if (!gs.length) return;
    el.setInput.value = gs.map(G.nameOf).join(" ");
    update();
    toast("grapheme set replaced (" + gs.length + ")");
  });
  el.analyseNames.addEventListener("click", function () {
    var names = renderAnalyse().map(G.nameOf).join(" ");
    navigator.clipboard.writeText(names).then(function () { toast("names copied"); }, function () { toast("copy failed"); });
  });

  el.fontInput.addEventListener("change", function () { if (el.fontInput.files[0]) loadFont(el.fontInput.files[0]); });
  el.corpusInput.addEventListener("change", function () {
    var files = el.corpusInput.files;
    if (!files.length) return;
    readFiles(files).then(function (texts) {
      useOwnWords(texts, Array.prototype.map.call(files, function (f) { return f.name; }).join(" + "));
    });
  });
  el.corpusReset.addEventListener("click", bundleWords);

  // Drop: fonts load as the preview font, text files become the word list.
  document.addEventListener("dragover", function (e) { e.preventDefault(); document.body.classList.add("dragging"); });
  document.addEventListener("dragleave", function (e) { if (!e.relatedTarget) document.body.classList.remove("dragging"); });
  document.addEventListener("drop", function (e) {
    e.preventDefault();
    document.body.classList.remove("dragging");
    var files = Array.prototype.slice.call(e.dataTransfer.files);
    var font = files.find(function (f) { return /\.(ttf|otf|woff2?)$/i.test(f.name); });
    var texts = files.filter(function (f) { return /\.(txt|md)$/i.test(f.name); });
    if (font) loadFont(font);
    if (texts.length) readFiles(texts).then(function (t) {
      useOwnWords(t, texts.map(function (f) { return f.name; }).join(" + "));
    });
  });

  update();
  loadPresets();
  loadEngine();
})();

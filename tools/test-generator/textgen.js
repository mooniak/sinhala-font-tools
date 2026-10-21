/*
 * textgen.js — realistic Sinhala test text restricted to a grapheme set.
 *
 * Works from the data bundle built by test-texts/corpus-build (data/). Given the
 * graphemes a font has, it makes text that uses only those graphemes:
 *
 *   chain      running text from corpus word-pair statistics
 *   sentences  real sentences, verbatim, that the font can show
 *   templates  real sentence shapes: renderable words kept, the rest replaced
 *              by invented words of the same shape
 *   targeted   real sentences densest in a chosen grapheme or class
 *
 * When the real vocabulary is too small, words are invented (see "Invention"):
 * a real word's sign pattern with new letters, a learned grapheme model, or a
 * random permutation — always within the hard rules of Sinhala word shape.
 *
 * Environment-neutral: the caller supplies `read(path) -> Promise<string>` for
 * the data folder. Browser: attaches `TextGen`. Node: module.exports, plus
 * TextGen.dirReader(dir). Depends on graphemes.js.
 *
 *   var eng = await TextGen.load(TextGen.dirReader("data"));
 *   var s = eng.session(["ක", "ට", "කා", "ටි"]);
 *   var r = s.chain({ seed: 1, words: 60 });   // { sentences, stats }
 *   TextGen.render(r)                          // "…"
 */
(function (root) {
  "use strict";

  var G = root.SinhalaGraphemes || (typeof require === "function" ? require("./graphemes.js") : null);

  var HAL = "්";
  var SIGN_START = /^[්-ෟෲෳ]/;
  // a bare sign, or a conjunct piece such as the repaya ර්‍ that only joins to a following consonant
  function isFragment(g) { return SIGN_START.test(g) || g.charAt(g.length - 1) === "\u200D"; }
  var WORD_RUN = /([඀-෿‌‍]+)/;
  var MIN_INITIAL_HAL = 300;           // a hal form may open a word if the corpus shows it at least this much

  // A sign the font lacks is replaced by its nearest relative (then none).
  var NEAR = {
    "ී": "ි", "ූ": "ු", "ේ": "ෙ", "ෝ": "ො",
    "ෑ": "ැ", "ෛ": "ෙ", "ෞ": "ො", "ෘ": "ු",
    "ෲ": "ෘ", "ෳ": "ෘ"
  };

  // ---- small utilities ------------------------------------------------

  function rng(seed) {
    var a = seed | 0;
    return function () {
      a = (a + 0x6d2b79f5) | 0;
      var t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  function shuffle(arr, rand) {
    for (var i = arr.length - 1; i > 0; i--) {
      var j = Math.floor(rand() * (i + 1));
      var t = arr[i]; arr[i] = arr[j]; arr[j] = t;
    }
    return arr;
  }

  /** Index into `weights` picked in proportion; `total` is their sum. */
  function wpick(weights, total, rand) {
    var t = rand() * total;
    for (var i = 0; i < weights.length; i++) if ((t -= weights[i]) <= 0) return i;
    return weights.length - 1;
  }

  function totals(table) {
    var out = {};
    for (var k in table) {
      var s = 0;
      for (var b in table[k]) s += table[k][b];
      out[k] = s;
    }
    return out;
  }

  /** base+sign combinations as graphemes: expand(["ක","ට"], ["ි","ු"]) -> ක කි කු ට ටි ටු. */
  function expand(bases, signs) {
    var seen = new Set(), out = [];
    function add(g) { g = g.normalize("NFC"); if (!seen.has(g)) { seen.add(g); out.push(g); } }
    bases.forEach(function (b) {
      add(b);
      if (/^[අ-ඖ]$/.test(b)) return;
      signs.forEach(function (s) { if (s !== "ං" && s !== "ඃ") add(b + s); });
    });
    signs.forEach(function (s) { if (s === "ං" || s === "ඃ") add(s); });
    return out;
  }

  // ---- the engine: data, shared across sessions -----------------------

  function Engine(raw, read) {
    var self = this;
    this.read = read;
    this.model = raw.model;
    this.index = raw.index;
    this.bigrams = raw.bigrams;
    this.gtab = [];                    // grapheme id -> { g, seg, d, tok }
    this.gid = new Map();
    this.words = [];                   // { w, run, mask, g: Int32Array }
    this.wordIndex = new Map();
    this.shards = new Map();           // shard number -> Promise<[record]>
    this.templates = null;
    this._next = [];

    raw.words.split("\n").forEach(function (line) {
      if (!line) return;
      var p = line.split("\t");
      var id = self.words.length;
      self.words.push({ w: p[0], run: +p[1] || 0, mask: +p[2] || 0, g: self.gidsOf(p[0]) });
      self.wordIndex.set(p[0], id);
    });

    var m = this.model;
    this.tot = { base: totals(m.base), bs: totals(m.baseSign), after: totals(m.afterBase), sn: totals(m.signNext) };
    this.skelCum = [];
    var s = 0;
    m.skeletons.forEach(function (k) { s += k[0]; self.skelCum.push(s); });
    this.initialHal = new Set(Object.keys(m.initialHal).filter(function (b) { return m.initialHal[b] >= MIN_INITIAL_HAL; }));
    var lens = Object.keys(m.len).map(Number).filter(function (n) { return n >= 2 && n <= 7; });
    this.lenW = lens.map(function (n) { return m.len[n]; });
    this.lenN = lens;
  }

  /** Sign token of a decomposed grapheme, as used by the model's skeletons. */
  function tokOf(d) { return d.kind === "V" ? "V" : d.kind === "M" ? d.sign : d.sign || "∅"; }

  Engine.prototype.gidOf = function (g) {
    var id = this.gid.get(g);
    if (id === undefined) {
      id = this.gtab.length;
      var d = G.decompose(g);
      this.gtab.push({ g: g, seg: G.segment(g)[0], d: d, tok: tokOf(d), stray: isFragment(g) });
      this.gid.set(g, id);
    }
    return id;
  };

  Engine.prototype.gidsOf = function (text) {
    var out = [], segs = G.segment(text);
    for (var i = 0; i < segs.length; i++) if (segs[i].sinhala) out.push(this.gidOf(segs[i].g));
    return Int32Array.from(out);
  };

  /** Successors of a context as [[index, count]]. 0 start, 1 comma, 2-4 sentence end, 5+i word row i. */
  Engine.prototype.succ = function (ctx) {
    var c = this._next[ctx];
    if (!c) {
      var s = this.bigrams.next[ctx] || "";
      c = this._next[ctx] = s ? s.split(",").map(function (p) { var q = p.split(":"); return [+q[0], +q[1]]; }) : [];
    }
    return c;
  };

  /** Violations of the hard word-shape rules (empty = fine). Rules are listed in the README. */
  Engine.prototype.violations = function (word) {
    var self = this, out = [];
    var ds = G.segment(word).filter(function (s) { return s.sinhala; }).map(function (s) { return { g: s.g, d: G.decompose(s.g) }; });
    if (ds.length < 2) out.push("H6");
    ds.forEach(function (x, i) {
      var d = x.d, p = i ? ds[i - 1] : null;
      if (d.kind === "V" && i > 0) out.push("H1");
      if (d.kind === "M" && (i === 0 || p.d.sign === HAL || p.d.kind === "M")) out.push("H2");
      if (d.sign === HAL && d.kind === "C") {
        if (i === 0 && !self.initialHal.has(d.base)) out.push("H3");
        if (p && p.d.sign === HAL) out.push("H4");
      }
      if (i > 1 && x.g === ds[i - 1].g && x.g === ds[i - 2].g) out.push("H5");
    });
    return out;
  };

  Engine.prototype.session = function (graphemes, opts) { return new Session(this, graphemes, opts || {}); };

  // ---- loading shards and templates -----------------------------------

  function parseRecords(engine, text) {
    var out = [], lines = text.split("\n");
    for (var i = 0; i < lines.length; i++) {
      if (!lines[i]) continue;
      var tab = lines[i].indexOf("\t");
      var t = lines[i].slice(tab + 1);
      out.push({ text: t, tags: lines[i].slice(0, tab), gids: engine.gidsOf(t) });
    }
    return out;
  }

  Engine.prototype.shard = function (n) {
    var self = this;
    if (!this.shards.has(n)) {
      this.shards.set(n, this.read("sentences/" + this.index.shards[n].file).then(function (t) { return parseRecords(self, t); }));
    }
    return this.shards.get(n);
  };

  Engine.prototype.loadTemplates = function () {
    var self = this;
    if (!this.templates) this.templates = this.read("templates.txt").then(function (t) { return parseRecords(self, t); });
    return this.templates;
  };

  // ---- a session: one grapheme set ------------------------------------

  /**
   * opts.fromParts   also count a grapheme as available when assembled from listed pieces
   * opts.sources     { running, names, dict } which word sources count as real words (all on)
   * opts.minFreq     running-text words seen fewer times are treated as typos, unless a word list carries them (3)
   * opts.zwnj        allow real words that contain an explicit ZWNJ (ස්‌ට); off by default
   */
  function Session(engine, graphemes, opts) {
    var e = this.e = engine, self = this;
    var seen = new Set();
    this.setList = [];
    graphemes.forEach(function (g) {
      g = String(g).normalize("NFC");
      if (!g || seen.has(g)) return;
      seen.add(g);
      self.setList.push(g);
      e.gidOf(g);
    });
    this.set = seen;
    this.fromParts = !!opts.fromParts;
    this.zwnj = !!opts.zwnj;
    this.minFreq = opts.minFreq === undefined ? 3 : opts.minFreq;
    var src = opts.sources || {};
    this.sources = { running: src.running !== false, names: src.names !== false, dict: src.dict !== false };

    this.avail = [];
    for (var id = 0; id < e.gtab.length; id++) this._avail(id);

    // real words the font can show
    this.okW = new Uint8Array(e.words.length);
    this.real = [];
    this.cum = [];
    this.byGid = new Map();
    var cum = 0, S = this.sources;
    for (var i = 0; i < e.words.length; i++) {
      var w = e.words[i];
      var allowed = (w.run >= this.minFreq && S.running) || ((w.mask & 7) && S.names) || ((w.mask & 8) && S.dict) || ((w.mask & 16) && S.running);
      if (!allowed || !w.g.length || (!this.zwnj && w.w.indexOf("\u200C") !== -1)) continue;
      var ok = true;
      for (var k = 0; k < w.g.length; k++) if (!this._avail(w.g[k])) { ok = false; break; }
      if (!ok) continue;
      this.okW[i] = 1;
      this.real.push(i);
      cum += w.run > 0 ? Math.pow(w.run, 0.7) : 0.3;
      this.cum.push(cum);
      var distinct = new Set(w.g);
      distinct.forEach(function (gid) {
        var l = self.byGid.get(gid);
        if (!l) self.byGid.set(gid, l = []);
        l.push(i);
      });
    }

    // graphemes whose use a text should show, and those usable for invention
    this.targets = [];
    this.bySign = {};
    for (var j = 0; j < e.gtab.length; j++) {
      var t = e.gtab[j];
      if (!this._avail(j) || t.stray) continue;
      if (this.set.has(t.g) || this.fromParts) this.targets.push(j);
      (this.bySign[t.tok] || (this.bySign[t.tok] = [])).push(j);
    }
    this.all = [];
    for (var tk in this.bySign) this.bySign[tk].forEach(function (id) { self.all.push(e.gtab[id]); });
    this.pool = null;                  // usable real sentences, after loadSentences
  }

  Session.prototype._avail = function (id) {
    var a = this.avail[id];
    if (a === undefined) {
      var t = this.e.gtab[id];
      a = this.avail[id] = G.availability(t.seg, this.set, this.fromParts) ? 1 : 0;
    }
    return a === 1;
  };

  /** Counts: real words, graphemes with no real word, and listed signs that stand on their own. */
  Session.prototype.info = function () {
    var self = this;
    var uncoverable = this.targets.filter(function (id) { return !self.byGid.has(id); })
      .map(function (id) { return self.e.gtab[id].g; });
    var strays = this.setList.filter(isFragment);
    return { graphemes: this.setList.length, targets: this.targets.length, realWords: this.real.length, uncoverable: uncoverable, strays: strays };
  };

  // ---- invention ------------------------------------------------------

  function P(tbl, tot, key, x, a) {
    var r = tbl[key];
    return (((r && r[x]) || 0) + a) / ((tot[key] || 0) + a * 30);
  }

  /** Can grapheme `c` go after `prev`/`prev2` at position i of an invented word? Hard rules H1–H5. */
  function allowed(e, c, i, prev, prev2) {
    var d = c.d;
    if (d.kind === "V") return i === 0;
    if (d.kind === "M") return i > 0 && prev.d.sign !== HAL && prev.d.kind !== "M";
    if (d.sign === HAL) {
      if (i === 0 && !e.initialHal.has(d.base)) return false;
      if (prev && prev.d.sign === HAL) return false;
    }
    if (prev && prev2 && c.g === prev.g && c.g === prev2.g) return false;
    return true;
  }

  /** Weight of grapheme `c` at position `pos` ("I" first, "M" middle, "F" last) after `prev`. */
  function fitWeight(e, c, pos, prev, used, ctl) {
    var d = c.d;
    if (d.kind === "M") return 1;
    var m = e.model, T = e.tot, b = d.base;
    var w = prev && prev.d.kind !== "M"
      ? 0.7 * P(m.afterBase, T.after, (prev.d.sign === HAL ? "H|" : "O|") + prev.d.base, b, 2) + 0.3 * P(m.base, T.base, pos, b, 2)
      : P(m.base, T.base, pos, b, 2);
    w = Math.pow(w * Math.sqrt(P(m.baseSign, T.bs, b, pos + c.tok, 0.5)), 0.6);
    for (var i = 0; i < used.length; i++) if (used[i].d.base === b) { w *= 0.35; break; }
    if (ctl.bias) w /= Math.pow(1 + (ctl.use[ctl.id(c)] || 0), 2 * ctl.bias);
    return w;
  }

  /**
   * Controls shared by all invention routines:
   *   rand, use (grapheme id -> times shown), bias (0..1 coverage pull), id(c)
   */
  Session.prototype._ctl = function (rand, use, bias) {
    var self = this;
    return { rand: rand, use: use || {}, bias: bias || 0, id: function (c) { return self.e.gid.get(c.g); } };
  };

  Session.prototype._cand = function (tok) {
    var e = this.e;
    if (!this.bySign[tok] || !this.bySign[tok].length) {
      while (NEAR[tok] && (!this.bySign[tok] || !this.bySign[tok].length)) tok = NEAR[tok];
      if (!this.bySign[tok] || !this.bySign[tok].length) tok = "∅";
    }
    return (this.bySign[tok] || []).map(function (id) { return e.gtab[id]; });
  };

  /** Fill a sign skeleton (["∅","ි","∅"]) with letters. `force` (a grapheme) is placed at a matching position when it can. */
  Session.prototype._fill = function (signs, ctl, force) {
    var e = this.e, out = [], n = signs.length;
    var forcePos = -1;
    if (force) {
      var at = [];
      signs.forEach(function (s, i) { if (s === force.tok && (force.d.kind !== "V" || i === 0)) at.push(i); });
      if (at.length) forcePos = at[Math.floor(ctl.rand() * at.length)];
    }
    for (var i = 0; i < n; i++) {
      var tok = signs[i] === "V" && i > 0 ? "∅" : signs[i];
      var pos = i === 0 ? "I" : i === n - 1 ? "F" : "M";
      var prev = out[i - 1], prev2 = out[i - 2];
      var cands = (i === forcePos ? [force] : this._cand(tok)).filter(function (c) { return allowed(e, c, i, prev, prev2); });
      if (!cands.length && i === forcePos) cands = this._cand(tok).filter(function (c) { return allowed(e, c, i, prev, prev2); });
      if (!cands.length) return null;
      var ws = cands.map(function (c) { return fitWeight(e, c, pos, prev, out, ctl); });
      var tot = ws.reduce(function (a, b) { return a + b; }, 0);
      if (!(tot > 0)) return null;
      out.push(cands[wpick(ws, tot, ctl.rand)]);
    }
    return out.map(function (c) { return c.g; }).join("");
  };

  Session.prototype._skeleton = function (rand, force) {
    var e = this.e, sk = e.model.skeletons;
    if (force) {
      var f = sk.filter(function (k) { return k[1].indexOf(force.tok) !== -1; });
      if (f.length) return f[wpick(f.map(function (k) { return k[0]; }), f.reduce(function (a, k) { return a + k[0]; }, 0), rand)][1];
    }
    var t = rand() * e.skelCum[e.skelCum.length - 1], lo = 0, hi = e.skelCum.length - 1;
    while (lo < hi) { var mid = (lo + hi) >> 1; if (e.skelCum[mid] >= t) hi = mid; else lo = mid + 1; }
    return sk[lo][1];
  };

  /** A word built grapheme by grapheme from the learned model. */
  Session.prototype._modelWord = function (ctl, force) {
    var e = this.e, rand = ctl.rand, n = e.lenN[wpick(e.lenW, e.lenW.reduce(function (a, b) { return a + b; }, 0), rand)];
    var all = this.all, out = [];
    var fp = force ? Math.floor(rand() * n) : -1;
    for (var i = 0; i < n; i++) {
      var pos = i === 0 ? "I" : i === n - 1 ? "F" : "M", prev = out[i - 1], prev2 = out[i - 2];
      var pt = prev ? prev.tok : "^";
      var cands = (i === fp ? [force] : all).filter(function (c) { return allowed(e, c, i, prev, prev2); });
      if (!cands.length) cands = all.filter(function (c) { return allowed(e, c, i, prev, prev2); });
      if (!cands.length) return null;
      var ws = cands.map(function (c) {
        return fitWeight(e, c, pos, prev, out, ctl) * P(e.model.signNext, e.tot.sn, pos + "|" + pt, c.tok, 2);
      });
      var tot = ws.reduce(function (a, b) { return a + b; }, 0);
      if (!(tot > 0)) return null;
      out.push(cands[wpick(ws, tot, rand)]);
    }
    return out.map(function (c) { return c.g; }).join("");
  };

  /** A word of random graphemes — still within the hard rules. */
  Session.prototype._permWord = function (ctl) {
    var e = this.e, rand = ctl.rand, all = this.all, out = [];
    var n = 2 + [0, 0, 0, 1, 1, 1, 1, 2, 2, 3][Math.floor(rand() * 10)];
    for (var i = 0; i < n; i++) {
      var prev = out[i - 1], prev2 = out[i - 2];
      var cands = all.filter(function (c) { return allowed(e, c, i, prev, prev2); });
      if (!cands.length) return null;
      var w = cands.map(function (c) { return ctl.bias ? 1 / Math.pow(1 + (ctl.use[ctl.id(c)] || 0), 2 * ctl.bias) : 1; });
      out.push(cands[wpick(w, w.reduce(function (a, b) { return a + b; }, 0), rand)]);
    }
    return out.map(function (c) { return c.g; }).join("");
  };

  var METHODS = { swap: 0.35, model: 0.55, perm: 0.1 };

  /**
   * Invent one word. `like` (a real word) gives the shape to copy (pattern swap);
   * `force` (a grapheme string) must appear in the word. Returns { w, inv }:
   * inv is false when the result happens to be a real corpus word.
   */
  Session.prototype.invent = function (ctl, like, force, taken) {
    var e = this.e, f = force ? e.gtab[e.gidOf(force)] : null, self = this;
    for (var tries = 0; tries < 12; tries++) {
      var w = null;
      if (like) {
        var signs = G.segment(like).filter(function (s) { return s.sinhala; }).map(function (s) { return tokOf(G.decompose(s.g)); });
        w = this._fill(signs, ctl, f);
      } else {
        var r = ctl.rand();
        if (r < METHODS.swap) w = this._fill(this._skeleton(ctl.rand, f), ctl, f);
        else if (r < METHODS.swap + METHODS.model) w = this._modelWord(ctl, f);
        else w = this._permWord(ctl);
      }
      if (!w || w === like || (taken && taken.has(w) && tries < 8)) continue;
      if (f && e.gidsOf(w).indexOf(e.gid.get(force)) === -1) continue;
      if (e.violations(w).length) continue;
      if (taken) taken.add(w);
      return { w: w, inv: !e.wordIndex.has(w) };
    }
    return null;
  };

  // ---- shared by the text modes ---------------------------------------

  function mark(use, gids, by) { for (var i = 0; i < gids.length; i++) use[gids[i]] = (use[gids[i]] || 0) + (by || 1); }

  function wordPiece(t, inv) { return { t: t, w: true, inv: !!inv }; }
  function textPiece(t) { return { t: t, w: false, inv: false }; }

  function stats(session, sentences, use) {
    var words = 0, inv = 0;
    sentences.forEach(function (s) { s.forEach(function (p) { if (p.w) { words++; if (p.inv) inv++; } }); });
    var shown = session.targets.filter(function (id) { return use[id] > 0; }).length;
    var missing = session.targets.filter(function (id) { return !(use[id] > 0); }).map(function (id) { return session.e.gtab[id].g; });
    return { words: words, invented: inv, inventedPct: words ? inv / words : 0, graphemes: session.targets.length, shown: shown, missing: missing };
  }

  /**
   * Make sure every listed grapheme appears: swap a covering word (real if one
   * exists, otherwise invented) into positions of the text that cost least.
   * Words past the room available go in an extra sentence.
   */
  Session.prototype._cover = function (sentences, use, rand, taken) {
    var self = this, e = this.e, ctl = this._ctl(rand, use, 0), extra = [];
    var slots = [];
    sentences.forEach(function (s, si) { s.forEach(function (p, pi) { if (p.w && pi > 0) slots.push([si, pi]); }); });
    shuffle(slots, rand);
    // replacing a word can uncover another grapheme, so go round a few times
    for (var pass = 0; pass < 3; pass++) {
      var missing = shuffle(this.targets.filter(function (id) { return !(use[id] > 0); }), rand);
      if (!missing.length) break;
      missing.forEach(function (id) {
        if (use[id] > 0) return;
        var g = e.gtab[id].g, word, inv = false;
        var reals = self.byGid.get(id);
        if (reals && reals.length) {
          // prefer a word that also shows other graphemes still missing
          var bestW = null, bestScore = -1;
          for (var c = 0; c < Math.min(150, reals.length); c++) {
            var cw = e.words[reals[Math.floor(rand() * reals.length)]], gs = new Set(), fresh = 0;
            for (var x = 0; x < cw.g.length; x++) if (!gs.has(cw.g[x])) { gs.add(cw.g[x]); if (!(use[cw.g[x]] > 0)) fresh++; }
            var score = fresh * fresh / cw.g.length + rand() * 0.01;
            if (score > bestScore) { bestScore = score; bestW = cw; }
          }
          word = bestW.w;
        } else {
          var r = self.invent(ctl, null, g, taken);
          if (!r) return;
          word = r.w; inv = r.inv;
        }
        var best = -1, bestCost = Infinity;
        for (var k = 0; k < Math.min(10, slots.length); k++) {
          var old = e.gidsOf(sentences[slots[k][0]][slots[k][1]].t), cost = 0;
          for (var x = 0; x < old.length; x++) if (use[old[x]] <= 1) cost++;
          if (cost < bestCost) { bestCost = cost; best = k; }
        }
        if (best >= 0 && bestCost === 0) {   // swap in place only if nothing becomes uncovered
          var slot = slots.splice(best, 1)[0], piece = sentences[slot[0]][slot[1]];
          mark(use, e.gidsOf(piece.t), -1);
          piece.t = word; piece.inv = inv;
        } else {
          extra.push(wordPiece(word, inv));
        }
        mark(use, e.gidsOf(word));
      });
    }
    // no room left in the text: the rest go in sentences of their own, ten words at most
    for (var at = 0; at < extra.length; at += 10) {
      var s = [];
      extra.slice(at, at + 10).forEach(function (p, i) { if (i) s.push(textPiece(" ")); s.push(p); });
      s.push(textPiece("."));
      sentences.push(s);
    }
  };

  /** Invention policy: { mode: "auto", max } invents only when needed; { mode: "ratio", ratio } invents that share. */
  function policy(inv) {
    inv = inv || {};
    return inv.mode === "ratio" ? { ratio: Math.max(0, Math.min(1, inv.ratio || 0)), max: 1 } : { ratio: null, max: inv.max === undefined ? 0.4 : inv.max };
  }

  // ---- invented words on their own ------------------------------------

  /**
   * A list of invented words. seed, count, coverage, cover (default on: words are
   * built around graphemes not yet shown until all are), contains (graphemes the
   * words should carry, cycled through).
   * Returns { sentences: [[piece]], stats } with one word per "sentence".
   */
  Session.prototype.pseudo = function (o) {
    o = o || {};
    var e = this.e, rand = rng(o.seed === undefined ? 1 : o.seed), n = o.count || 40;
    var use = {}, ctl = this._ctl(rand, use, o.coverage === undefined ? 0.5 : o.coverage), taken = new Set();
    var contains = (o.contains || []).map(function (g) { e.gidOf(g); return g; });
    var words = [], tries = 0;
    while (words.length < n && tries++ < n * 20) {
      var force = null;
      if (contains.length) force = contains[words.length % contains.length];
      else if (o.cover !== false) {
        var missing = this.targets.filter(function (id) { return !(use[id] > 0); });
        if (missing.length) force = e.gtab[missing[Math.floor(rand() * missing.length)]].g;
      }
      var r = this.invent(ctl, null, force, taken);
      if (!r) continue;
      words.push([wordPiece(r.w, r.inv)]);
      mark(use, e.gidsOf(r.w));
    }
    return { sentences: words, stats: stats(this, words, use), mode: "pseudo" };
  };

  // ---- chain ----------------------------------------------------------

  /**
   * Running text from word-pair statistics.
   *   seed, words (count), coverage 0..1 (pull toward under-used graphemes),
   *   invent ({mode:"auto", max} | {mode:"ratio", ratio}), cover (default true:
   *   every listed grapheme appears at least once)
   * Returns { sentences: [[piece]], stats }, piece = { t, w, inv }.
   */
  Session.prototype.chain = function (o) {
    o = o || {};
    var e = this.e, self = this, rand = rng(o.seed === undefined ? 1 : o.seed);
    var want = o.words || 80, pol = policy(o.invent), bias = o.coverage === undefined ? 0.5 : o.coverage;
    var use = {}, ctl = this._ctl(rand, use, bias), taken = new Set();
    var made = 0, invented = 0, stall = 0, lastAt = new Map(), sentences = [];

    function pen(wi) {
      var at = lastAt.get(wi);
      if (at === undefined) return 1;
      var d = made - at;
      return d < 12 ? 0.15 : d < 40 ? 0.5 : 1;
    }
    function boost(wi) {
      if (!bias) return 1;
      var g = e.words[wi].g, seen = new Set(), need = 0;
      for (var i = 0; i < g.length; i++) if (!seen.has(g[i])) { seen.add(g[i]); need += 1 / (1 + (use[g[i]] || 0)); }
      return 1 + bias * 30 * (seen.size ? need / seen.size : 0);
    }
    function unigram() {
      if (!self.real.length) return -1;
      var best = -1, bw = -1, total = self.cum[self.cum.length - 1];
      for (var k = 0; k < 6; k++) {
        var t = rand() * total, lo = 0, hi = self.cum.length - 1;
        while (lo < hi) { var mid = (lo + hi) >> 1; if (self.cum[mid] >= t) hi = mid; else lo = mid + 1; }
        var wi = self.real[lo], w = pen(wi) * boost(wi) * rand();
        if (w > bw) { bw = w; best = wi; }
      }
      return best;
    }
    // a real vocabulary too small to avoid repeating itself gets a share of invented words
    var tiny = pol.ratio === null ? Math.max(0, Math.min(0.55, 1 - this.real.length / 400)) : 0;
    function wantInvented() {
      if (!self.real.length) return true;
      if (pol.ratio !== null) return rand() < pol.ratio;
      if (invented >= pol.max * Math.max(made, 1)) return false;
      return rand() < tiny;
    }

    while (made < want && stall < 20) {
      var pieces = [], len = 0, ctx = 0, target = 6 + Math.floor(rand() * 12), lastComma = false, endMark = ".";
      while (made < want) {
        // what the corpus says can follow
        var cands = [], ws = [], wordW = 0;
        if (ctx >= 0) {
          var list = e.succ(ctx);
          for (var q = 0; q < list.length; q++) {
            var j = list[q][0], n = list[q][1], w;
            if (j === 1) w = len >= 2 && !lastComma && len < target - 1 ? n : 0;
            else if (j <= 4) w = len >= 4 && !lastComma ? n * (len >= target ? 4 : 1) : 0;
            else {
              if (!self.okW[j - 5]) continue;
              w = n * pen(j - 5) * boost(j - 5);
              wordW += w;
            }
            if (w > 0) { cands.push(j); ws.push(w); }
          }
        }
        var tok = null;
        if (wordW > 0) tok = cands[wpick(ws, ws.reduce(function (a, b) { return a + b; }, 0), rand)];
        else if (len >= 4 && !lastComma && (len >= target || (ctx >= 0 && rand() < 0.5))) tok = 2;

        if (tok === 1) { pieces.push(textPiece(",")); lastComma = true; ctx = 1; continue; }
        if (tok !== null && tok <= 4) { endMark = ["", "", ".", "?", "!"][tok]; break; }

        // a word: from the chain, else from overall frequency, else invented
        var inv = wantInvented(), piece = null, wid = -1;
        if (!inv && tok !== null) { wid = tok - 5; piece = wordPiece(e.words[wid].w, false); }
        else if (!inv && (wid = unigram()) >= 0) piece = wordPiece(e.words[wid].w, false);
        else {
          var r = self.invent(ctl, null, null, taken);
          if (r) {
            wid = r.inv ? -1 : e.wordIndex.get(r.w);
            piece = wordPiece(r.w, r.inv);
            if (r.inv) invented++;
          } else if ((wid = unigram()) >= 0) piece = wordPiece(e.words[wid].w, false);
        }
        if (!piece) break;
        if (len > 0) pieces.push(textPiece(" "));
        pieces.push(piece);
        len++; made++; lastComma = false;
        ctx = wid >= 0 && wid < e.bigrams.vocab ? 5 + wid : -1;
        if (wid >= 0) lastAt.set(wid, made);
        mark(use, e.gidsOf(piece.t));
      }
      if (len) {
        if (lastComma) pieces.pop();
        pieces.push(textPiece(endMark));
        sentences.push(pieces);
        stall = 0;
      } else stall++;
    }

    if (o.cover !== false && sentences.length) this._cover(sentences, use, rand, taken);
    return { sentences: sentences, stats: stats(this, sentences, use), mode: "chain" };
  };

  // ---- real sentences -------------------------------------------------

  /**
   * Load the sentences this set can show. Only shards that could contain a
   * usable sentence are fetched. onProgress(done, total) is optional.
   */
  Session.prototype.loadSentences = function (onProgress) {
    var self = this, e = this.e, idx = e.index;
    var rankOk = idx.graphemes.map(function (g) { return self._avail(e.gidOf(g)); });
    var pre = [0];
    rankOk.forEach(function (ok, i) { pre.push(pre[i] + (ok ? 1 : 0)); });
    var need = [];
    idx.shards.forEach(function (s, n) { if (pre[s.hi + 1] - pre[s.lo] > 0) need.push(n); });
    var done = 0;
    if (onProgress) onProgress(0, need.length);
    return Promise.all(need.map(function (n) {
      return e.shard(n).then(function (recs) { if (onProgress) onProgress(++done, need.length); return recs; });
    })).then(function (all) {
      var pool = [];
      all.forEach(function (recs) {
        recs.forEach(function (r) {
          for (var i = 0; i < r.gids.length; i++) if (!self._avail(r.gids[i])) return;
          pool.push(r);
        });
      });
      self.pool = pool;
      return { shards: need.length, of: idx.shards.length, sentences: pool.length };
    });
  };

  /** exclude: tag letters to leave out (default "ln": Latin, ZWNJ); sources: tag letters allowed ("12pegj"), default all. */
  function tagFilter(o) {
    var ex = o.exclude === undefined ? "ln" : o.exclude, src = o.sources;
    return function (r) {
      for (var i = 0; i < r.tags.length; i++) {
        var t = r.tags[i];
        if (ex.indexOf(t) !== -1) return false;
      }
      if (src !== undefined) { var s = r.tags[0]; if (/[12peg]/.test(s) && src.indexOf(s) === -1) return false; }
      return true;
    };
  }

  function recordSentence(r) {
    var parts = r.text.split(WORD_RUN), out = [];
    parts.forEach(function (t, i) { if (t) out.push(i % 2 ? wordPiece(t, false) : textPiece(t)); });
    return out;
  }

  /** Real sentences the font can show, verbatim. Needs loadSentences first. */
  Session.prototype.sentences = function (o) {
    o = o || {};
    if (!this.pool) throw new Error("call loadSentences() first");
    var e = this.e, rand = rng(o.seed === undefined ? 1 : o.seed), n = o.count || 10;
    var ok = tagFilter(o), minW = o.minWords || 0, maxW = o.maxWords || Infinity;
    var pool = this.pool.filter(function (r) {
      if (!ok(r)) return false;
      var w = r.text.split(" ").length;
      return w >= minW && w <= maxW;
    });
    shuffle(pool, rand);
    var picked = [], use = {};
    if (o.cover !== false) {
      var missing = new Set(this.targets);
      for (var i = 0; i < pool.length && missing.size && picked.length < n; i++) {
        var hit = false;
        for (var k = 0; k < pool[i].gids.length; k++) if (missing.has(pool[i].gids[k])) { hit = true; break; }
        if (hit) { picked.push(pool[i]); pool[i].gids.forEach(function (g) { missing.delete(g); }); pool[i] = null; }
      }
      pool = pool.filter(Boolean);
    }
    for (var j = 0; picked.length < n && j < pool.length; j++) picked.push(pool[j]);
    shuffle(picked, rand);
    var sentences = picked.map(recordSentence);
    picked.forEach(function (r) { mark(use, r.gids); });
    return { sentences: sentences, stats: stats(this, sentences, use), mode: "sentences", available: pool.length + picked.length };
  };

  /**
   * Real sentences densest in a target.
   *   spec.graphemes  exact graphemes
   *   spec.signs      any grapheme carrying one of these signs
   *   spec.classes    "rakar" | "yansa" | "repha" | "conjunct" (any ZWJ conjunct)
   */
  Session.prototype.targeted = function (spec, o) {
    o = o || {};
    if (!this.pool) throw new Error("call loadSentences() first");
    var e = this.e, rand = rng(o.seed === undefined ? 1 : o.seed), n = o.count || 10;
    var wantG = new Set(spec.graphemes || []), wantS = new Set(spec.signs || []), cls = spec.classes || [];
    var hits = new Map();
    function match(id) {
      var h = hits.get(id);
      if (h !== undefined) return h;
      var t = e.gtab[id];
      h = wantG.has(t.g) || (t.d.sign && wantS.has(t.d.sign)) ||
        cls.some(function (c) {
          if (c === "rakar") return t.seg.parts.indexOf("්‍ර") !== -1;
          if (c === "yansa") return t.seg.parts.indexOf("්‍ය") !== -1;
          if (c === "repha") return t.seg.parts.indexOf("ර්‍") !== -1;
          if (c === "conjunct") return t.g.indexOf("‍") !== -1;
          return false;
        });
      hits.set(id, h);
      return h;
    }
    var ok = tagFilter(o), minHits = o.minHits || 1, scored = [];
    this.pool.forEach(function (r) {
      if (!ok(r)) return;
      var h = 0;
      for (var i = 0; i < r.gids.length; i++) if (match(r.gids[i])) h++;
      if (h >= minHits) scored.push({ r: r, s: Math.pow(h, 1.5) / r.gids.length + rand() * 0.001 });   // density, with a pull toward more hits
    });
    scored.sort(function (a, b) { return b.s - a.s; });
    var picked = scored.slice(0, n).map(function (x) { return x.r; });
    var use = {};
    picked.forEach(function (r) { mark(use, r.gids); });
    var sentences = picked.map(recordSentence);
    return { sentences: sentences, stats: stats(this, sentences, use), mode: "targeted", matching: scored.length };
  };

  // ---- templates ------------------------------------------------------

  /**
   * Real sentence shapes with invented words. Each sentence keeps the words the
   * font can render, the rest become same-shaped invented words; punctuation
   * and numerals stay. Returns a promise (the template pool is loaded on first use).
   *   count, seed, coverage, invent ({mode:"auto", max} | {mode:"ratio", ratio})
   */
  Session.prototype.templates = function (o) {
    var self = this;
    return this.e.loadTemplates().then(function (pool) { return self._templates(pool, o || {}); });
  };

  Session.prototype._templates = function (pool, o) {
    var e = this.e, self = this, rand = rng(o.seed === undefined ? 1 : o.seed);
    var n = o.count || 8, pol = policy(o.invent), bias = o.coverage === undefined ? 0.5 : o.coverage;
    var use = {}, ctl = this._ctl(rand, use, bias), taken = new Set(), ok = tagFilter(o);
    var sentences = [];

    function analyse(r) {
      var parts = r.text.split(WORD_RUN), words = 0, kept = 0;
      for (var i = 1; i < parts.length; i += 2) {
        words++;
        var wi = e.wordIndex.get(parts[i]);
        if (wi !== undefined && self.okW[wi]) kept++;
      }
      return { parts: parts, words: words, kept: kept };
    }

    for (var s = 0; s < n; s++) {
      var best = null, bestScore = -1;
      for (var t = 0; t < 60; t++) {
        var r = pool[Math.floor(rand() * pool.length)];
        if (!ok(r)) continue;
        var a = analyse(r);
        if (!a.words) continue;
        var frac = a.kept / a.words;
        var score = pol.ratio !== null ? rand() : (1 - frac <= pol.max ? 1 + frac : frac) + rand() * 0.2;
        if (score > bestScore) { bestScore = score; best = a; }
      }
      if (!best) continue;
      var pieces = [];
      best.parts.forEach(function (p, i) {
        if (i % 2 === 0) { if (p) pieces.push(textPiece(p)); return; }
        var wi = e.wordIndex.get(p), real = wi !== undefined && self.okW[wi];
        var swap = !real || (pol.ratio !== null && rand() < pol.ratio);
        if (swap) {
          var r = self.invent(ctl, p, null, taken);
          if (r) { pieces.push(wordPiece(r.w, r.inv)); mark(use, e.gidsOf(r.w)); return; }
          if (real) { pieces.push(wordPiece(p, false)); mark(use, e.gidsOf(p)); return; }
          var any = self.invent(ctl, null, null, taken);   // the shape would not do (e.g. one grapheme)
          if (any) { pieces.push(wordPiece(any.w, any.inv)); mark(use, e.gidsOf(any.w)); }
          return;
        }
        pieces.push(wordPiece(p, false));
        mark(use, e.gidsOf(p));
      });
      sentences.push(pieces);
    }
    if (o.cover !== false && sentences.length) this._cover(sentences, use, rand, taken);
    return { sentences: sentences, stats: stats(this, sentences, use), mode: "templates" };
  };

  // ---- output ---------------------------------------------------------

  /** Plain text of a result. opts.sep joins sentences (default " "). */
  function render(result, opts) {
    var sep = opts && opts.sep !== undefined ? opts.sep : " ";
    return result.sentences.map(function (s) { return s.map(function (p) { return p.t; }).join(""); }).join(sep);
  }

  // ---- loading --------------------------------------------------------

  /** Fetch the data bundle through read(path) -> Promise<string>. */
  function load(read) {
    return Promise.all([
      read("words.txt"), read("bigrams.json"), read("model.json"), read("sentences/index.json")
    ]).then(function (r) {
      return new Engine({ words: r[0], bigrams: JSON.parse(r[1]), model: JSON.parse(r[2]), index: JSON.parse(r[3]) }, read);
    });
  }

  /** Node: a reader for a data directory. */
  function dirReader(dir) {
    var fs = require("fs"), path = require("path");
    return function (rel) { return fs.promises.readFile(path.join(dir, rel), "utf8"); };
  }

  var api = { load: load, dirReader: dirReader, render: render, expand: expand, rng: rng, shuffle: shuffle };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.TextGen = api;
})(typeof globalThis !== "undefined" ? globalThis : this);

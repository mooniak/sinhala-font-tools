/*
 * stats.js — word table, word-pair (bigram) counts, and the tables the
 * word-invention model learns from.
 */
"use strict";

const { RUN } = require("./clean");

// Bits in a word's `mask`: which non-running-text sources list it.
const MASK = { person: 1, place: 2, water: 4, dict: 8, func: 16 };

// ---- word table ----------------------------------------------------------

class WordTable {
  constructor() { this.m = new Map(); }               // word -> [running freq, mask]
  add(w, run, mask) {
    let e = this.m.get(w);
    if (!e) this.m.set(w, e = [0, 0]);
    e[0] += run;
    e[1] |= mask;
  }
  /** Rows sorted by running frequency (then mask-only words by code point). */
  rows(minRun) {
    const out = [];
    for (const [w, [run, mask]] of this.m) if (run >= minRun || mask) out.push([w, run, mask]);
    out.sort((a, b) => b[1] - a[1] || (a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0));
    return out;
  }
}

// ---- tokens in a cleaned line -------------------------------------------

const TOKEN = new RegExp(RUN.source + "|[,.?!]|[;:]|[0-9A-Za-z\\ufffc]+|\\S", "g");

/** cb(kind, value): kind "w" word, "," comma, "." sentence end, "b" break (digits, Latin, rejected token). */
function forEachToken(text, cb) {
  TOKEN.lastIndex = 0;
  let m;
  while ((m = TOKEN.exec(text))) {
    const t = m[0], c = t.charCodeAt(0);
    if (c >= 0x0d80 && c <= 0x0dff) cb("w", t);
    else if (t === ",") cb(",", t);
    else if (t === "." || t === "?" || t === "!") cb(".", t);
    else if (t === ";" || t === ":" || /^[0-9A-Za-z￼]/.test(t)) cb("b", t);
    // quotes, brackets, dashes: ignored, adjacency carries on
  }
}

// ---- bigrams -------------------------------------------------------------

const SPECIALS = ["<s>", ",", ".", "?", "!"];

/**
 * Count word pairs over cleaned running-text lines. Context indices:
 * 0 sentence start, 1 comma, 2–4 sentence end marks (".", "?", "!"),
 * 5+i = row i of the word table. Only the first `vocab` rows take part.
 */
function buildBigrams(lines, wordIndex, vocab, pairMin, maxSucc) {
  const counts = new Map();
  const N = 1 << 20;
  const bump = (a, b) => { const k = a * N + b; counts.set(k, (counts.get(k) || 0) + 1); };
  const ENDS = { ".": 2, "?": 3, "!": 4 };
  for (const line of lines) {
    let prev = 0;                                // sentence start
    forEachToken(line, (kind, t) => {
      if (kind === "w") {
        const i = wordIndex.get(t);
        if (i === undefined || i >= vocab) { prev = -1; return; }
        if (prev >= 0) bump(prev, 5 + i);
        prev = 5 + i;
      } else if (kind === ",") {
        if (prev > 4) { bump(prev, 1); prev = 1; }
        else if (prev !== 0) prev = -1;          // ",," or a comma after a break; at sentence start: ignored
      } else if (kind === ".") {
        if (prev > 4) bump(prev, ENDS[t]);
        prev = 0;
      } else {
        prev = -1;
      }
    });
  }
  const next = new Array(5 + vocab);
  const tmp = new Map();
  for (const [k, n] of counts) {
    if (n < pairMin) continue;
    const a = Math.floor(k / N), b = k - a * N;
    let l = tmp.get(a);
    if (!l) tmp.set(a, l = []);
    l.push([b, n]);
  }
  let pairs = 0;
  for (let a = 0; a < next.length; a++) {
    const l = (tmp.get(a) || []).sort((x, y) => y[1] - x[1] || x[0] - y[0]).slice(0, maxSucc);
    pairs += l.length;
    next[a] = l.map(([b, n]) => b + ":" + n).join(",");
  }
  return { specials: SPECIALS, vocab, pairs, next };
}

// ---- word-invention model -----------------------------------------------

const SINGLE_SIGNS = new Set("ා ැ ෑ ි ී ු ූ ෘ ෲ ෟ ෳ ෙ ේ ෛ ො ෝ ෞ ්".split(" "));

/**
 * Learn how Sinhala words are put together, from words with running freq >= minRun.
 * A word is a list of graphemes; each is split into base + sign (decompose), and
 * the tables count how bases and signs follow one another by position
 * (I initial, M medial, F final). Counts are sqrt(freq), so very common words
 * do not drown the rest, and scaled x10 into integers.
 */
function buildModel(rows, G, minRun) {
  const B0 = {}, BS = {}, B = {}, SN = {}, INIT_HAL = {}, LEN = {}, SK = new Map();
  let used = 0;
  const add = (o, a, b, w) => { const r = o[a] || (o[a] = {}); r[b] = (r[b] || 0) + w; };

  for (const [word, run] of rows) {
    if (run < minRun) break;                     // rows are sorted by run desc
    const gs = G.segment(word).filter((s) => s.sinhala).map((s) => G.decompose(s.g));
    if (!gs.length || gs.some((d) => d.kind === "C" && d.sign && !SINGLE_SIGNS.has(d.sign))) continue;
    used++;
    const w = Math.sqrt(run), n = gs.length;
    const tok = (d) => d.kind === "V" ? "V" : d.kind === "M" ? d.sign : d.sign || "∅";
    LEN[Math.min(n, 12)] = (LEN[Math.min(n, 12)] || 0) + w;
    gs.forEach((d, i) => {
      const pos = i === 0 ? "I" : i === n - 1 ? "F" : "M";
      const st = tok(d);
      add(SN, pos + "|" + (i ? tok(gs[i - 1]) : "^"), st, w);
      if (d.kind === "M") return;
      add(B0, pos, d.base, w);
      add(BS, d.base, pos + st, w);
      if (i === 0 && d.sign === "්") INIT_HAL[d.base] = (INIT_HAL[d.base] || 0) + w;
      if (i > 0 && gs[i - 1].kind !== "M") add(B, (gs[i - 1].sign === "්" ? "H" : "O") + "|" + gs[i - 1].base, d.base, w);
    });
    if (n >= 2 && n <= 7) {
      const key = gs.map(tok).join(" ");
      SK.set(key, (SK.get(key) || 0) + 1);
    }
  }

  const scale = (o, top) => {
    const out = {};
    for (const k of Object.keys(o).sort()) {
      const r = o[k], ents = Object.keys(r).map((b) => [b, Math.round(r[b] * 10)]).filter((e) => e[1] > 0);
      ents.sort((x, y) => y[1] - x[1] || (x[0] < y[0] ? -1 : 1));
      const kept = top ? ents.slice(0, top) : ents;
      if (kept.length) { out[k] = {}; kept.forEach(([b, n]) => { out[k][b] = n; }); }
    }
    return out;
  };
  const flat = (o) => Object.fromEntries(Object.entries(o).map(([k, v]) => [k, Math.round(v * 10)]));

  const skeletons = [...SK].filter((e) => e[1] >= 3).sort((a, b) => b[1] - a[1]).slice(0, 4000)
    .map(([k, n]) => [n, k.split(" ")]);
  return {
    wordsUsed: used,
    len: flat(LEN),
    skeletons,
    base: scale(B0),
    baseSign: scale(BS, 40),
    afterBase: scale(B, 60),
    signNext: scale(SN),
    initialHal: Object.fromEntries(Object.entries(flat(INIT_HAL)).filter((e) => e[1] > 0).sort((a, b) => b[1] - a[1])),
  };
}

module.exports = { MASK, WordTable, forEachToken, buildBigrams, buildModel, SPECIALS };

/*
 * select.js — choose which sentences to ship, and shard them.
 *
 * A sentence can only be shown for a font that has *all* its graphemes. So
 * graphemes are ranked by how many candidate sentences use them, and each
 * sentence is filed under its rarest grapheme. For a font with grapheme set S
 * the sentences it can use are in the shards whose rank range contains a
 * grapheme of S — the browser loads only those.
 *
 * To keep the shipped set small without starving small fonts, each rarest-
 * grapheme group keeps at most K sentences (K chosen to hit the target total),
 * so every grapheme keeps some sentences of its own.
 */
"use strict";

function hash(str, seed) {
  let h = (2166136261 ^ seed) >>> 0;
  for (let i = 0; i < str.length; i++) { h ^= str.charCodeAt(i); h = Math.imul(h, 16777619) >>> 0; }
  h ^= h >>> 15; h = Math.imul(h, 2246822519) >>> 0; h ^= h >>> 13;
  return h >>> 0;
}

/** cands: [{ text, tags }]. Adds .ids (distinct grapheme ids) and .rank (rarest grapheme rank). */
function rankGraphemes(cands, G) {
  const id = new Map(), names = [], df = [];
  for (const c of cands) {
    const seen = new Set();
    for (const s of G.segment(c.text)) {
      if (!s.sinhala) continue;
      let i = id.get(s.g);
      if (i === undefined) { i = names.length; id.set(s.g, i); names.push(s.g); df.push(0); }
      seen.add(i);
    }
    c.ids = [...seen];
    for (const i of seen) df[i]++;
  }
  const order = names.map((_, i) => i).sort((a, b) => df[b] - df[a] || (names[a] < names[b] ? -1 : 1));
  const rankOf = new Array(names.length);
  order.forEach((i, r) => { rankOf[i] = r; });
  for (const c of cands) {
    let m = 0;
    for (const i of c.ids) if (rankOf[i] > m) m = rankOf[i];
    c.rank = m;
    c.ids = null;
  }
  return { graphemes: order.map((i) => names[i]), df: order.map((i) => df[i]) };
}

/**
 * Pick ~target sentences. Sentences with a ZWNJ are always kept (up to forcedMax)
 * because there are few and they are the only way to test explicit non-joining.
 */
function selectSentences(cands, target, forcedMax, seed) {
  for (const c of cands) c.h = hash(c.text, seed);
  const forced = cands.filter((c) => c.tags.includes("n")).sort((a, b) => a.h - b.h).slice(0, forcedMax);
  const isForced = new Set(forced);
  const groups = new Map();
  for (const c of cands) {
    if (isForced.has(c)) continue;
    let g = groups.get(c.rank);
    if (!g) groups.set(c.rank, g = []);
    g.push(c);
  }
  for (const g of groups.values()) g.sort((a, b) => a.h - b.h);
  const want = Math.max(0, target - forced.length);
  const total = (K) => { let n = 0; for (const g of groups.values()) n += Math.min(g.length, K); return n; };
  let lo = 1, hi = Math.max(1, ...[...groups.values()].map((g) => g.length));
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (total(mid) >= want) hi = mid; else lo = mid + 1;
  }
  const K = lo;
  const kept = forced.slice();
  for (const g of groups.values()) kept.push(...g.slice(0, K));
  kept.sort((a, b) => a.rank - b.rank || a.h - b.h);
  return { kept, K, forced: forced.length };
}

/** Split kept sentences (sorted by rank) into shards of about `size`, never splitting a rank group. */
function shard(kept, size) {
  const shards = [];
  let cur = null;
  for (const c of kept) {
    if (!cur || (cur.items.length >= size && c.rank !== cur.hi)) {
      cur = { lo: c.rank, hi: c.rank, items: [] };
      shards.push(cur);
    }
    cur.hi = c.rank;
    cur.items.push(c);
  }
  return shards;
}

/** Sentences for template mode: ordinary running prose of moderate length, hash-ordered. */
function pickTemplates(cands, n, seed) {
  const ok = cands.filter((c) => !/[lh]/.test(c.tags) && c.text.length <= 130 &&
    (() => { const w = c.text.split(" ").length; return w >= 6 && w <= 16; })());
  ok.sort((a, b) => hash(a.text, seed + 1) - hash(b.text, seed + 1));
  return ok.slice(0, n);
}

module.exports = { hash, rankGraphemes, selectSentences, shard, pickTemplates };

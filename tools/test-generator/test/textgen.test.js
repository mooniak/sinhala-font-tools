/*
 * Tests for textgen.js against the built data bundle (test-texts/corpus-build).
 *   node --test tools/test-generator/test/
 */
"use strict";

const test = require("node:test");
const assert = require("node:assert");
const fs = require("fs");
const path = require("path");

const G = require("../graphemes.js");
const TG = require("../textgen.js");

const DATA = path.join(__dirname, "../data");
const have = fs.existsSync(path.join(DATA, "words.txt"));
const T = (name, fn) => test(name, { skip: !have && "data/ not built (run test-texts/corpus-build)" }, fn);

const TINY = TG.expand(["ට", "ස", "ප", "ඩ", "ඪ", "ච", "එ", "ය", "ව"], ["ි", "ු"]);
const SMALL = TG.expand(["ට", "ස", "ප", "ඩ", "ඪ", "ච", "එ", "ය", "ව", "ග", "ත", "න"], ["ි", "ු", "්", "ා", "ෙ", "ං"]);
let eng, LARGE;
const engine = async () => {
  if (!eng) {
    eng = await TG.load(TG.dirReader(DATA));
    LARGE = eng.index.graphemes.slice(0, 300);
  }
  return eng;
};

// every Sinhala grapheme of a rendered result is in the set
const inside = (result, set) => {
  const s = new Set(set);
  const bad = new Set();
  result.sentences.forEach((sent) => sent.forEach((p) => {
    if (p.w) G.segment(p.t).forEach((x) => { if (x.sinhala && !s.has(x.g)) bad.add(x.g); });
  }));
  return [...bad];
};
const invented = (r) => r.sentences.flatMap((s) => s.filter((p) => p.w && p.inv).map((p) => p.t));

T("hard rules flag what they should", async () => {
  const e = await engine();
  assert.deepStrictEqual(e.violations("කාමර"), []);
  assert.deepStrictEqual(e.violations("ස්වාමී"), []);          // ස් may open a word
  assert.ok(e.violations("කඅ").includes("H1"));                // independent vowel inside a word
  assert.ok(e.violations("කංං").includes("H2"));               // mark after a mark
  assert.ok(e.violations("ංක").includes("H2"));                // mark opening a word
  assert.ok(e.violations("ඩ්කා").includes("H3"));              // ඩ් does not open words
  assert.ok(e.violations("ක්ත්කා").includes("H4"));            // hal form after hal form
  assert.ok(e.violations("කකකක").includes("H5"));              // same grapheme three times
  assert.ok(e.violations("ක").includes("H6"));                 // one grapheme
});

T("real words in the corpus mostly satisfy the rules", async () => {
  const e = await engine();
  const top = e.words.slice(0, 5000).filter((w) => w.g.length >= 2);
  const bad = top.filter((w) => e.violations(w.w).length);
  assert.ok(bad.length / top.length < 0.02, `${bad.length}/${top.length} frequent words break a rule: ${bad.slice(0, 8).map((w) => w.w)}`);
});

for (const [name, set] of [["tiny", TINY], ["small", SMALL]]) {
  T(`chain (${name}): deterministic, inside the set, every grapheme shown`, async () => {
    const e = await engine();
    const a = e.session(set).chain({ seed: 7, words: 150 });
    const b = e.session(set).chain({ seed: 7, words: 150 });
    const c = e.session(set).chain({ seed: 8, words: 150 });
    assert.strictEqual(TG.render(a), TG.render(b));
    assert.notStrictEqual(TG.render(a), TG.render(c));
    assert.deepStrictEqual(inside(a, set), []);
    assert.deepStrictEqual(a.stats.missing, []);
    assert.ok(a.stats.words >= 150 && a.stats.words <= 175, "word count " + a.stats.words);
  });

  T(`invented words (${name}) obey the hard rules and are not real words`, async () => {
    const e = await engine();
    const r = e.session(set).chain({ seed: 2, words: 600, invent: { mode: "ratio", ratio: 1 }, cover: false });
    const inv = invented(r);
    assert.ok(inv.length > 500, "invented " + inv.length);
    inv.forEach((w) => {
      assert.deepStrictEqual(e.violations(w), [], w);
      assert.ok(!e.wordIndex.has(w), "real word flagged invented: " + w);
    });
    assert.deepStrictEqual(inside(r, set), []);
    assert.ok(new Set(inv).size > inv.length * 0.7, "invented words repeat too much");
  });
}

T("invention policy: ratio 0 invents nothing, auto stays under its cap", async () => {
  const e = await engine();
  const none = e.session(SMALL).chain({ seed: 1, words: 300, invent: { mode: "ratio", ratio: 0 }, cover: false });
  assert.strictEqual(none.stats.invented, 0);
  const auto = e.session(TINY).chain({ seed: 1, words: 400, invent: { mode: "auto", max: 0.2 }, cover: false });
  assert.ok(auto.stats.inventedPct <= 0.25, "auto share " + auto.stats.inventedPct);
  const half = e.session(SMALL).chain({ seed: 1, words: 400, invent: { mode: "ratio", ratio: 0.5 }, cover: false });
  assert.ok(Math.abs(half.stats.inventedPct - 0.5) < 0.12, "ratio 0.5 gave " + half.stats.inventedPct);
});

T("a large set is mostly real words", async () => {
  const e = await engine();
  const t0 = Date.now();
  const r = e.session(LARGE).chain({ seed: 1, words: 500 });
  assert.ok(Date.now() - t0 < 5000, "took " + (Date.now() - t0) + " ms");
  assert.ok(r.stats.inventedPct < 0.05, "invented " + r.stats.inventedPct);
  assert.deepStrictEqual(inside(r, LARGE), []);
});

T("real sentences: only needed shards load, all inside the set, tag filters work", async () => {
  const e = await engine();
  const top = e.index.graphemes.slice(0, 120);
  const s = e.session(top);
  const info = await s.loadSentences();
  assert.ok(info.shards < info.of, `loaded ${info.shards}/${info.of} shards`);
  assert.ok(info.sentences > 5000, "sentences for 120 graphemes: " + info.sentences);
  const r = s.sentences({ seed: 1, count: 40 });
  assert.strictEqual(r.sentences.length, 40);
  assert.deepStrictEqual(inside(r, top), []);
  assert.ok(!r.sentences.some((x) => /[A-Za-z]/.test(x.map((p) => p.t).join(""))), "Latin text got through the default filter");
  assert.strictEqual(TG.render(s.sentences({ seed: 3, count: 10 })), TG.render(s.sentences({ seed: 3, count: 10 })));
  // the cover option picks sentences that between them show as many graphemes as possible
  const covered = s.sentences({ seed: 1, count: 40, cover: true }).stats.shown;
  const plain = s.sentences({ seed: 1, count: 40, cover: false }).stats.shown;
  assert.ok(covered >= plain, `cover shows ${covered}, plain ${plain}`);
});

T("a font with rare letters but few common ones has no complete sentences, and says so", async () => {
  const e = await engine();
  const s = e.session(SMALL);
  const info = await s.loadSentences();
  assert.ok(info.shards < info.of);
  assert.strictEqual(info.sentences, 0);
  assert.deepStrictEqual(s.sentences({ count: 5 }).sentences, []);
});

T("targeted sentences contain the target", async () => {
  const e = await engine();
  const s = e.session(LARGE);
  await s.loadSentences();
  const rak = s.targeted({ classes: ["rakar"] }, { count: 15, minHits: 3 });
  assert.ok(rak.sentences.length > 0);
  rak.sentences.forEach((x) => assert.ok(x.map((p) => p.t).join("").includes("\u0DCA\u200D\u0DBB")));
  const one = LARGE.find((g) => g === "ඩ");
  const hit = s.targeted({ graphemes: [one] }, { count: 5 });
  hit.sentences.forEach((x) => assert.ok(G.segment(x.map((p) => p.t).join("")).some((y) => y.g === one)));
});

T("templates: inside the set, real sentence shape, invented words marked", async () => {
  const e = await engine();
  const s = e.session(SMALL);
  const r = await s.templates({ seed: 4, count: 10 });
  assert.strictEqual(r.sentences.length, 10);
  assert.deepStrictEqual(inside(r, SMALL), []);
  const inv = invented(r);
  assert.ok(inv.length > 0, "a small set should need invented words");
  inv.forEach((w) => assert.deepStrictEqual(e.violations(w), [], w));
  const kept = r.sentences.flatMap((x) => x.filter((p) => p.w && !p.inv)).length;
  assert.ok(kept > 0, "no real words kept");
  assert.ok(r.sentences.every((x) => /[.?!”"’)]$|[඀-෿]$|[0-9]$/.test(x.map((p) => p.t).join(""))), "sentences lost their ending");
  assert.strictEqual(TG.render(r), TG.render(await e.session(SMALL).templates({ seed: 4, count: 10 })));
});

T("no ZWNJ words unless asked", async () => {
  const e = await engine();
  const withoutZ = e.session(LARGE).chain({ seed: 1, words: 600 });
  assert.ok(!TG.render(withoutZ).includes("\u200C"));
});

T("pseudo: invented words, obeying the rules, built around under-used graphemes", async () => {
  const e = await engine();
  const s = e.session(SMALL);
  const r = s.pseudo({ seed: 5, count: 80 });
  assert.strictEqual(r.sentences.length, 80);
  assert.deepStrictEqual(inside(r, SMALL), []);
  assert.deepStrictEqual(r.stats.missing, []);
  r.sentences.forEach((x) => assert.deepStrictEqual(e.violations(x[0].t), [], x[0].t));
  const withG = s.pseudo({ seed: 5, count: 30, contains: ["ඪි"] });
  withG.sentences.forEach((x) => assert.ok(G.segment(x[0].t).some((y) => y.g === "ඪි"), x[0].t));
});

T("coverage is guaranteed even when graphemes outnumber the words asked for", async () => {
  const e = await engine();
  const base = ["ට", "ස", "ප", "ඩ", "ඪ", "ච", "එ", "ය", "ව", "ග", "ත", "න", "ක", "ද", "ර", "ල", "අ", "උ", "ආ", "ඇ", "ඈ"];
  const big = TG.expand(base, ["ි", "ු", "්", "ා", "ෙ", "ං", "ැ", "ෑ", "ේ", "ො", "ෝ", "ෛ"]);
  for (const seed of [1, 2, 3, 4]) {
    const s = e.session(big);
    const c = s.chain({ seed, words: 90 });
    const t = await s.templates({ seed, count: 8 });
    assert.deepStrictEqual(c.stats.missing, [], "chain, seed " + seed);
    assert.deepStrictEqual(t.stats.missing, [], "templates, seed " + seed);
    assert.deepStrictEqual(inside(c, big), []);
    assert.deepStrictEqual(inside(t, big), []);
  }
});

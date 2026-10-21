/* node --test tools/test-generator/test/extras.test.js */
"use strict";
const test = require("node:test");
const assert = require("node:assert");
const X = require("../extras.js");
const TG = require("../textgen.js");

const sent = (t) => [{ t, w: true, inv: false }, { t: ".", w: false, inv: false }];
const base = { sentences: [sent("අ"), sent("ආ"), sent("ඉ"), sent("ඊ")], mode: "templates" };

test("no kinds or zero rate leaves the result alone", () => {
  assert.strictEqual(X.apply(base, { kinds: [], seed: 1 }), base);
  assert.strictEqual(X.apply(base, { kinds: ["date"], rate: 0, seed: 1 }), base);
});

test("between adds one-piece sentences and keeps the originals", () => {
  const r = X.apply(base, { kinds: ["date"], rate: 1, place: "between", seed: 1 });
  assert.strictEqual(r.sentences.length, 8);
  assert.match(r.sentences[1][0].t, /^[\d\-\/.]+$/);
  assert.strictEqual(base.sentences.length, 4);
});

test("within inserts after a word", () => {
  const r = X.apply(base, { kinds: ["time"], rate: 1, place: "within", seed: 2 });
  assert.strictEqual(r.sentences.length, 4);
  r.sentences.forEach((s) => assert.strictEqual(s.length, 3));
  assert.strictEqual(r.sentences[0][0].t, "අ");
  assert.match(r.sentences[0][1].t, /^ \d/);
});

test("Sinhala digits, never letters", () => {
  const r = X.apply(base, { kinds: ["number", "date", "time"], script: "sinhala", rate: 1, seed: 3 });
  r.sentences.filter((s) => s.length === 1).forEach((s) => assert.doesNotMatch(s[0].t, /[0-9]/));
  assert.strictEqual(X.digits("2026", "sinhala"), "෨෦෨෬");
});

test("same seed, same result", () => {
  const o = { kinds: X.KINDS, rate: 0.7, seed: 9 };
  assert.deepStrictEqual(TG.render(X.apply(base, o)), TG.render(X.apply(base, o)));
});

test("pseudo word lists are left alone", () => {
  const p = { sentences: [[{ t: "අ", w: true }]], mode: "pseudo" };
  assert.strictEqual(X.apply(p, { kinds: ["number"], rate: 1, seed: 1 }), p);
});

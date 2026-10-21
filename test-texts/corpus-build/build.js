#!/usr/bin/env node
/*
 * corpus-build — turn the raw UCSC LTRL Sinhala corpora into the compact data
 * bundle that tools/test-generator loads. See README.md.
 *
 *   node test-texts/corpus-build/build.js [--corpus DIR] [--out DIR] [options]
 */
"use strict";

const fs = require("fs");
const path = require("path");
const zlib = require("zlib");

const G = require("../../tools/test-generator/graphemes.js");
const { loadSources } = require("./lib/load");
const { RUN, Stats, cleanLine, sentenceSplit, acceptSentence } = require("./lib/clean");
const { MASK, WordTable, buildBigrams, buildModel } = require("./lib/stats");
const { rankGraphemes, selectSentences, shard, pickTemplates } = require("./lib/select");

const REPO = path.resolve(__dirname, "..");
const opt = {
  corpus: path.join(REPO, "test-texts/sinhala-corpora-master"),
  out: path.join(REPO, "tools/test-generator/data"),
  sentences: 150000,     // target sentences shipped in shards
  shard: 5000,           // sentences per shard (approx.)
  templates: 20000,      // sentences in the template pool
  forcedMax: 2000,       // ZWNJ sentences always kept, up to this many
  wordsMin: 2,           // keep words seen this often in running text (or listed by a word-list source)
  vocabMin: 5,           // words at least this frequent take part in word pairs
  pairMin: 4,            // keep word pairs seen at least this often
  maxSucc: 60,           // successors kept per word
  modelMin: 3,           // words at least this frequent train the invention model
  seed: 1,
};
for (let i = 2; i < process.argv.length; i++) {
  const a = process.argv[i];
  if (a === "-h" || a === "--help") { console.log(fs.readFileSync(__filename, "utf8").split("*/")[0]); process.exit(0); }
  const m = /^--([a-zA-Z]+)$/.exec(a);
  if (!m || !(m[1] in opt)) { console.error("unknown option: " + a); process.exit(2); }
  const v = process.argv[++i];
  opt[m[1]] = typeof opt[m[1]] === "number" ? Number(v) : path.resolve(v);
}

const t0 = Date.now();
const log = (...a) => console.error(`[${((Date.now() - t0) / 1000).toFixed(1).padStart(5)}s]`, ...a);
const SRC_CHAR = { n1: "1", n2: "2", p: "p", e: "e", g: "g" };

// ---- read + clean -------------------------------------------------------

const st = new Stats();
const words = new WordTable();
const proseLines = [];                 // cleaned running text, for word pairs
const cands = new Map();               // text -> { text, tags }
const names = new Map();               // text -> kind
const reject = new Stats(), perSource = new Stats();
const notes = [];

log("reading", path.relative(REPO, opt.corpus));
for (const doc of loadSources(opt.corpus, (n) => notes.push(n))) {
  perSource.bump(doc.source + ":lines", doc.lines.length);
  for (const line of doc.lines) {
    if (!line.trim()) continue;
    const { text, bad } = cleanLine(line, st);
    st.bump("runs-rejected", bad);
    if (!text) continue;

    if (doc.kind === "list") {
      for (const run of text.match(RUN) || []) words.add(run, 0, MASK[doc.source] || 0);
    } else if (doc.kind === "names") {
      if (bad || !/[඀-෿]/.test(text) || /[A-Za-z0-9]/.test(text)) { reject.bump("names"); continue; }
      names.set(text, doc.source);
      for (const run of text.match(RUN) || []) words.add(run, 0, MASK[doc.source]);
    } else {
      for (const run of text.match(RUN) || []) words.add(run, 1, 0);
      proseLines.push(text);
      const sents = sentenceSplit(text);
      for (const s of sents) {
        const r = acceptSentence(s, sents.length === 1);
        if (r.reject) { reject.bump(r.reject); continue; }
        if (!cands.has(r.text)) {
          cands.set(r.text, { text: r.text, tags: (SRC_CHAR[doc.source] || "") + r.tags });
          perSource.bump(doc.source + ":sentences");
        } else reject.bump("duplicate");
      }
    }
  }
}
log(`${words.m.size} distinct words, ${cands.size} candidate sentences, ${names.size} names`);

// ---- words, pairs, model ------------------------------------------------

const rows = words.rows(opt.wordsMin);
let vocab = rows.findIndex((r) => r[1] < opt.vocabMin);
if (vocab < 0) vocab = rows.length;
const wordIndex = new Map();
for (let i = 0; i < vocab; i++) wordIndex.set(rows[i][0], i);

log(`word table: ${rows.length} rows, ${vocab} in the pair vocabulary`);
const bigrams = buildBigrams(proseLines, wordIndex, vocab, opt.pairMin, opt.maxSucc);
log(`word pairs: ${bigrams.pairs}`);
const model = buildModel(rows, G, opt.modelMin);
log(`model trained on ${model.wordsUsed} words, ${model.skeletons.length} skeletons`);

// ---- sentences ----------------------------------------------------------

const candList = [...cands.values()];
log("ranking graphemes over", candList.length, "sentences");
const ranking = rankGraphemes(candList, G);
const sel = selectSentences(candList, opt.sentences, opt.forcedMax, opt.seed);
const shards = shard(sel.kept, opt.shard);
const templates = pickTemplates(candList, opt.templates, opt.seed);
// For a font with only the N most-used graphemes: complete sentences it can show.
const coverage = {};
for (const n of [40, 60, 80, 100, 120, 160, 200, 300, 400]) {
  coverage[n] = {
    shipped: sel.kept.filter((c) => c.rank < n).length,
    available: candList.filter((c) => c.rank < n).length,
  };
}
log(`kept ${sel.kept.length} sentences (up to ${sel.K} per rarest grapheme, ${sel.forced} ZWNJ), ${shards.length} shards, ${templates.length} templates`);

// ---- write --------------------------------------------------------------

const out = opt.out;
fs.rmSync(path.join(out, "sentences"), { recursive: true, force: true });
fs.mkdirSync(path.join(out, "sentences"), { recursive: true });
const written = [];
function write(rel, content) {
  const p = path.join(out, rel);
  fs.writeFileSync(p, content);
  const buf = Buffer.from(content);
  written.push({ file: rel, bytes: buf.length, gzip: zlib.gzipSync(buf).length });
}
const lineOf = (c) => c.tags + "\t" + c.text;

write("words.txt", rows.map(([w, run, mask]) => w + "\t" + run + (mask ? "\t" + mask : "")).join("\n") + "\n");
write("bigrams.json", JSON.stringify({
  specials: bigrams.specials, vocab: bigrams.vocab,
  firstWord: rows[0][0], lastWord: rows[vocab - 1][0],
  next: bigrams.next,
}));
write("model.json", JSON.stringify(model));
write("templates.txt", templates.map(lineOf).join("\n") + "\n");
const nameRows = [...names].sort((a, b) => (a[1] < b[1] ? -1 : a[1] > b[1] ? 1 : a[0] < b[0] ? -1 : 1));
write("names.txt", nameRows.map(([t, k]) => k + "\t" + t).join("\n") + "\n");

const shardIndex = shards.map((s, i) => {
  const file = `sentences/s-${String(i).padStart(2, "0")}.txt`;
  write(file, s.items.map(lineOf).join("\n") + "\n");
  return { file: path.basename(file), lo: s.lo, hi: s.hi, n: s.items.length };
});
write("sentences/index.json", JSON.stringify({
  note: "graphemes are ordered most to least used; a shard holds sentences whose rarest grapheme has a rank in [lo, hi]",
  graphemes: ranking.graphemes, df: ranking.df, shards: shardIndex,
}));

const manifest = {
  generator: "test-texts/corpus-build",
  source: "UCSC LTRL Sinhala corpora (LGPL-LR) — see README.md",
  options: opt,
  maskBits: MASK,
  counts: {
    distinctWords: words.m.size, wordsShipped: rows.length, pairVocabulary: vocab, wordPairs: bigrams.pairs,
    candidateSentences: cands.size, sentencesShipped: sel.kept.length, perRarestGraphemeCap: sel.K,
    templates: templates.length, names: names.size, graphemes: ranking.graphemes.length,
  },
  coverageByTopGraphemes: coverage,
  cleaning: st.n,
  sentenceRejects: reject.n,
  perSource: perSource.n,
  files: written,
};
manifest.options.corpus = path.relative(REPO, opt.corpus);
manifest.options.out = path.relative(REPO, opt.out);
fs.writeFileSync(path.join(out, "manifest.json"), JSON.stringify(manifest, null, 1) + "\n");

// ---- report -------------------------------------------------------------

const kb = (n) => (n / 1024 >= 1024 ? (n / 1048576).toFixed(1) + " MB" : (n / 1024).toFixed(0) + " KB");
const sum = (f) => written.filter(f).reduce((a, w) => [a[0] + w.bytes, a[1] + w.gzip], [0, 0]);
console.log("\ncomplete sentences for a font with only the N most-used graphemes (shipped / in corpus):");
console.log("  " + Object.entries(coverage).map(([n, c]) => `${n}: ${c.shipped}/${c.available}`).join("   "));
console.log("cleaning:", JSON.stringify(st.n));
console.log("sentence rejects:", JSON.stringify(reject.n));
for (const w of written.filter((w) => !w.file.startsWith("sentences/s-"))) {
  console.log(`  ${w.file.padEnd(22)} ${kb(w.bytes).padStart(8)}  gzip ${kb(w.gzip).padStart(8)}`);
}
const sh = sum((w) => w.file.startsWith("sentences/s-"));
console.log(`  sentences/s-*.txt (${shards.length})`.padEnd(24), kb(sh[0]).padStart(8), " gzip", kb(sh[1]).padStart(8));
const all = sum(() => true);
console.log(`  total`.padEnd(24), kb(all[0]).padStart(8), " gzip", kb(all[1]).padStart(8));
if (notes.length) console.log("notes:", notes.join("; "));
log("done");

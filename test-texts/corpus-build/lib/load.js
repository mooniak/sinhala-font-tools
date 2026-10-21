/*
 * load.js — find and decode the UCSC LTRL corpora.
 *
 * The files are a mix of UTF-16 (LE and BE, with BOM) and UTF-8. Every source
 * is reduced to the same shape so the rest of the build does not care where
 * text came from:
 *
 *   { source, kind, lines }
 *     source  short id: n1 n2 (news V1/V2), p (parallel), e (NER), g (wordnet
 *             glosses), person / place / water / dict / func (word lists)
 *     kind    "prose" (running text), "names" (name phrases) or "list" (words)
 *     lines   array of strings
 */
"use strict";

const fs = require("fs");
const path = require("path");

function readText(file) {
  const b = fs.readFileSync(file);
  if (b[0] === 0xff && b[1] === 0xfe) return new TextDecoder("utf-16le").decode(b.subarray(2));
  if (b[0] === 0xfe && b[1] === 0xff) return new TextDecoder("utf-16be").decode(b.subarray(2));
  return new TextDecoder("utf-8").decode(b).replace(/^﻿/, "");
}

function walk(dir, out) {
  out = out || [];
  for (const name of fs.readdirSync(dir).sort()) {
    const p = path.join(dir, name);
    if (fs.statSync(p).isDirectory()) walk(p, out);
    else if (/\.txt$/i.test(name) && !/^readmes?\.txt$/i.test(name)) out.push(p);
  }
  return out;
}

const splitLines = (t) => t.split(/\r\n|\r|\n/);

// Join NER tokens back into a sentence: no space before closing punctuation.
function joinTokens(tokens) {
  let s = "";
  for (const t of tokens) {
    if (!s) s = t;
    else if (/^[.,;:!?)”’]$/.test(t)) s += t;
    else if (/[(“‘]$/.test(s)) s += t;
    else s += " " + t;
  }
  return s;
}

const NAME_KIND = [
  [/Personal|Artists/i, "person"],
  [/Rivers|Reservoirs/i, "water"],
  [/./, "place"],                       // cities, countries, mountains
];

/** Yield every source found under `root`. Missing folders are skipped with a note. */
function* loadSources(root, note) {
  const dir = (...p) => path.join(root, ...p);
  const have = (p) => fs.existsSync(p) || (note(`missing: ${path.relative(root, p)}`), false);

  const news = dir("sinhala-news-corpus");
  for (const [id, v] of [["n1", "V1"], ["n2", "V2"]]) {
    const d = path.join(news, `UCSC-Sinhala-News-Corpus-${v}`);
    if (!have(d)) continue;
    for (const f of walk(d)) {
      const t = readText(f).replace(/<HEADER>[\s\S]*?<\/HEADER>/gi, "").replace(/<[^>]+>/g, " ");
      yield { source: id, kind: "prose", lines: splitLines(t) };
    }
  }

  const para = dir("en-sin_parallel_corpus");
  if (have(para)) for (const f of walk(para)) yield { source: "p", kind: "prose", lines: splitLines(readText(f)) };

  const ner = dir("namedentity-tagged-corpus");
  if (have(ner)) {
    for (const f of walk(ner)) {
      const sents = [];
      let cur = [];
      for (const line of splitLines(readText(f))) {
        const tok = line.split("\t")[0].trim();
        if (tok) cur.push(tok);
        else if (cur.length) { sents.push(joinTokens(cur)); cur = []; }
      }
      if (cur.length) sents.push(joinTokens(cur));
      yield { source: "e", kind: "prose", lines: sents };
    }
  }

  const wn = dir("sinhala-wordnet_v1");
  if (have(wn)) {
    for (const f of walk(wn)) {
      const syn = [], gloss = [];
      splitLines(readText(f)).slice(1).forEach((l) => {
        const c = l.split("\t");
        if (c[0]) syn.push(c[0].replace(/;/g, " "));
        if (c[4]) gloss.push(c[4]);
      });
      yield { source: "dict", kind: "list", lines: syn };
      yield { source: "g", kind: "prose", lines: gloss };
    }
  }

  const names = dir("sinhala-proper-names");
  if (have(names)) {
    for (const f of walk(names)) {
      const kind = NAME_KIND.find(([re]) => re.test(path.basename(f)))[1];
      yield { source: kind, kind: "names", lines: splitLines(readText(f)) };
    }
  }

  const ingiya = dir("ingiya-english-sinhala-dictionary-database");
  if (have(ingiya)) {
    // words.txt in this folder is grep output ("en-si.txt:ධී"), not a word list.
    for (const n of ["si-en.txt", "en-si.txt"]) {
      const f = path.join(ingiya, n);
      if (have(f)) yield { source: "dict", kind: "list", lines: splitLines(readText(f)) };
    }
  }

  const func = dir("sinhala-functional-words");
  if (have(func)) for (const f of walk(func)) yield { source: "func", kind: "list", lines: splitLines(readText(f)) };
}

module.exports = { readText, walk, loadSources };

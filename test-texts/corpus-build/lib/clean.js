/*
 * clean.js — repair or reject the encoding quirks of the source text.
 *
 * Works on Sinhala runs (a maximal stretch of U+0D80–0DFF plus ZWJ/ZWNJ). A
 * run is repaired where the intent is unambiguous, or rejected as malformed;
 * everything outside Sinhala runs is left alone.
 *
 * Repairs:  ZWJ before al-lakuna (ZWJ ්) → al-lakuna ZWJ;  ZWJ that does not
 *           sit between ් and a consonant → dropped;  ZWNJ other than ් ZWNJ C
 *           → dropped.
 * Rejects:  starts with a sign, two signs in a row, sign after virama or after
 *           an independent vowel, unassigned code points.
 * Kept:     ් ZWNJ C (ස්‌ට) — it is deliberate, and a sentence carrying one is
 *           tagged so a test can include or exclude it.
 */
"use strict";

const AL = "්", ZWJ = "‍", ZWNJ = "‌";
const RUN = /[඀-෿‌‍]+/g;
const CONS = /[ක-ෆ]/;

// Assigned Sinhala code points.
const ASSIGNED = new Uint8Array(0x100);   // indexed by the low byte of a U+0D80–0DFF code point
[[0x82, 0x83], [0x85, 0x96], [0x9a, 0xb1], [0xb3, 0xbb], [0xbd, 0xbd], [0xc0, 0xc6], [0xca, 0xca],
 [0xcf, 0xd4], [0xd6, 0xd6], [0xd8, 0xdf], [0xf2, 0xf4]].forEach(([a, b]) => {
  for (let i = a; i <= b; i++) ASSIGNED[i] = 1;
});

const SIGN = "[ා-ෟෲෳ]";                // vowel signs (not virama)
const BAD = [
  ["starts-with-sign", /^[්-ෟෲෳං-ඃ]/],
  ["double-sign", new RegExp(`${SIGN}[්-ෟෲෳ]`)],
  ["hal-sign", new RegExp(`්${SIGN}`)],
  ["hal-hal", /්්/],
  ["sign-after-vowel", /[අ-ඖ][්-ෟෲෳ]/],
  ["sign-after-anusvara", /[ං-ඃ][්-ෟෲෳ]/],
];

class Stats {
  constructor() { this.n = Object.create(null); }
  bump(k, by) { this.n[k] = (this.n[k] || 0) + (by === undefined ? 1 : by); }
}

/** Clean one Sinhala run. Returns the string ("" if nothing is left) or null if malformed. */
function cleanRun(run, st) {
  let s = run.normalize("NFC");
  if (s.includes(ZWJ + AL)) { st.bump("fixed:zwj-before-hal"); s = s.split(ZWJ + AL).join(AL + ZWJ); }
  s = s.replace(/‍{2,}/g, ZWJ).replace(/‌{2,}/g, ZWNJ);
  if (s.includes(ZWJ)) {
    s = s.replace(/‍/g, (m, i, str) =>
      i > 0 && str[i - 1] === AL && CONS.test(str[i + 1] || "") ? m : (st.bump("fixed:zwj-dropped"), ""));
  }
  if (s.includes(ZWNJ)) {
    s = s.replace(/‌/g, (m, i, str) =>
      i > 0 && str[i - 1] === AL && CONS.test(str[i + 1] || "") ? m : (st.bump("fixed:zwnj-dropped"), ""));
  }
  for (let i = 0; i < s.length; i++) {
    const c = s.charCodeAt(i);
    if (c >= 0x0d80 && c <= 0x0dff && !ASSIGNED[c & 0xff]) { st.bump("bad:unassigned"); return null; }
  }
  for (const [name, re] of BAD) if (re.test(s)) { st.bump("bad:" + name); return null; }
  return s;
}

const MALFORMED = "￼";   // stands in for a rejected run inside a line

/** Clean every Sinhala run of a line. `bad` counts rejected runs (left as U+FFFC). */
function cleanLine(line, st) {
  let bad = 0;
  const text = line
    .replace(/[  -  \t]/g, " ")
    .replace(RUN, (run) => {
      const r = cleanRun(run, st);
      if (r === null) { bad++; return MALFORMED; }
      return r;
    })
    .replace(/ {2,}/g, " ")
    .trim();
  return { text, bad };
}

const SIN = /[඀-෿]/;
const SIN_G = /[඀-෿]/g;
const LATIN = /[A-Za-z]/g;
const ALLOWED = /^[඀-෿‌‍ A-Za-z0-9.,;:!?'"()\-–—…“”‘’\/%&+=@#$*\[\]•]+$/;
const TERMINAL = /[.?!][”’"')]?$/;

function sentenceSplit(text) {
  return text.split(/(?<=[.?!][”’"')]?)\s+/).filter(Boolean);
}

const count = (s, ch) => s.split(ch).length - 1;
// Brackets and quotes must pair up, or the sentence is a fragment of something longer.
function balanced(s) {
  return count(s, "(") === count(s, ")") && count(s, "[") === count(s, "]") &&
    count(s, "“") === count(s, "”") && count(s, "‘") === count(s, "’") &&
    count(s, '"') % 2 === 0 && count(s, "'") % 2 === 0;
}

/**
 * Decide whether a cleaned sentence is usable as a test sentence.
 * Returns { text, tags } or { reject: reason }. `whole` = the sentence is a
 * whole source line (a headline when it has no terminal punctuation).
 */
function acceptSentence(s, whole) {
  const len = s.length;
  if (s.includes(MALFORMED)) return { reject: "malformed-token" };
  if (len < 25) return { reject: "length" };
  if (!ALLOWED.test(s)) return { reject: "charset" };
  const sin = (s.match(SIN_G) || []).length;
  const lat = (s.match(LATIN) || []).length;
  if (sin / (sin + lat) < 0.6) return { reject: "not-sinhala" };
  const words = s.split(" ").filter((w) => SIN.test(w)).length;
  if (words < 4) return { reject: "few-words" };
  if (!/^["'“‘(]?[඀-෿0-9]/.test(s)) return { reject: "start" };
  if (/^\S{1,3}\.\s/.test(s)) return { reject: "initials-fragment" };
  if (!balanced(s)) return { reject: "unbalanced" };
  let tags = "";
  if (!TERMINAL.test(s)) {
    if (whole && words <= 14) tags += "h";
    else return { reject: "no-terminal" };
  }
  if (lat) tags += "l";
  if (/[0-9]/.test(s)) tags += "d";
  if (s.includes(ZWNJ)) tags += "n";
  return { text: s, tags };
}

module.exports = { RUN, MALFORMED, Stats, cleanRun, cleanLine, sentenceSplit, acceptSentence };

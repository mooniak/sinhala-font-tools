#!/usr/bin/env node
/*
 * generate-glyphnames.js
 * ======================
 * Generates every possible *composite* glyph name that a Sinhala designer might
 * add at their discretion, and writes them to a text file (one name per line).
 *
 * The glyphset standards enumerate only the required orthographic glyphs for
 * each level. But a designer is free to also draw, say, `kI-sinh` (කි). This
 * tool produces the full menu of such composites so none get missed.
 *
 * The output also opens with the atomic glyphs of the Sinhala Unicode block
 * (U+0D80–U+0DFF) — independent vowels, consonants, standalone vowel/modifier
 * signs, the special signs (rakaransaya/repaya/yansaya), punctuation and the
 * Sinhala lith numerals — so the list is a complete glyph inventory.
 *
 * Data flow (nothing is duplicated):
 *   sinhala-definitions.js  ->  the base inventory (consonants, ligated
 *                               conjuncts, touching clusters, rakar exceptions)
 *   lankaglyphset-map.js    ->  unicodeToName(): the authoritative name engine
 *
 * The tool builds a Unicode string for each base + sign combination and asks
 * the name engine what it is called. Touching clusters are the one case the
 * engine cannot name directly (their ZWJ-before-virama encoding is not an
 * orthographic cluster), so they are named via their ligated-conjunct
 * equivalent with a `.touch` dot-suffix (see README section 7).
 *
 * Signs applied (per the naming standard, README sections 4 & 5):
 *   virama ්  signI ි  signII ී  signU ු  signUu ූ  rakar ්‍ර
 *   rakar also combines: rakar+virama (kR), rakar+signI (kRI),
 *   rakar+signII (kRIi). rakar+signU/Uu are contextual signs
 *   (usign.rasign / uusign.rasign), not per-base glyphs, so they are omitted.
 *
 * Usage:
 *   node generate-glyphnames.js [-o out.txt] [--grouped] [--no-bare]
 *     -o, --output <file>   output path (default: ./glyphnames.txt)
 *     --grouped             add `# section` comment headers between groups
 *     --no-bare             omit the plain base glyph names (ka-sinh, kSsa-sinh)
 *     --no-block            omit the Unicode-block atomic glyphs (composites only)
 *     --attested-rakar      only generate rakar forms not in rakaransayaExceptions
 */

"use strict";

const fs = require("fs");
const path = require("path");

const defs = require("./sinhala-definitions.js");
const LGS = require("../glyphname-unicode-converter/lankaglyphset-map.js");

// --- Unicode building blocks ------------------------------------------------
const AL = "්"; // al-lakuna / virama  ්
const ZWJ = "‍"; // zero-width joiner
const RA = "ර"; // ර
const RAKAR = AL + ZWJ + RA; // ්‍ර  rakaransaya (post-base ra)

// Vowel signs + virama applied to every base. `seq` is the Unicode to append.
const SIGNS = [
  { key: "virama", seq: AL },
  { key: "signI", seq: "ි" }, // ි
  { key: "signII", seq: "ී" }, // ී
  { key: "signU", seq: "ු" }, // ු
  { key: "signUu", seq: "ූ" }, // ූ
];

// Rakar and the rakar+sign combinations (README section 5). signU/signUu after
// rakar are contextual signs, not per-base glyphs, so they are not listed here.
const RAKAR_SIGNS = [
  { key: "rakar", seq: RAKAR }, // kRa
  { key: "rakar+virama", seq: RAKAR + AL }, // kR
  { key: "rakar+signI", seq: RAKAR + "ි" }, // kRI
  { key: "rakar+signII", seq: RAKAR + "ී" }, // kRIi
];

// Assigned Sinhala-block code points the name engine does not resolve on its
// own. Stable Unicode assignments; the stems match the canonical glyphset.
const EXTRA_BLOCK = {
  0x0d81: "candrabindu",
  0x0de6: "lithzero", 0x0de7: "lithone", 0x0de8: "lithtwo", 0x0de9: "liththree",
  0x0dea: "lithfour", 0x0deb: "lithfive", 0x0dec: "lithsix", 0x0ded: "lithseven",
  0x0dee: "litheight", 0x0def: "lithnine",
};

// Special signs that are multi-codepoint sequences rather than single block
// characters, plus the contextual U/Uu-after-rakar signs. All canonical.
const SPECIAL_SIGNS = ["rasign", "repha", "yasign", "usign.rasign", "uusign.rasign"];

// --- Name resolution --------------------------------------------------------

// Name a Unicode string via the authoritative engine. Returns the glyph name or
// null if the engine cannot resolve it (recorded as an unresolved diagnostic).
function nameOf(seq) {
  const r = LGS.unicodeToName(seq);
  return r && r.name ? r.name : null;
}

// Turn a bare stem into its final glyph name using the canonical glyphset: some
// glyphs carry no namespace (kunddaliya), most take `-sinh`. Mirrors the name
// engine's own finalize rule so fallback names stay consistent.
function finalizeStem(stem) {
  const G = LGS.GLYPHSET || {};
  if (G[stem + "-sinh"]) return stem + "-sinh";
  if (G[stem]) return stem; // e.g. kunddaliya (Punctuation, no namespace)
  return stem + "-sinh";
}

// Touching clusters (c1 + ZWJ + ් + c2) are not orthographic clusters the engine
// can parse. They are named like the equivalent ligated conjunct (c1 + ් + ZWJ +
// c2) with a `.touch` dot-suffix inserted before the namespace.
function touchName(c1, c2, signSeq) {
  const ligated = c1 + AL + ZWJ + c2 + (signSeq || "");
  const base = nameOf(ligated);
  if (!base) return null;
  return base.includes("-")
    ? base.replace(/-(sinh|taml)$/, ".touch-$1")
    : base + ".touch";
}

// --- Unicode-block atomic glyphs --------------------------------------------

// Which block group a code point belongs to (used for the grouped output).
function blockGroupOf(cp) {
  if (cp >= 0x0d85 && cp <= 0x0d96) return "vowels"; // independent vowels
  if (cp >= 0x0d9a && cp <= 0x0dc6) return "block-consonants"; // consonants
  if (cp >= 0x0de6 && cp <= 0x0def) return "punctuation-numerals"; // lith digits
  if (cp === 0x0df4) return "punctuation-numerals"; // kunddaliya
  return "signs"; // candrabindu, anusvaraya, visargaya, virama, vowel signs
}

const BLOCK_ORDER = ["vowels", "block-consonants", "signs", "special-signs", "punctuation-numerals"];

// Enumerate the whole Sinhala Unicode block (U+0D80–U+0DFF) plus the special
// multi-codepoint signs, emitting one atomic glyph name per assigned character.
function generateBlock(emit) {
  const buckets = {};
  for (const g of BLOCK_ORDER) buckets[g] = [];

  for (let cp = 0x0d80; cp <= 0x0dff; cp++) {
    const ch = String.fromCodePoint(cp);
    let name = nameOf(ch);
    if (!name && EXTRA_BLOCK[cp]) name = finalizeStem(EXTRA_BLOCK[cp]);
    if (!name) continue; // unassigned / unnameable code point
    buckets[blockGroupOf(cp)].push([name, ch]);
  }
  for (const stem of SPECIAL_SIGNS) buckets["special-signs"].push([finalizeStem(stem), null]);

  for (const g of BLOCK_ORDER) for (const [name, seq] of buckets[g]) emit(name, seq, g);
}

// --- Combination generation -------------------------------------------------

// Build [{ name, seq, group }] rows. Order: Unicode-block atomics, then
// bare base + vowel signs + rakar set for each base group.
function generate(opts) {
  const rows = [];
  const seen = new Set();
  const unresolved = [];

  function emit(name, seq, group) {
    if (!name) {
      unresolved.push({ seq, group });
      return;
    }
    if (seen.has(name)) return;
    seen.add(name);
    rows.push({ name, seq, group });
  }

  if (opts.block) generateBlock(emit);

  // By default rakar is generated for every base (the full "all possible" menu a
  // designer might draw). With --attested-rakar, only forms not in the chart's
  // rakaransayaExceptions are produced.
  const canRakar = opts.attestedRakar
    ? (uni) => !defs.rakaransayaExceptions.has(uni)
    : () => true;

  // 1. Consonants
  for (const c of defs.originalConsonants) {
    if (opts.bare) emit(nameOf(c), c, "consonants");
    for (const s of SIGNS) emit(nameOf(c + s.seq), c + s.seq, "consonants");
    if (canRakar(c)) {
      for (const rs of RAKAR_SIGNS) emit(nameOf(c + rs.seq), c + rs.seq, "consonant-rakar");
    }
  }

  // 2. Ligated conjuncts (kSsa, nDa, ...)
  for (const [c1, c2] of defs.conjunctPairs) {
    const conj = c1 + AL + ZWJ + c2;
    if (opts.bare) emit(nameOf(conj), conj, "conjuncts");
    for (const s of SIGNS) emit(nameOf(conj + s.seq), conj + s.seq, "conjuncts");
    if (canRakar(conj)) {
      for (const rs of RAKAR_SIGNS) emit(nameOf(conj + rs.seq), conj + rs.seq, "conjunct-rakar");
    }
  }

  // 3. Touching clusters (named via ligated equivalent + `.touch`).
  //    Vowel signs + virama only — rakar does not apply to touching clusters.
  for (const [c1, c2] of defs.touchingClusterPairs) {
    const seq = c1 + ZWJ + AL + c2;
    if (opts.bare) emit(touchName(c1, c2, ""), seq, "touching");
    for (const s of SIGNS) emit(touchName(c1, c2, s.seq), c1 + ZWJ + AL + c2 + s.seq, "touching");
  }

  return { rows, unresolved };
}

// --- Output -----------------------------------------------------------------

const GROUP_LABELS = {
  vowels: "Independent vowels",
  "block-consonants": "Consonants (base letters)",
  signs: "Vowel signs & modifier signs",
  "special-signs": "Special signs (rakaransaya, repaya, yansaya)",
  "punctuation-numerals": "Punctuation & Sinhala numerals",
  consonants: "Consonant + sign",
  "consonant-rakar": "Consonant + rakar",
  conjuncts: "Ligated conjunct + sign",
  "conjunct-rakar": "Ligated conjunct + rakar",
  touching: "Touching cluster + sign (.touch)",
};

function render(rows, grouped) {
  if (!grouped) return rows.map((r) => r.name).join("\n") + "\n";
  const lines = [];
  let current = null;
  for (const r of rows) {
    if (r.group !== current) {
      if (lines.length) lines.push("");
      lines.push("# " + (GROUP_LABELS[r.group] || r.group));
      current = r.group;
    }
    lines.push(r.name);
  }
  return lines.join("\n") + "\n";
}

// --- CLI --------------------------------------------------------------------

function parseArgs(argv) {
  const opts = { output: path.join(__dirname, "glyphnames.txt"), grouped: false, bare: true, block: true, attestedRakar: false };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "-o" || a === "--output") opts.output = argv[++i];
    else if (a === "--grouped") opts.grouped = true;
    else if (a === "--no-bare") opts.bare = false;
    else if (a === "--no-block") opts.block = false;
    else if (a === "--attested-rakar") opts.attestedRakar = true;
    else if (a === "-h" || a === "--help") {
      console.log(fs.readFileSync(__filename, "utf8").split("\n").slice(1, 40).join("\n").replace(/^\s?\*\/?/gm, ""));
      process.exit(0);
    }
  }
  return opts;
}

function main() {
  const opts = parseArgs(process.argv.slice(2));
  const { rows, unresolved } = generate(opts);
  const out = render(rows, opts.grouped);
  fs.writeFileSync(opts.output, out, "utf8");

  const counts = rows.reduce((m, r) => ((m[r.group] = (m[r.group] || 0) + 1), m), {});
  console.log(`Wrote ${rows.length} glyph names to ${path.relative(process.cwd(), opts.output)}`);
  for (const g of Object.keys(GROUP_LABELS)) {
    if (counts[g]) console.log(`  ${String(counts[g]).padStart(4)}  ${GROUP_LABELS[g]}`);
  }
  if (unresolved.length) {
    console.log(`\n${unresolved.length} sequence(s) could not be named:`);
    for (const u of unresolved.slice(0, 20)) console.log(`  [${u.group}] ${LGS.hex(u.seq)}`);
    if (unresolved.length > 20) console.log(`  ... and ${unresolved.length - 20} more`);
  }
}

if (require.main === module) main();

module.exports = { generate, nameOf, touchName };

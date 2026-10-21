#!/usr/bin/env node
/**
 * build.js — the Sinhala glyph catalogue the Sinhala Glyph Builder plugin
 * offers in its Add Glyphs dialog.
 *
 *   node tools/composite-map/glyph-catalogue/build.js          write the catalogue
 *   node tools/composite-map/glyph-catalogue/build.js --check  fail if it is stale
 *   node tools/composite-map/glyph-catalogue/build.js --list   print counts per group
 *
 * One entry per glyph a Sinhala font may contain, gathered from:
 *
 *   sinhala-design-dependencies.yaml  every stage glyph (letters, marks, form
 *                                     families, sweeps, conjunct systems)
 *   test-generator/data                every grapheme attested in the corpus
 *   sinhala-composites.yaml           composites, keep_drawn, review, sign
 *                                     variants and i-sign alternates
 *
 * Each entry says how the glyph can be made — `draw` (an outline glyph),
 * `composite` (components) or `features` (no precomposed glyph: GSUB/GPOS
 * shape it from its parts) — which one is recommended, and what it depends
 * on: its design parents from the model plus the parts it is made of. The
 * plugin refuses a glyph whose parents are not in the font.
 *
 * Output: tools/_generated/sinhala-glyph-catalogue.json (bundled into the
 * plugin by `python -m composite_map build-plugin`).
 */

'use strict';

const fs = require('fs');
const path = require('path');

const REPO = path.resolve(__dirname, '..', '..', '..');
const S = require(path.join(REPO, 'tools/glyphs-filters/sources.js'));
const CAT = require(path.join(REPO, 'tools/glyphs-filters/catalogue.js'));
const G = require(path.join(REPO, 'tools/test-generator/graphemes.js'));

const { model, composites: MAP, LGS } = S;
const OUT = path.join(REPO, 'tools/_generated/sinhala-glyph-catalogue.json');
const CORPUS_INDEX = path.join(REPO, 'tools/test-generator/data/sentences/index.json');

const AL = '්';
const ZWJ = '‍';
const REPHA = 'ර' + AL + ZWJ;
const RASIGN = AL + ZWJ + 'ර';
const YASIGN = AL + ZWJ + 'ය';
const PART_NAMES = { [RASIGN]: 'rasign-sinh', [YASIGN]: 'yasign-sinh', [REPHA]: 'repha-sinh' };

// How each vowel sign / virama is assembled around its base: [before], [after].
// The split vowels follow their Unicode decomposition (ේ = ෙ + ්, ො = ෙ + ා,
// ෝ = ෙ + ා්, ෞ = ෙ + ෟ), which is also how shaping engines split them.
const SIGN_LAYOUT = {
  'ා': [[], ['aasign-sinh']],
  'ැ': [[], ['aesign-sinh']],
  'ෑ': [[], ['aaesign-sinh']],
  'ි': [[], ['isign-sinh']],
  'ී': [[], ['iisign-sinh']],
  'ු': [[], ['usign-sinh']],
  'ූ': [[], ['uusign-sinh']],
  'ෘ': [[], ['vocalicrsign-sinh']],
  'ෲ': [[], ['vocalicrrsign-sinh']],
  'ෟ': [[], ['vocaliclsign-sinh']],
  'ෳ': [[], ['vocalicllsign-sinh']],
  '්': [[], ['virama-sinh']],
  'ෙ': [['esign-sinh'], []],
  'ේ': [['esign-sinh'], ['virama-sinh']],
  'ෛ': [['aisign-sinh'], []],
  'ො': [['esign-sinh'], ['aasign-sinh']],
  'ෝ': [['esign-sinh'], ['aasign_virama-sinh']],
  'ෞ': [['esign-sinh'], ['vocaliclsign-sinh']],
};
const PREBASE = new Set(['ෙ', 'ේ', 'ෛ', 'ො', 'ෝ', 'ෞ']);
// Signs that advance after (or before) the base rather than attach to it.
const SPACING = new Set(['ා', 'ැ', 'ෑ', 'ෘ', 'ෲ', 'ෟ', 'ෳ', ...PREBASE]);

const GROUPS = [
  ['consonants', 'Consonants'],
  ['vowels', 'Independent vowels'],
  ['signs', 'Signs & marks'],
  ['variants', 'Sign variants & alternates'],
  ['virama', '් forms'],
  ['ispilla', 'ි ී forms'],
  ['papilla', 'ු ූ forms'],
  ['spacing', 'ා ැ ෑ ෘ ෲ ෟ ෳ forms'],
  ['prebase', 'ෙ ේ ෛ ො ෝ ෞ forms'],
  ['rakar', 'Rakaransaya ්‍ර'],
  ['yansa', 'Yansaya ්‍ය'],
  ['repha', 'Repaya ර්‍'],
  ['ligature', 'Conjunct ligatures'],
  ['numerals', 'Numerals'],
  ['other', 'Other'],
  ['attested', 'Attested in the corpus'],
  ['map-composite', 'Composite map · composites'],
  ['map-keep', 'Composite map · keep drawn'],
  ['map-review', 'Composite map · review'],
];
const GROUP_ORDER = new Map(GROUPS.map(([id], i) => [id, i]));
const SIGN_GROUP = {
  '්': 'virama', 'ි': 'ispilla', 'ී': 'ispilla', 'ු': 'papilla', 'ූ': 'papilla',
};

// --------------------------------------------------------------------------
// Naming
// --------------------------------------------------------------------------

const nameCache = new Map();
const textOf = new Map();   // name -> grapheme text

/** LankaGlyphSets name for a grapheme (the converter's, plus the sign parts). */
function nameOf(text) {
  if (nameCache.has(text)) return nameCache.get(text);
  let name = PART_NAMES[text] || null;
  if (!name) {
    const r = LGS.unicodeToName(text);
    if (r && r.name) name = r.name;
  }
  nameCache.set(text, name);
  if (name && !textOf.has(name)) textOf.set(name, text);
  return name;
}

function textForName(name) {
  if (textOf.has(name)) return textOf.get(name);
  for (const [t, n] of Object.entries(PART_NAMES)) if (n === name) return t;
  const m = /^(.+)_repha-sinh$/.exec(name);
  if (m) {
    const base = textForName(m[1] + '-sinh');
    return base ? REPHA + base : null;
  }
  if (name === 'aasign_virama-sinh') return 'ා' + AL;
  const g = LGS.GLYPHSET[name];
  if (g && g.unicode && !g.unicode.includes(' ')) {
    return String.fromCodePoint(parseInt(g.unicode.slice(2), 16));
  }
  const r = LGS.nameToUnicode(name);
  return r && r.unicode ? r.unicode.normalize('NFC') : null;
}

/** usign-sinh.medium -> usign-sinh; names without a post-namespace suffix pass. */
const plain = name => name.replace(/(-sinh)\.[^.]+$/, '$1');

// --------------------------------------------------------------------------
// Entries
// --------------------------------------------------------------------------

const items = new Map();

function entry(name, text) {
  let it = items.get(name);
  if (!it) {
    it = {
      name, text: text || textForName(name) || null,
      groups: new Set(), stage: null, freq: 0,
      components: null, parts: null, requires: new Set(),
      modes: ['draw'], default: 'draw', seed: null, notes: [],
    };
    items.set(name, it);
  } else if (!it.text && text) {
    it.text = text;
  }
  return it;
}

function setStage(it, n) {
  if (n == null || !isFinite(n)) return;
  if (it.stage == null || n < it.stage) it.stage = n;
}

function addText(text) {
  const name = nameOf(text);
  if (!name) return null;
  return entry(name, text);
}

const charsToNames = chars => chars.map(nameOf).filter(Boolean);

// 1. The model: every stage glyph, with its design parents.
const familyOf = new Map();   // form text -> family id
for (const [id, e] of Object.entries(model.glyphs)) {
  if (e.type !== 'form-family') continue;
  for (const form of S.formGlyphs(id)) {
    familyOf.set(form, id);
    if (e.mark === 'ි') familyOf.set(form.replace(/ි$/, 'ී'), id);
    if (e.mark === 'ු') familyOf.set(form.replace(/ු$/, 'ූ'), id);
  }
}
const systemOf = new Map();   // conjunct form text -> conjunct-system id
for (const [id, forms] of Object.entries(CAT.conjunctFormsByEntry)) {
  for (const f of forms) systemOf.set(f, id);
}
const SYSTEM_SIGN = { rakaransaya: 'rasign-sinh', yansaya: 'yasign-sinh', repaya: 'repha-sinh' };

for (const [id, e] of Object.entries(model.glyphs)) {
  const parents = charsToNames(e.parents || []);
  if (e.codepoint) {
    const it = addText(id);
    if (it) {
      setStage(it, e.stage);
      parents.forEach(p => it.requires.add(p));
    }
  }
  if (SYSTEM_SIGN[id]) {
    const it = entry(SYSTEM_SIGN[id]);
    setStage(it, e.stage);
    parents.forEach(p => it.requires.add(p));
  }
  if (e.type === 'form-family') {
    for (const [n, forms] of CAT.familyFormsByStage(id)) {
      for (const f of forms) setStage(addText(f) || {}, n);
    }
  } else if (!e.codepoint) {
    for (const t of CAT.stageChars(id)) setStage(addText(t) || {}, e.stage);
  }
}
// design parents of family forms and conjunct-system members
for (const it of items.values()) {
  if (!it.text) continue;
  const fam = familyOf.get(it.text);
  if (fam) charsToNames(model.glyphs[fam].parents || []).forEach(p => it.requires.add(p));
  const sys = systemOf.get(it.text);
  if (sys) charsToNames(model.glyphs[sys].parents || []).forEach(p => it.requires.add(p));
}

// 2. The corpus: every attested grapheme, with its document frequency.
const corpus = JSON.parse(fs.readFileSync(CORPUS_INDEX, 'utf8'));
corpus.graphemes.forEach((g, i) => {
  const it = addText(g);
  if (!it) return;
  it.freq = Math.max(it.freq, corpus.df[i] || 0);
  it.groups.add('attested');
});

// 3. The composite map.
const keep = MAP.keep_drawn || {};
const review = MAP.review || {};
const comps = MAP.composites || {};
for (const name of [...Object.keys(comps), ...Object.keys(keep), ...Object.keys(review)]) {
  entry(name);
}
const atoms = MAP.atoms || {};
for (const name of [...(atoms.base_letters || []), ...(atoms.signs || [])]) entry(name);
const variants = { ...(atoms.sign_variants || {}) };
for (const alt of atoms.ispilla_alternates || []) {
  if (alt.includes('.')) variants[alt] = { sign: plain(alt), slot: alt.split('.').pop() };
}
for (const [name, v] of Object.entries(variants)) {
  const it = entry(name, textForName(v.sign));
  it.seed = v.sign;
  it.requires.add(v.sign);
  it.groups.add('variants');
  it.notes.push(`${v.slot} variant of ${v.sign}; seeded from it, then redesigned`);
}

// --------------------------------------------------------------------------
// Decomposition, modes, groups
// --------------------------------------------------------------------------

/** -> { components, groups, spacing, ligature } for a grapheme text. */
function decompose(text) {
  const out = { components: null, groups: [], spacing: false, ligature: false, yansa: false };
  const seg = G.segment(text);
  if (seg.length !== 1 || !seg[0].sinhala) return out;
  const parts = seg[0].parts;
  if (parts.length < 2) {
    if (text.includes(ZWJ)) { out.ligature = true; out.groups.push('ligature'); }
    return out;
  }
  const d = G.decompose(text);
  const base = d.base;
  // conjunct type of the base
  if (base.includes(RASIGN)) out.groups.push('rakar');
  if (base.includes(YASIGN)) { out.groups.push('yansa'); out.yansa = true; }
  if (base.startsWith(REPHA)) out.groups.push('repha');
  const baseParts = G.segment(base)[0].parts;
  if (baseParts.some(p => p.includes(ZWJ) && !PART_NAMES[p])) {
    out.groups.push('ligature');
    out.ligature = true;
  }

  let components;
  if (!d.sign) {
    // a bare conjunct: base piece + rakaransaya / yansaya / repaya
    if (baseParts.length < 2) return out;
    const head = baseParts.filter(p => p && !PART_NAMES[p]);
    const signs = baseParts.filter(p => PART_NAMES[p]);
    if (head.length !== 1) return out;
    components = [nameOf(head[0]), ...signs.map(p => PART_NAMES[p])];
  } else {
    const baseName = nameOf(base);
    const pre = [], post = [];
    for (const s of [...d.sign]) {
      const layout = SIGN_LAYOUT[s];
      if (!layout) return out;
      pre.push(...layout[0]);
      post.push(...layout[1]);
      if (SPACING.has(s)) out.spacing = true;
      const grp = SIGN_GROUP[s] || (PREBASE.has(s) ? 'prebase' : 'spacing');
      if (!out.groups.includes(grp)) out.groups.push(grp);
    }
    components = [...pre, baseName, ...post];
  }
  if (components.every(Boolean)) out.components = components;
  return out;
}

const NUMERAL = /^(lith|archaic)/;
const consonantNames = new Set(charsToNames(S.consonants()));

/** Components, parts, modes, recommendation and groups of one entry. */
function describe(it) {
  if (NUMERAL.test(it.name)) it.groups.add('numerals');
  if (it.seed) return;
  const d = it.text ? decompose(it.text) : { components: null, groups: [] };
  d.groups.forEach(g => it.groups.add(g));
  const mapped = comps[it.name];
  const guess = review[it.name] && review[it.name].guess;
  it.components = (mapped && mapped.components) || guess || d.components;
  it.parts = it.components ? it.components.map(plain) : null;
  if (d.ligature) {
    // a ligature is designed from its letters
    for (const ch of it.text) {
      if (consonantNames.has(nameOf(ch))) it.requires.add(nameOf(ch));
    }
  }
  if (it.components) it.modes = ['draw', 'composite', 'features'];
  else if (d.ligature) it.modes = ['draw', 'features'];

  if (mapped) {
    it.default = 'composite';
    it.groups.add('map-composite');
    it.notes.push(`composite map: tier ${mapped.tier} (${mapped.source})`);
  } else if (keep[it.name]) {
    it.groups.add('map-keep');
    it.notes.push(`composite map: keep drawn — ${keep[it.name]}`);
  } else if (review[it.name]) {
    it.groups.add('map-review');
    it.notes.push('composite map: review — the composite is a guess, confirm it');
  } else if (it.components && (d.spacing || d.yansa)) {
    it.default = 'features';
    it.notes.push('the sign sits beside the base: shaping places it, no precomposed glyph needed');
  } else if (d.ligature && !it.components) {
    it.notes.push('conjunct ligature; features alone set it as the plain sequence');
  } else if (it.components) {
    it.default = 'composite';
  }

  // type group for atoms and anything still ungrouped
  const typed = [...it.groups].some(g => !g.startsWith('map-') && g !== 'attested');
  if (typed) return;
  const cp = it.text && it.text.codePointAt(0);
  if (consonantNames.has(it.name) || (atoms.base_letters || []).includes(it.name)) it.groups.add('consonants');
  else if (cp >= 0x0d85 && cp <= 0x0d96 && [...it.text].length === 1) it.groups.add('vowels');
  else if (/sign|virama|anusvaraya|visargaya|repha|kunddaliya|candrabindu/.test(it.name)) it.groups.add('signs');
  else it.groups.add('other');
}

// Describe every entry, closing over dependencies: each part and parent is
// itself an entry (and may bring parts of its own).
const described = new Set();
let pending = [...items.values()];
while (pending.length) {
  pending.forEach(it => { describe(it); described.add(it.name); });
  for (const it of pending) {
    for (const dep of [...(it.parts || []), ...(it.components || []), ...it.requires]) entry(dep);
  }
  pending = [...items.values()].filter(it => !described.has(it.name));
}
for (const it of items.values()) it.requires.delete(it.name);

// Stage of an unscheduled glyph: the stage all of its dependencies exist by.
const visiting = new Set();
function derivedStage(it) {
  if (it.stage != null) return it.stage;
  if (visiting.has(it.name)) return null;
  visiting.add(it.name);
  const deps = new Set([...(it.parts || []), ...it.requires]);
  let st = deps.size ? -Infinity : null;
  for (const dep of deps) {
    const s = derivedStage(items.get(dep));
    if (s == null) { st = null; break; }
    st = Math.max(st, s);
  }
  visiting.delete(it.name);
  if (st != null) it.stage = st;
  return st;
}
items.forEach(derivedStage);

// --------------------------------------------------------------------------
// Output
// --------------------------------------------------------------------------

function sortKey(it) {
  const g = Math.min(...[...it.groups].map(x => GROUP_ORDER.get(x) ?? 99));
  return [it.stage == null ? 99 : it.stage, g, -it.freq, it.name];
}
function compare(a, b) {
  const ka = sortKey(a), kb = sortKey(b);
  for (let i = 0; i < ka.length; i++) {
    if (ka[i] < kb[i]) return -1;
    if (ka[i] > kb[i]) return 1;
  }
  return 0;
}

const list = [...items.values()].sort(compare).map(it => {
  const o = { name: it.name, text: it.text, groups: [...it.groups].sort((a, b) => GROUP_ORDER.get(a) - GROUP_ORDER.get(b)) };
  if (it.stage != null) o.stage = it.stage;
  if (it.freq) o.freq = it.freq;
  o.modes = it.modes;
  o.default = it.default;
  if (it.components) o.components = it.components;
  if (it.parts && it.parts.join() !== (it.components || []).join()) o.parts = it.parts;
  if (it.requires.size) o.requires = [...it.requires].sort();
  if (it.seed) o.seed = it.seed;
  if (it.notes.length) o.note = it.notes.join('; ');
  return o;
});

const usedGroups = new Set(list.flatMap(it => it.groups));
const catalogue = {
  generated_by: 'tools/composite-map/glyph-catalogue/build.js',
  model_version: model.meta && model.meta.version,
  sources: [
    'sinhala-design-stages/sinhala-design-dependencies.yaml',
    'sinhala-composites.yaml',
    'tools/test-generator/data/sentences/index.json',
    'tools/glyphname-unicode-converter/lankaglyphset-map.js',
  ],
  stages: model.stages.map(s => ({ n: s.n, name: s.name })),
  groups: GROUPS.filter(([id]) => usedGroups.has(id)).map(([id, title]) => ({ id, title })),
  items: list,
};

const text = JSON.stringify(catalogue, null, 1) + '\n';
const args = process.argv.slice(2);

if (args.includes('--list')) {
  for (const { id, title } of catalogue.groups) {
    console.log(`${String(list.filter(it => it.groups.includes(id)).length).padStart(5)}  ${title}`);
  }
  const byMode = {};
  list.forEach(it => { byMode[it.default] = (byMode[it.default] || 0) + 1; });
  console.log(`${String(list.length).padStart(5)}  total — recommended: ${JSON.stringify(byMode)}`);
  console.log(`${String(list.filter(it => !it.text).length).padStart(5)}  without a grapheme`);
  console.log(`${String(list.filter(it => it.stage == null).length).padStart(5)}  without a stage`);
} else if (args.includes('--check')) {
  const current = fs.existsSync(OUT) ? fs.readFileSync(OUT, 'utf8') : '';
  if (current !== text) {
    console.error(`stale: ${path.relative(REPO, OUT)} — run node ${path.relative(REPO, __filename)}`);
    process.exit(1);
  }
  console.log(`${path.relative(REPO, OUT)} is up to date (${list.length} glyphs)`);
} else {
  fs.writeFileSync(OUT, text);
  console.log(`wrote ${path.relative(REPO, OUT)} (${list.length} glyphs)`);
}

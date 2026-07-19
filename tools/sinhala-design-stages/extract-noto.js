#!/usr/bin/env node
/**
 * extract-noto.js — mine the Noto Sans Sinhala Glyphs package
 * (docs/NotoSansSinhala.glyphspackage) for its OpenType classes and
 * substitution behaviour, and write docs/sinhala.min.yaml:
 * a provenance-tagged reference of how a highly optimised production
 * Sinhala font actually groups bases per mark form.
 *
 * Also prints a comparison against sinhala-design-dependencies.yaml so
 * completing our taxonomy becomes a mechanical diff, not guesswork.
 *
 *   node extract-noto.js
 */

'use strict';

const fs = require('fs');
const path = require('path');
const yaml = require('js-yaml');

const HERE = __dirname;
const PLIST = path.join(HERE, 'docs', 'NotoSansSinhala.glyphspackage', 'fontinfo.plist');
const OUT = path.join(HERE, 'docs', 'sinhala.min.yaml');
const MODEL = path.join(HERE, 'sinhala-design-dependencies.yaml');

const src = fs.readFileSync(PLIST, 'utf8');

// ---------------------------------------------------------------------------
// Glyphs-style name -> Sinhala character map (bases, vowels, signs).
// Conjunct names (kSsa, nDa, dRa, …) are decoded from the font's own
// substitution rules further down — never guessed.
// ---------------------------------------------------------------------------
const NAME2CHAR = {
  a: 'අ', aa: 'ආ', ae: 'ඇ', aae: 'ඈ', i: 'ඉ', ii: 'ඊ', u: 'උ', uu: 'ඌ',
  vocalicr: 'ඍ', vocalicrr: 'ඎ', vocalicl: 'ඏ', vocalicll: 'ඐ',
  e: 'එ', ee: 'ඒ', ai: 'ඓ', o: 'ඔ', oo: 'ඕ', au: 'ඖ',
  ka: 'ක', kha: 'ඛ', ga: 'ග', gha: 'ඝ', nga: 'ඞ', nnga: 'ඟ',
  ca: 'ච', cha: 'ඡ', ja: 'ජ', jha: 'ඣ', nya: 'ඤ', jnya: 'ඥ', nyja: 'ඦ',
  tta: 'ට', ttha: 'ඨ', dda: 'ඩ', ddha: 'ඪ', nna: 'ණ', nndda: 'ඬ',
  ta: 'ත', tha: 'ථ', da: 'ද', dha: 'ධ', na: 'න', nda: 'ඳ',
  pa: 'ප', pha: 'ඵ', ba: 'බ', bha: 'භ', ma: 'ම', mba: 'ඹ',
  ya: 'ය', ra: 'ර', la: 'ල', va: 'ව', sha: 'ශ', ssa: 'ෂ', sa: 'ස',
  ha: 'හ', lla: 'ළ', fa: 'ෆ',
  anusvara: 'ං', visarga: 'ඃ', kunddaliya: '෴',
  aasign: 'ා', aesign: 'ැ', aaesign: 'ෑ', isign: 'ි', iisign: 'ී',
  usign: 'ු', uusign: 'ූ', vocalicrsign: 'ෘ', vocalicrrsign: 'ෲ',
  vocaliclsign: 'ෟ', vocalicllsign: 'ෳ',
  esign: 'ෙ', eesign: 'ේ', aisign: 'ෛ', osign: 'ො', oosign: 'ෝ', ausign: 'ෞ',
  virama: '්', rasign: '්‍ර', yasign: '්‍ය', repha: 'ර්‍', touch: '‍්(touch)',
};
const ZWJ = '‍';

const conjunctNames = new Map(); // e.g. nDa -> න්‍ද

function baseName(glyphName) {
  return glyphName.replace(/-sinh.*$/, '').replace(/\.\w+$/, '');
}
function toChar(glyphName) {
  const n = baseName(glyphName);
  if (NAME2CHAR[n]) {
    const suffix = glyphName.includes('.') ? glyphName.slice(glyphName.indexOf('.')) : '';
    return NAME2CHAR[n] + suffix;
  }
  if (conjunctNames.has(n)) return conjunctNames.get(n);
  return `«${glyphName}»`; // unresolved — kept visible on purpose
}

// ---------------------------------------------------------------------------
// Pull every `sub …;` statement out of the feature/lookup code blocks.
// Glyphs escapes newlines inside code strings as \012.
// ---------------------------------------------------------------------------
const code = src.replace(/\\012/g, '\n');
const subs = [...code.matchAll(/sub ([^;]+) by ([^;]+);/g)]
  .map(m => ({ from: m[1].trim().split(/\s+/), to: m[2].trim() }));

// Decode conjunct glyph names from their own composition rules:
//   sub A-sinh virama-sinh zerowidthjoiner B-sinh by AB-sinh;
for (const s of subs) {
  if (s.from.length === 4 && s.from[1].startsWith('virama') && s.from[2] === 'zerowidthjoiner') {
    const a = toChar(s.from[0]), b = toChar(s.from[3]);
    if (!a.includes('«') && !b.includes('«')) conjunctNames.set(baseName(s.to), `${a}්${ZWJ}${b}`);
  }
}
// Rakar forms: sub A-sinh rasign-sinh by ARa-sinh;  (A + ්‍ර)
for (const s of subs) {
  if (s.from.length === 2 && s.from[1].startsWith('rasign') && !s.from[0].startsWith('@')) {
    const a = toChar(s.from[0]);
    if (!a.includes('«')) conjunctNames.set(baseName(s.to), `${a}්${ZWJ}ර`);
  }
}

// ---------------------------------------------------------------------------
// Classes block: { code = "…"; name = X; }
// ---------------------------------------------------------------------------
const classes = {};
for (const m of code.matchAll(/\{\s*code = "([^"]*)";\s*name = (\w+);\s*\}/g)) {
  const members = [...new Set(m[1].trim().split(/\s+/).filter(Boolean))];
  classes[m[2]] = { glyph_names: members, chars: members.map(toChar) };
}

// ---------------------------------------------------------------------------
// Categorise substitutions into the systems we care about.
// ---------------------------------------------------------------------------
const systems = {
  virama_fused: [],       // base + ් -> single glyph  (rahena-type wrap)
  virama_alternates: {},  // class -> ්.altN            (contextual mark form)
  i_fused: [], ii_fused: [],
  i_alternates: {}, ii_alternates: {},
  u_fused: [], uu_fused: [],
  u_alternates: {},
  conjuncts: [],
  special: [],
};

for (const s of subs) {
  const [a, b] = s.from;
  const to = s.to;
  if (s.from.length === 2 && !a.startsWith('@')) {
    const host = toChar(a);
    if (b.startsWith('virama')) systems.virama_fused.push(host);
    else if (b.startsWith('iisign')) systems.ii_fused.push(host);
    else if (b.startsWith('isign')) systems.i_fused.push(host);
    else if (b.startsWith('uusign')) systems.uu_fused.push(host);
    else if (b.startsWith('usign')) systems.u_fused.push(host);
  }
  // contextual mark alternates: sub @CLASS mark' by mark.altN;  (also single-host contexts)
  if (s.from.length === 2 && b.endsWith("'")) {
    const mark = b.slice(0, -1);
    const ctx = a.startsWith('@')
      ? { class: a.slice(1), chars: (classes[a.slice(1)] || {}).chars || [] }
      : { host: toChar(a) };
    const bucket = mark.startsWith('virama') ? systems.virama_alternates
      : mark.startsWith('iisign') ? systems.ii_alternates
      : mark.startsWith('isign') ? systems.i_alternates
      : mark.startsWith('usign') || mark.startsWith('uusign') ? systems.u_alternates
      : null;
    if (bucket) (bucket[to] = bucket[to] || []).push(ctx);
    else systems.special.push(`${a} ${mark} -> ${to}`);
  }
  if (s.from.length === 4 && s.from[2] === 'zerowidthjoiner') {
    systems.conjuncts.push(`${toChar(a)} + ් + ZWJ + ${toChar(s.from[3])} -> ${toChar(to)}`);
  }
  // the රු -> ැ-shape reuse and friends
  if (s.from.length === 2 && a === 'ra-sinh' && b.endsWith("'")) {
    systems.special.push(`ර + ${toChar(b.slice(0, -1))} -> ${toChar(to)} (glyph reuse)`);
  }
}
for (const k of ['virama_fused', 'i_fused', 'ii_fused', 'u_fused', 'uu_fused']) {
  systems[k] = [...new Set(systems[k])].sort();
}
systems.conjuncts = [...new Set(systems.conjuncts)];
systems.special = [...new Set(systems.special)];

// ---------------------------------------------------------------------------
// Write the reference YAML
// ---------------------------------------------------------------------------
const out = {
  meta: {
    source: 'docs/NotoSansSinhala.glyphspackage (Copyright 2022 The Noto Project Authors, github.com/notofonts/sinhala)',
    extracted_by: 'extract-noto.js — regenerate with `node extract-noto.js`; never hand-edit',
    reading: [
      'Noto processes each mark through a THREE-tier system: default mark form,',
      'contextual alternate mark form (per class), or a fully fused ligature glyph.',
      'Fused sets correspond to what our model calls atomic form families;',
      'virama_fused is the rahena-type wrap set (bases with a top terminal),',
      'virama default is the kodiya (flag).',
    ].join(' '),
  },
  classes,
  systems,
};
fs.writeFileSync(OUT, yaml.dump(out, { lineWidth: 100, noRefs: true }));
console.log(`✓ wrote ${path.relative(process.cwd(), OUT)}`);

// ---------------------------------------------------------------------------
// Comparison against our model
// ---------------------------------------------------------------------------
const model = yaml.load(fs.readFileSync(MODEL, 'utf8'));
const fams = Object.entries(model.glyphs).filter(([, g]) => g.type === 'form-family');

console.log('\n=== Noto vs sinhala-design-dependencies.yaml ===');
const compare = (label, notoChars, mark) => {
  const noto = new Set(notoChars.filter(c => !c.includes('«') && !c.includes('්')));
  const oursAll = new Set(fams.filter(([, g]) => g.mark === mark).flatMap(([, g]) => g.hosts || []));
  const onlyNoto = [...noto].filter(c => !oursAll.has(c));
  const matchFam = fams.filter(([, g]) => g.mark === mark && (g.hosts || []).some(h => noto.has(h)))
    .map(([id]) => id).join(', ');
  console.log(`\n${label}: ${[...noto].join(' ')}`);
  if (matchFam) console.log(`  overlaps our: ${matchFam}`);
  if (onlyNoto.length) console.log(`  NOT in any of our ${mark} families: ${onlyNoto.join(' ')}`);
};
const altChars = infos => infos.flatMap(i => i.chars || (i.host ? [i.host] : []));
compare('virama FUSED (rahena wrap)', systems.virama_fused, '්');
for (const [alt, infos] of Object.entries(systems.virama_alternates)) compare(`virama alt ${alt}`, altChars(infos), '්');
compare('ි FUSED', systems.i_fused, 'ි');
for (const [alt, infos] of Object.entries(systems.i_alternates)) compare(`ි alt ${alt}`, altChars(infos), 'ි');
compare('ු FUSED', systems.u_fused, 'ු');
for (const [alt, infos] of Object.entries(systems.u_alternates)) compare(`ු alt ${alt}`, altChars(infos), 'ු');
console.log(`\nconjunct composition rules found: ${systems.conjuncts.length}`);
console.log(`special/reuse rules: ${systems.special.length} (see docs/sinhala.min.yaml)`);

/**
 * catalogue.js — the filter catalogue. Every filter is a derived set: a name,
 * the glyph names it covers, and the `path` that produced it. Nothing is
 * hand-listed; if a filter is empty, the model has a hole and build.js says so.
 *
 * Sections become top-level folders in the Glyphs sidebar (or one file each
 * under `--split`); a filter's `group` becomes a folder inside its section.
 */

'use strict';

const S = require('./sources');
const { model, spacing, composites, LANKA, SHAPING } = S;

const ZWJ = '‍';
const VIRAMA = '්';
const RA = 'ර';
const YA = 'ය';
const I_MARKS = ['ි', 'ී', 'ු', 'ූ', '්'];

const sections = [];
const section = (id, title, blurb) => {
  const s = { id, title, blurb, filters: [] };
  sections.push(s);
  // `group` opens a subfolder; every filter added after it lands inside.
  let current = null;
  return {
    group(name) { current = name; },
    add(name, chars, path) {
      s.filters.push({ name, glyphs: S.names(chars), path, group: current });
    },
    addNames(name, glyphNames, path) {
      s.filters.push({ name, glyphs: [...new Set(glyphNames)], path, group: current });
    },
  };
};

const entries = Object.entries(model.glyphs);

// ---------------------------------------------------------------------------
// Conjunct expansions — shared by the Stages and Conjuncts sections.
// ---------------------------------------------------------------------------
const cons = S.consonants();
const rakarHosts = cons.filter(c => !SHAPING.rakaransayaExceptions.has(c));
const repayaHosts = cons.filter(c => !SHAPING.repayaExceptions.has(c));
const yansayaHosts = cons.filter(c => !SHAPING.yansayaExceptions.has(c));

const rakarForms = rakarHosts.map(c => c + VIRAMA + ZWJ + RA);
const repayaForms = repayaHosts.map(c => RA + VIRAMA + ZWJ + c);
const yansayaForms = yansayaHosts.map(c => c + VIRAMA + ZWJ + YA);
const kshaForms = ['ක' + VIRAMA + ZWJ + 'ෂ'];
const classicForms = Object.entries(LANKA.conjunctMap || {})
  .flatMap(([a, bs]) => bs.map(b => a + VIRAMA + ZWJ + b));
const touchingForms = Object.entries(LANKA.touchingClusterMap || {})
  .flatMap(([a, bs]) => bs.map(b => a + VIRAMA + ZWJ + b));

const conjunctFormsByEntry = {
  rakaransaya: rakarForms,
  repaya: repayaForms,
  yansaya: yansayaForms,
  ksha: kshaForms,
  'classic-conjuncts': classicForms,
  'touching-clusters': touchingForms,
};

// Sweeps (the `process` entries in the model). Consonants only: vowel signs
// on an independent vowel are an error in the model, not a grid cell.
const halSweep = cons.map(c => c + VIRAMA);
const completionSweep = cons.flatMap(c => I_MARKS.map(m => c + m));
const spacingReps = [
  ...Object.values(spacing.classes.right).map(c => c.rep),
  ...Object.values(spacing.classes.left).map(c => c.rep),
];

/** Characters an entry contributes to a stage: its own, or its expansions. */
function stageChars(id) {
  const e = model.glyphs[id];
  if (e.type === 'conjunct-system') return conjunctFormsByEntry[id] || [];
  if (e.type === 'process') {
    if (id === 'hal-sweep') return halSweep;
    if (id === 'completion-sweep') return completionSweep;
    if (id === 'kerning-pass') return spacingReps;
  }
  return S.charsOf(id);
}

// ---------------------------------------------------------------------------
// 1. Stages — the design schedule, exact and cumulative.
// ---------------------------------------------------------------------------
{
  const sec = section('Stages', 'Stages',
    'The design schedule from sinhala-design-dependencies.yaml. The cumulative ' +
    'filters are the useful ones day to day: "everything that should exist by now".');
  const byStage = new Map();
  for (const [id, e] of entries) {
    if (!byStage.has(e.stage)) byStage.set(e.stage, []);
    byStage.get(e.stage).push(...stageChars(id));
  }
  const stageNums = [...byStage.keys()].sort((a, b) => a - b);
  sec.group('By stage');
  for (const n of stageNums) {
    const st = model.stages.find(s => s.n === n) || {};
    sec.add(`Stage ${n} — ${st.name || ''}`.trim(), byStage.get(n), 'glyphs[].stage');
  }
  sec.group('Cumulative — what should exist by now');
  let cum = [];
  for (const n of stageNums) {
    cum = cum.concat(byStage.get(n));
    sec.add(`Through Stage ${n}`, cum.slice(), 'glyphs[].stage (cumulative)');
  }
}

// ---------------------------------------------------------------------------
// 2. Structure — skeletons and structural elements.
// ---------------------------------------------------------------------------
{
  const sec = section('Structure', 'Structure',
    'Skeletons and structural elements: the families a change propagates through.');
  sec.group('Skeletons');
  for (const [id, def] of Object.entries(model.skeletons)) {
    const chars = entries.filter(([, e]) => e.skeleton === id).flatMap(([i]) => S.charsOf(i));
    sec.add(`Skeleton · ${def.name}`, chars, 'glyphs[].skeleton');
  }
  sec.group('Elements');
  for (const [id, def] of Object.entries(model.elements)) {
    const chars = entries.filter(([, e]) => (e.elements || []).includes(id))
      .flatMap(([i]) => S.charsOf(i));
    sec.add(`Element · ${def.name}`, chars, 'glyphs[].elements[]');
  }
}

// ---------------------------------------------------------------------------
// 3. Spacing — the classes from sinhala-spacing.yaml, plus the work sets.
// ---------------------------------------------------------------------------
{
  const sec = section('Spacing', 'Spacing',
    'Sidebearing classes. A class member inherits its rep via metrics keys, so ' +
    'the representatives filter is the only set that gets bespoke spacing.');
  for (const side of ['left', 'right']) {
    sec.group(side === 'left' ? 'Left classes' : 'Right classes');
    for (const [cls, def] of Object.entries(spacing.classes[side])) {
      const chars = [...def.members];
      for (const fam of Object.values(spacing.forms || {})) {
        for (const [glyph, sides] of Object.entries(fam.glyphs || {})) {
          if (sides[side] === cls) chars.push(glyph);
        }
      }
      sec.add(`${side === 'left' ? 'Left' : 'Right'} · ${cls}`, chars,
        `sinhala-spacing.yaml classes.${side}`);
    }
  }
  sec.group('Work sets');
  sec.add('Class representatives (bespoke spacing / kerning pass)', spacingReps,
    'sinhala-spacing.yaml classes.*.rep');
  sec.add('Fused forms (inherit their host)',
    Object.values(spacing.forms || {}).flatMap(f => Object.keys(f.glyphs || {})),
    'sinhala-spacing.yaml forms');
  sec.add('Nonspacing marks (never spaced)', spacing.nonspacing || [],
    'sinhala-spacing.yaml nonspacing');
  sec.add('FLAGGED — provisional spacing, needs the designer',
    Object.keys(spacing.flags || {}), 'sinhala-spacing.yaml flags');
  const unassigned = [...(spacing.unassigned?.left || []), ...(spacing.unassigned?.right || [])];
  if (unassigned.length) {
    sec.add('Unassigned (no spacing class yet)', unassigned, 'sinhala-spacing.yaml unassigned');
  }
}

// ---------------------------------------------------------------------------
// 4. Mark forms — one filter per form family, plus the roll-ups and sweeps.
// ---------------------------------------------------------------------------
{
  const sec = section('MarkForms', 'Mark forms',
    'Each form family is one design decision covering many combinations. The ' +
    'roll-ups gather every typographic form of a mark; the sweeps are the ' +
    'Stage 8 completion gates.');
  const families = entries.filter(([, e]) => e.type === 'form-family');
  const markLabel = { 'ි': 'ි ී families (ispilla)', 'ු': 'ු ූ forms (papilla)', '්': '් forms (halkirima)' };
  for (const mark of ['ි', 'ු', '්']) {
    sec.group(markLabel[mark] || `${mark} forms`);
    for (const [id, e] of families.filter(([, e]) => e.mark === mark)) {
      const label = e.display ? `${id} — ${e.display}` : id;
      sec.add(label, S.formGlyphs(id), 'glyphs[type=form-family]');
    }
  }
  sec.group('Roll-ups and sweeps');
  const byMark = new Map();
  for (const [id, e] of families) {
    if (!e.mark) continue;
    if (!byMark.has(e.mark)) byMark.set(e.mark, []);
    byMark.get(e.mark).push(...S.formGlyphs(id));
  }
  for (const [mark, chars] of byMark) {
    sec.add(`All ${mark} forms`, chars, 'form-family.mark');
  }
  sec.add('Sweep · every base + ් (hal-sweep)', halSweep, 'glyphs.hal-sweep');
  sec.add('Sweep · base × ි ී ු ූ ් grid (completion-sweep)', completionSweep,
    'glyphs.completion-sweep');
}

// ---------------------------------------------------------------------------
// 5. Composites — the build/keep-drawn decisions.
// ---------------------------------------------------------------------------
{
  const sec = section('Composites', 'Composites',
    'From sinhala-composites.yaml: what can be assembled from parts, what must ' +
    'stay drawn and why, and what is still awaiting a decision.');
  const tiers = new Map();
  const sources = new Map();
  for (const [glyph, def] of Object.entries(composites.composites || {})) {
    if (!tiers.has(def.tier)) tiers.set(def.tier, []);
    tiers.get(def.tier).push(glyph);
    if (!sources.has(def.source)) sources.set(def.source, []);
    sources.get(def.source).push(glyph);
  }
  sec.group('By tier');
  for (const tier of [...tiers.keys()].sort()) {
    sec.addNames(`Composite · tier ${tier}`, tiers.get(tier), 'composites[].tier');
  }
  sec.group('By source');
  for (const [src, list] of sources) {
    sec.addNames(`Source · ${src}`, list, 'composites[].source');
  }
  const reasons = new Map();
  for (const [glyph, reason] of Object.entries(composites.keep_drawn || {})) {
    if (!reasons.has(reason)) reasons.set(reason, []);
    reasons.get(reason).push(glyph);
  }
  sec.group('Keep drawn — why');
  for (const [reason, list] of [...reasons].sort((a, b) => b[1].length - a[1].length)) {
    sec.addNames(`Keep drawn · ${reason}`, list, 'keep_drawn');
  }
  sec.group(null);
  sec.addNames('REVIEW — composite guess needs confirming',
    Object.keys(composites.review || {}), 'review');
}

// ---------------------------------------------------------------------------
// 6. Conjuncts — the Stage 9 layer, including what must NOT be drawn.
// ---------------------------------------------------------------------------
{
  const sec = section('Conjuncts', 'Conjuncts',
    'Generated from the shaping exception lists, so the "excluded" filters are ' +
    'as authoritative as the "applies" ones.');
  sec.add('Rakaransaya ්‍ර — applies', rakarForms, 'shaping-exceptions.rakaransaya (inverse)');
  sec.add('Rakaransaya ්‍ර — EXCLUDED hosts', [...SHAPING.rakaransayaExceptions],
    'shaping-exceptions.rakaransaya');
  sec.add('Repaya ර්‍ — applies', repayaForms, 'shaping-exceptions.repaya (inverse)');
  sec.add('Repaya ර්‍ — EXCLUDED hosts', [...SHAPING.repayaExceptions],
    'shaping-exceptions.repaya');
  sec.add('Yansaya ්‍ය — applies', yansayaForms, 'shaping-exceptions.yansaya (inverse)');
  sec.add('Yansaya ්‍ය — EXCLUDED hosts', [...SHAPING.yansayaExceptions],
    'shaping-exceptions.yansaya');
  sec.add('ක්‍ෂ ligature', kshaForms, 'glyphs.ksha');
  sec.add('Classic conjuncts', classicForms, 'lanka-glyph-data.conjunctMap');
  sec.add('Touching clusters', touchingForms, 'lanka-glyph-data.touchingClusterMap');
}

// ---------------------------------------------------------------------------
// 7. Dependencies — what reopens when a decision changes.
// ---------------------------------------------------------------------------
{
  const sec = section('Dependencies', 'Dependencies',
    'The freeze/reopen rule made clickable: change one metric or one archetype ' +
    'and these are the glyphs that must be re-verified.');
  sec.group('Reopens if a metric changes');
  for (const [id, def] of Object.entries(model.metrics)) {
    const chars = new Set();
    for (const [gid, e] of entries) {
      if (!(e.requires || []).includes(id)) continue;
      stageChars(gid).forEach(c => chars.add(c));
      for (const d of S.descendants(gid)) stageChars(d).forEach(c => chars.add(c));
    }
    sec.add(`Reopens if ${id} changes — ${def.name}`, [...chars],
      'metrics + glyphs[].requires + parents closure');
  }
  const roots = new Set([
    ...Object.values(model.skeletons).map(s => s.introduced_by),
    ...Object.values(model.elements).map(e => e.introduced_by),
  ]);
  sec.group('Descendants of an archetype');
  for (const root of roots) {
    if (!model.glyphs[root]) continue;
    const chars = S.descendants(root).flatMap(stageChars);
    sec.add(`Descendants of ${root} (${S.name(root) || root})`, chars, 'glyphs[].parents closure');
  }
}

// ---------------------------------------------------------------------------
// 8. Inventory — level, frequency, density, type, coverage, open questions.
// ---------------------------------------------------------------------------
{
  const sec = section('Inventory', 'Inventory',
    'Shipping targets and qualitative tags, plus what the stage test texts ' +
    'actually exercise and where the model still has holes.');
  const group = (field, label, path) => {
    const m = new Map();
    for (const [id, e] of entries) {
      const v = e[field];
      if (!v) continue;
      if (!m.has(v)) m.set(v, []);
      m.get(v).push(...stageChars(id));
    }
    for (const [v, chars] of m) sec.add(`${label} · ${v}`, chars, path);
  };
  sec.group('Level (shipping target)');
  group('level', 'Level', 'glyphs[].level');
  sec.group('Frequency');
  group('frequency', 'Frequency', 'glyphs[].frequency');
  sec.group('Type');
  group('type', 'Type', 'glyphs[].type');
  sec.group('Density');

  for (const [level, chars] of Object.entries(model.density || {})) {
    sec.add(`Density · ${level}`, chars, 'density');
  }
  const classified = new Set(Object.values(model.density || {}).flat());
  sec.add('Density · UNCLASSIFIED bases (gap density-incomplete)',
    S.bases().filter(b => !classified.has(b)), 'density vs glyphs[type=base]');

  sec.group('Test-text coverage');
  const SINHALA = /[඀-෿]/;
  for (const st of model.stages) {
    const t = st.teststrings || {};
    const text = [...(t.drills || []), ...(t.words || []), ...(t.sentences || [])].join(' ');
    const chars = [...new Set([...text].filter(c => SINHALA.test(c)))];
    if (chars.length) {
      sec.add(`Exercised by Stage ${st.n} test texts`, chars, 'stages[].teststrings');
    }
  }
  sec.group(null);
  sec.add('OPEN — provisional spacing (gap rare-spacing-provisional)',
    Object.keys(spacing.flags || {}), 'sinhala-spacing.yaml flags');
}

module.exports = { sections };

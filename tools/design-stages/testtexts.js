/**
 * testtexts.js — the model index, the test-text schedule check and the
 * deterministic drill generator.
 *
 * Extracted from build.js so that more than one tool can ask "what text does
 * stage n exercise?" without running a build. glyphs-filters needs exactly
 * that: the graphemes a stage's test texts touch are filter members, because a
 * font may draw them atomically instead of composing them with features.
 *
 * Requiring this module has no side effects — it loads the YAML and indexes
 * it, nothing else. All *structural* validation stays in build.js.
 */

'use strict';

const fs = require('fs');
const path = require('path');
const yaml = require('js-yaml');

const SRC = path.join(__dirname, '..', '..', 'model', 'sinhala-design-dependencies.yaml');

const ZWJ = '‍';
const IGNORE = new Set([' ', '\n', '\t', '.', ',', '!', '?', ':', ';', '"', "'", '“', '”', '-', '–']);
const ATOMIC_MARKS = ['ි', 'ී', 'ු', 'ූ', '්'];
const BODY_MARKS = ['ා', 'ැ', 'ෑ', 'ෙ', 'ේ', 'ො', 'ෝ', 'ෛ', 'ෘ', 'ෲ', 'ෟ', 'ෳ', 'ෞ'];

const data = yaml.load(fs.readFileSync(SRC, 'utf8'));
const glyphs = data.glyphs;

// ---------------------------------------------------------------------------
// Index the model
// ---------------------------------------------------------------------------
const entries = Object.entries(glyphs).map(([id, g]) => ({ id, ...g }));
const byId = new Map(entries.map(e => [e.id, e]));
const seq = e => e.stage * 1000 + e.order; // schedule position
const ordered = [...entries].sort((a, b) => seq(a) - seq(b));

const stageNumbers = data.stages.map(s => s.n);
const stageByN = new Map(data.stages.map(s => [s.n, s]));

// mark-form family lookups
const iFamilies = entries.filter(e => e.type === 'form-family' && e.mark === 'ි');
const iHostToFamily = new Map();
for (const f of iFamilies) for (const h of f.hosts || []) iHostToFamily.set(h, f);
const raForms = byId.get('ra-forms');
// hosts with an irregular/special ු form (u-special, du-form, llu-form, …)
const uHostToFamily = new Map();
for (const f of entries.filter(e => e.type === 'form-family' && e.mark === 'ු')) {
  for (const h of f.hosts || []) uHostToFamily.set(h, f);
}
// hosts with a non-kodiya ් form (hal-rahena, hal-trap, hal-ja)
const halHostToFamily = new Map();
for (const f of entries.filter(e => e.type === 'form-family' && e.mark === '්')) {
  for (const h of f.hosts || []) halHostToFamily.set(h, f);
}
const minConjunctStage = Math.min(...entries.filter(e => e.type === 'conjunct-system').map(e => e.stage));

// When each form-family member becomes drawable: the latest of the family's
// introduction, its host and its mark. A family introduced on one host does
// not bring its later hosts with it (fam-i-tthi is Stage 1 via ඪි; ථි waits
// for ථ). Conjunct hosts (ත්‍ථ, ද්‍ර) wait for the conjunct layer.
function hostStage(h) {
  if (byId.get(h)) return byId.get(h).stage;
  const letters = [...h].map(c => byId.get(c)).filter(Boolean).map(e => e.stage);
  return Math.max(minConjunctStage, ...letters);
}
function familyMembersByStage(f) {
  const markStage = byId.get(f.mark) ? byId.get(f.mark).stage : f.stage;
  const out = new Map();
  for (const h of [...(f.hosts || []), ...(f.conjunct_hosts || [])]) {
    const st = Math.max(f.stage, markStage, hostStage(h));
    if (!out.has(st)) out.set(st, []);
    out.get(st).push(h + f.mark);
  }
  return out;
}

const isMarkLike = e => !!e.position; // attaches to a preceding base
const isBaseLike = e => !e.position && e.type !== 'form-family' && e.type !== 'process' && e.type !== 'conjunct-system';

// ---------------------------------------------------------------------------
// Test-text validation: a text at stage n may only use what exists at n.
// ---------------------------------------------------------------------------
function schedOk(id, n) { const e = byId.get(id); return e && e.stage <= n; }

function validateText(text, n, label) {
  const errs = [], warns = [];
  const chars = [...text];
  const baseAt = i => { // nearest preceding base-like char
    for (let j = i - 1; j >= 0; j--) {
      const c = chars[j];
      if (c === ZWJ || IGNORE.has(c)) continue;
      const e = byId.get(c);
      if (e && isBaseLike(e)) return c;
      if (!e) return null;
    }
    return null;
  };
  chars.forEach((c, i) => {
    if (IGNORE.has(c)) return;
    if (c === ZWJ) {
      if (n < minConjunctStage) errs.push(`${label}: ZWJ conjunct before stage ${minConjunctStage}`);
      return;
    }
    const e = byId.get(c);
    if (!e) { errs.push(`${label}: "${c}" (U+${c.codePointAt(0).toString(16).toUpperCase()}) has no glyph entry`); return; }
    if (e.stage > n) { errs.push(`${label}: ${c} is stage ${e.stage}, used at stage ${n}`); return; }
    if (!isMarkLike(e)) return;
    const b = baseAt(i);
    const be = b && byId.get(b);
    if (be && (be.type === 'vowel' || (be.type === 'composite' && !be.position))) {
      errs.push(`${label}: vowel sign ${c} on independent vowel ${b}`);
      return;
    }
    if (c === 'ි' || c === 'ී') {
      if (c === 'ී' && !schedOk('ී', n)) errs.push(`${label}: ී used before its stage`);
      if (b === 'ර') { if (!(raForms && raForms.stage <= n)) errs.push(`${label}: ${b}${c} before ra-forms`); return; }
      const fam = b && iHostToFamily.get(b);
      if (fam) { if (fam.stage > n) errs.push(`${label}: ${b}${c} needs ${fam.id} (stage ${fam.stage})`); }
      else if (b) warns.push(`${label}: ${b}${c} — host ${b} in no ි family (taxonomy gap)`);
    } else if (c === 'ු' || c === 'ූ') {
      if (c === 'ූ' && !schedOk('ූ', n)) errs.push(`${label}: ූ used before its stage`);
      if (b === 'ර') { if (raForms.stage > n) errs.push(`${label}: රු needs ra-forms (stage ${raForms.stage})`); }
      else { const fam = b && uHostToFamily.get(b); if (fam && fam.stage > n) errs.push(`${label}: ${b}${c} needs ${fam.id} (stage ${fam.stage})`); }
    } else if (c === '්') {
      if (b === 'ර') { if (raForms.stage > n) errs.push(`${label}: ර් needs ra-forms (stage ${raForms.stage})`); }
      else { const fam = b && halHostToFamily.get(b); if (fam && fam.stage > n) errs.push(`${label}: ${b}් needs ${fam.id} (stage ${fam.stage})`); }
    }
  });
  return { errs, warns };
}

// ---------------------------------------------------------------------------
// Drill generation (deterministic) — rhythm lines from the cumulative set.
// ---------------------------------------------------------------------------
function comboOk(t, n) { const r = validateText(t, n, ''); return r.errs.length === 0 && r.warns.length === 0; }

function genDrills(n) {
  const news = ordered.filter(e => e.stage === n);
  const prevBases = ordered.filter(e => e.stage < n && ['base', 'vowel'].includes(e.type));
  const newBases = news.filter(e => ['base', 'vowel'].includes(e.type));
  const f1 = (prevBases.find(e => e.id === 'ට') || newBases[0] || {}).id;
  const f2 = (prevBases.find(e => e.id === 'න') || prevBases.find(e => e.id === 'ස') || prevBases[0] || { id: f1 }).id || f1;
  const lines = [];
  if (newBases.length && f1) {
    lines.push(newBases.map(b => `${f1}${b.id}${f2}${b.id}${f1}`).join(' '));
    lines.push(newBases.map(b => `${b.id}${b.id}${f1}${b.id}`).join(' '));
  }
  // newly-unlocked base+mark joins, computed against the previous stage.
  // Atomic systems (ි ී ු ූ ්) sweep every host; body marks sample 6 hosts.
  // Independent vowels never take vowel signs, so hosts are consonant bases only.
  const hosts = ordered.filter(e => e.stage <= n && e.type === 'base');
  const unlocked = [];
  for (const m of ATOMIC_MARKS) {
    for (const h of hosts) {
      const t = h.id + m;
      if (comboOk(t, n) && !(n > 0 && comboOk(t, n - 1))) unlocked.push(t);
    }
  }
  for (const m of BODY_MARKS) {
    let count = 0;
    for (const h of hosts) {
      if (count >= 6) break;
      const t = h.id + m;
      if (comboOk(t, n) && !(n > 0 && comboOk(t, n - 1))) { unlocked.push(t); count++; }
    }
  }
  for (let i = 0; i < unlocked.length; i += 14) lines.push(unlocked.slice(i, i + 14).join(' '));
  return lines.filter(Boolean);
}

/**
 * Every test-text line a stage exercises: generated drills first, then the
 * authored drills, words and sentences. This is the set the Lists tab shows
 * and the set glyphs-filters harvests graphemes from.
 */
function stageTexts(n) {
  const s = stageByN.get(n);
  if (!s) return [];
  const ts = s.teststrings || {};
  return [
    ...genDrills(n),
    ...(ts.drills || []),
    ...(ts.words && ts.words.length ? [ts.words.join(' ')] : []),
    ...(ts.sentences || []),
  ];
}

module.exports = {
  SRC, ZWJ, IGNORE, ATOMIC_MARKS, BODY_MARKS,
  data, glyphs, entries, byId, seq, ordered, stageNumbers, stageByN,
  iHostToFamily, uHostToFamily, halHostToFamily, raForms, minConjunctStage,
  hostStage, familyMembersByStage, isMarkLike, isBaseLike,
  schedOk, validateText, comboOk, genDrills, stageTexts,
};

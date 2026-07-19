#!/usr/bin/env node
/**
 * build.js — validate the Sinhala design dependency graph and regenerate
 * the visual explainer (index.html) plus a machine view (stages.json).
 *
 *   node build.js          validate + write index.html and stages.json
 *   node build.js --check  validate only, write nothing
 *
 * Everything on the page is DERIVED from sinhala-design-dependencies.yaml.
 * If the process changes, edit the YAML and run `npm run build`.
 */

'use strict';

const fs = require('fs');
const path = require('path');
const yaml = require('js-yaml');

const HERE = __dirname;
const SRC = path.join(HERE, 'sinhala-design-dependencies.yaml');
const OUT_HTML = path.join(HERE, 'index.html');
const OUT_JSON = path.join(HERE, 'stages.json');

const ZWJ = '‍';
const IGNORE = new Set([' ', '\n', '\t', '.', ',', '!', '?', ':', ';', '"', "'", '“', '”', '-', '–']);

const data = yaml.load(fs.readFileSync(SRC, 'utf8'));
const glyphs = data.glyphs;
const errors = [];
const warnings = [];

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

const isMarkLike = e => !!e.position; // attaches to a preceding base
const isBaseLike = e => !e.position && e.type !== 'form-family' && e.type !== 'process' && e.type !== 'conjunct-system';

// ---------------------------------------------------------------------------
// Structural validation
// ---------------------------------------------------------------------------
for (const e of ordered) {
  if (!Number.isInteger(e.stage) || !stageByN.has(e.stage)) errors.push(`${e.id}: stage ${e.stage} not defined in stages block`);
  for (const p of e.parents || []) {
    const pe = byId.get(p);
    if (!pe) { errors.push(`${e.id}: unknown parent "${p}"`); continue; }
    if (seq(pe) >= seq(e)) errors.push(`${e.id} (s${e.stage}.${e.order}): parent ${p} is scheduled at or after it (s${pe.stage}.${pe.order})`);
  }
  for (const m of e.requires || []) {
    if (!data.metrics[m]) errors.push(`${e.id}: unknown metric "${m}"`);
  }
  if (e.skeleton) {
    const sk = data.skeletons[e.skeleton];
    if (!sk) errors.push(`${e.id}: unknown skeleton "${e.skeleton}"`);
    else {
      const intro = byId.get(sk.introduced_by);
      if (intro && seq(intro) > seq(e)) errors.push(`${e.id}: uses skeleton ${e.skeleton} introduced later by ${sk.introduced_by}`);
    }
  }
  for (const el of e.elements || []) {
    const def = data.elements[el];
    if (!def) { errors.push(`${e.id}: unknown element "${el}"`); continue; }
    const intro = byId.get(def.introduced_by);
    if (intro && seq(intro) > seq(e)) errors.push(`${e.id}: uses element ${el} introduced later by ${def.introduced_by}`);
  }
}
// unique order per stage
const seen = new Map();
for (const e of ordered) {
  const k = `${e.stage}.${e.order}`;
  if (seen.has(k)) errors.push(`duplicate schedule slot s${k}: ${seen.get(k)} and ${e.id}`);
  seen.set(k, e.id);
}
// metrics committed_by must exist
for (const [mid, m] of Object.entries(data.metrics)) {
  if (m.committed_by && !byId.get(m.committed_by)) errors.push(`metric ${mid}: committed_by "${m.committed_by}" is not a glyph entry`);
}
// spacing classes: rep first
for (const side of ['left', 'right']) {
  for (const [cid, cls] of Object.entries(data.spacing_classes[side])) {
    const rep = byId.get(cls.rep);
    if (!rep) { errors.push(`spacing ${cid}: rep ${cls.rep} not a glyph entry`); continue; }
    for (const m of cls.members) {
      const me = byId.get(m);
      if (!me) { warnings.push(`spacing ${cid}: member ${m} has no glyph entry`); continue; }
      if (seq(me) < seq(rep)) errors.push(`spacing ${cid}: member ${m} (s${me.stage}.${me.order}) designed before rep ${cls.rep} (s${rep.stage}.${rep.order})`);
    }
  }
}
// form-family hosts must exist as entries
for (const f of entries.filter(e => e.type === 'form-family')) {
  for (const h of f.hosts || []) if (!byId.get(h)) errors.push(`${f.id}: host ${h} has no glyph entry`);
}

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
const ATOMIC_MARKS = ['ි', 'ී', 'ු', 'ූ', '්'];
const BODY_MARKS = ['ා', 'ැ', 'ෑ', 'ෙ', 'ේ', 'ො', 'ෝ', 'ෛ', 'ෘ', 'ෲ', 'ෟ', 'ෳ', 'ෞ'];
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

// validate authored texts + collect per-stage output
const stagesOut = [];
for (const s of data.stages) {
  const ts = s.teststrings || {};
  const authored = [...(ts.drills || []), ...(ts.words || []), ...(ts.sentences || [])];
  for (const t of authored) {
    const { errs, warns } = validateText(t, s.n, `stage ${s.n} "${t}"`);
    errors.push(...errs);
    warnings.push(...warns);
  }
  const generated = genDrills(s.n);
  for (const t of generated) {
    const { errs } = validateText(t, s.n, `stage ${s.n} generated "${t}"`);
    errors.push(...errs); // generated drills must be clean by construction
  }
  const news = ordered.filter(e => e.stage === s.n);
  const cumulative = ordered.filter(e => e.stage <= s.n);
  stagesOut.push({
    ...s,
    glyphs: news.map(e => e.id),
    generated_drills: generated,
    new_count: news.length,
    cumulative_count: cumulative.length,
    total: ordered.length,
  });
}

// ---------------------------------------------------------------------------
// Report
// ---------------------------------------------------------------------------
for (const w of warnings) console.warn('  warn:', w);
if (errors.length) {
  console.error(`\n✗ ${errors.length} validation error(s):`);
  for (const e of errors) console.error('  ERROR:', e);
  process.exit(1);
}
console.log(`✓ graph valid — ${ordered.length} design units, ${data.stages.length} stages, ${warnings.length} warning(s)`);
if (process.argv.includes('--check')) process.exit(0);

// ---------------------------------------------------------------------------
// HTML generation
// ---------------------------------------------------------------------------
const esc = s => String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const one = s => esc(String(s == null ? '' : s).replace(/\s+/g, ' ').trim());

const TYPE_LABEL = {
  base: 'base', vowel: 'vowel', mark: 'mark', composite: 'composite',
  'form-family': 'form family', 'conjunct-system': 'conjunct system',
  sign: 'sign', process: 'process',
};

function stageBadges(n) {
  const b = [];
  for (const [id, m] of Object.entries(data.metrics)) {
    const c = byId.get(m.committed_by);
    if ((m.stage === n && n === 0) || (c && c.stage === n && m.stage !== 0)) b.push({ k: 'metric', t: m.name });
  }
  for (const [id, sk] of Object.entries(data.skeletons)) {
    const c = byId.get(sk.introduced_by);
    if (c && c.stage === n) b.push({ k: 'skeleton', t: `${sk.name} skeleton` });
  }
  for (const [id, el] of Object.entries(data.elements)) {
    const c = byId.get(el.introduced_by);
    if (c && c.stage === n) b.push({ k: 'element', t: `${el.name} element` });
  }
  for (const side of ['left', 'right']) {
    for (const [cid, cls] of Object.entries(data.spacing_classes[side])) {
      const r = byId.get(cls.rep);
      if (r && r.stage === n) b.push({ k: 'spacing', t: `${cid} (rep ${cls.rep})` });
    }
  }
  return b;
}

function tile(e) {
  const disp = e.display || e.id;
  const from = (e.parents || []).length ? `← ${(e.parents || []).join(' + ')}` : (e.stage === 0 ? '' : 'root');
  const meta = [TYPE_LABEL[e.type] || e.type, e.codepoint ? `U+${e.codepoint}` : null].filter(Boolean).join(' · ');
  const note = e.ai && e.ai.construction ? one(e.ai.construction) : '';
  return `<div class="tile t-${e.type}" title="${note}">
    <span class="ord">${e.stage}.${e.order}</span>
    <span class="g">${esc(disp)}</span>
    <span class="from">${esc(from)}</span>
    <span class="meta">${esc(meta)}</span>
  </div>`;
}

function textBlock(title, arr, cls) {
  if (!arr || !arr.length) return '';
  return `<div class="texts"><h4>${esc(title)}</h4>${arr.map(t => `<p class="sinh ${cls || ''}">${esc(t)}</p>`).join('')}</div>`;
}

const famRows = entries.filter(e => e.type === 'form-family').sort((a, b) => seq(a) - seq(b)).map(f => {
  const hostStages = (f.hosts || []).map(h => byId.get(h)).filter(Boolean).map(h => h.stage);
  const completes = hostStages.length ? Math.max(...hostStages, f.stage) : f.stage;
  return `<tr><td class="sinh big">${esc(f.display || f.id)}</td><td><code>${esc(f.id)}</code></td>
    <td class="sinh">${esc((f.hosts || []).join(' ') || '—')}</td><td>${f.stage}</td><td>${completes}</td>
    <td>${one(f.ai && f.ai.construction || '')}</td></tr>`;
}).join('');

const spacingTable = side => Object.entries(data.spacing_classes[side]).map(([cid, cls]) => {
  const members = cls.members.map(m => m === cls.rep ? `<b class="rep">${esc(m)}</b>` : esc(m)).join(' ');
  const rep = byId.get(cls.rep);
  return `<tr><td><code>${esc(cid)}</code></td><td class="sinh big rep">${esc(cls.rep)}</td>
    <td>s${rep.stage}.${rep.order}</td><td class="sinh big">${members}</td><td>${one(cls.note || '')}</td></tr>`;
}).join('');

const elementCards = Object.entries(data.elements).map(([id, el]) => {
  const intro = byId.get(el.introduced_by);
  return `<div class="card">
    <div class="sinh showcase">${esc((el.members || []).join(' '))}</div>
    <h4>${esc(el.name)} <code>${esc(id)}</code></h4>
    <p class="dim">introduced by <span class="sinh">${esc(el.introduced_by)}</span> (stage ${intro ? intro.stage : '?'}) — ${one(el.anatomy || '')}</p>
    <p>${one(el.description)}</p>
  </div>`;
}).join('');

const skeletonCards = Object.entries(data.skeletons).map(([id, sk]) => {
  const intro = byId.get(sk.introduced_by);
  return `<div class="card"><div class="sinh showcase">${esc(sk.introduced_by)}</div>
    <h4>${esc(sk.name)} <code>${esc(id)}</code></h4>
    <p class="dim">archetype <span class="sinh">${esc(sk.introduced_by)}</span>, stage ${intro ? intro.stage : '?'}</p>
    <p>${one(sk.description)}</p></div>`;
}).join('');

const metricRows = Object.entries(data.metrics).map(([id, m]) =>
  `<tr><td><code>${esc(id)}</code></td><td>${esc(m.name)}</td><td class="sinh big">${esc(m.committed_by || '—')}</td><td>${m.stage}</td><td>${one(m.description)}</td></tr>`).join('');

const depCards = data.model.dependency_types.map(d =>
  `<div class="card"><h4>${esc(d.name)}</h4><p>${one(d.summary)}</p></div>`).join('');

const ruleItems = data.model.rules.map(r => `<li>${one(r)}</li>`).join('');
const gateItems = data.model.gates.map(r => `<li>${one(r)}</li>`).join('');
const gapItems = data.gaps.map(g => `<li><code>${esc(g.id)}</code> — ${one(g.text)}</li>`).join('');

const aiDo = (data.ai_guidance.algorithm || []).map(a => `<li>${one(a)}</li>`).join('');
const aiDont = (data.ai_guidance.do_not || []).map(a => `<li>${one(a)}</li>`).join('');

const stageSections = stagesOut.map(s => {
  const news = ordered.filter(e => e.stage === s.n);
  const badges = stageBadges(s.n);
  const pct = Math.round(100 * s.cumulative_count / s.total);
  const ts = s.teststrings || {};
  return `<section class="stage" id="stage-${s.n}">
  <header>
    <div class="snum">${s.n}</div>
    <div>
      <h3>${esc(s.name)}</h3>
      <p class="goal">${one(s.goal)}</p>
    </div>
  </header>
  ${badges.length ? `<div class="badges">${badges.map(b => `<span class="badge b-${b.k}">${esc(b.t)}</span>`).join('')}</div>` : ''}
  ${news.length ? `<div class="flow">${news.map(tile).join('')}</div>` : ''}
  ${textBlock('Generated drills', s.generated_drills, 'drill')}
  ${textBlock('Drills', ts.drills, 'drill')}
  ${textBlock('Words', ts.words && ts.words.length ? [ts.words.join('  ')] : null, '')}
  ${textBlock('Sentences', ts.sentences, 'sent')}
  <div class="gate"><b>Gate:</b> ${one(s.gate)}</div>
  <div class="bar"><div style="width:${pct}%"></div><span>${s.cumulative_count} / ${s.total} design units scheduled (${pct}%)</span></div>
</section>`;
}).join('\n');

const generatedAt = new Date().toISOString().slice(0, 16).replace('T', ' ');

const html = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sinhala Design Dependency Model</title>
<meta name="description" content="A dependency-based, staged development process for Sinhala fonts — generated from sinhala-design-dependencies.yaml">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Abhaya+Libre:wght@400;500;600;700;800&family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
:root{
  --bg:#f5f6f8; --panel:#ffffff; --ink:#1a1c1e; --dim:#66707c; --line:#e7eaee;
  --chip:#eef1f5; --accent:#cf4b34; --accent2:#345ddb; --metric:#9a7112;
  --skeleton:#cf4b34; --element:#345ddb; --spacing:#1f9d63;
  --accent-soft:rgba(207,75,52,.07); --accent-line:rgba(207,75,52,.18);
  --shadow:0 1px 2px rgba(17,24,39,.04), 0 12px 28px -14px rgba(17,24,39,.14);
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--ink);
  font-family:"Inter",system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
  font-size:16px;line-height:1.6;-webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility}
.sinh{font-family:"Abhaya Libre","Noto Sans Sinhala","Iskoola Pota",serif}
.wrap{max-width:1080px;margin:0 auto;padding:0 24px}
a{color:var(--accent2);text-decoration:none}
a:hover{text-decoration:underline}
code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.8em;background:var(--chip);color:var(--ink);padding:2px 6px;border-radius:6px;border:1px solid var(--line)}
h2{font-size:1.8rem;margin:3.4rem 0 .7rem;font-weight:700;letter-spacing:-.01em}
h2 small{display:block;font-weight:400;color:var(--dim);font-size:1rem;letter-spacing:0;margin-top:.15rem}
h4{font-weight:700;font-size:1rem;margin:1.2rem 0 .4rem}
.hero{padding:5rem 0 3rem;position:relative;overflow:hidden}
.hero .mark{position:absolute;right:-10px;top:-70px;font-size:18rem;opacity:.05;font-weight:800;pointer-events:none;color:var(--accent)}
.hero h1{font-size:2.8rem;margin:0 0 .5rem;font-weight:800;line-height:1.08;letter-spacing:-.02em}
.hero p.sub{font-size:1.18rem;color:var(--dim);max-width:52rem;margin:.5rem 0}
.hero .prov{font-size:.85rem;color:var(--dim);margin-top:1rem}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:16px;margin:1.2rem 0}
.card{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:18px 20px;box-shadow:var(--shadow)}
.card h4{margin:.1rem 0 .45rem;font-size:1.05rem}
.card p{margin:.3rem 0;font-size:.92rem;color:var(--dim)}
.card .showcase{font-size:2.6rem;line-height:1.2;margin-bottom:.3rem;color:var(--ink)}
.dim{color:var(--dim)}
ol.rules li,ul.plain li{margin:.5rem 0}
section.stage{background:var(--panel);border:1px solid var(--line);border-radius:18px;padding:24px 26px;margin:1.4rem 0;box-shadow:var(--shadow)}
section.stage header{display:flex;gap:18px;align-items:flex-start}
.snum{font-size:2rem;font-weight:800;color:var(--accent);min-width:2.6rem;height:2.6rem;
  display:flex;align-items:center;justify-content:center;line-height:1;background:var(--accent-soft);border-radius:12px}
section.stage h3{margin:.15rem 0 .3rem;font-size:1.4rem;font-weight:700;letter-spacing:-.01em}
p.goal{margin:.2rem 0 .6rem;color:var(--dim);max-width:56rem}
.badges{display:flex;flex-wrap:wrap;gap:6px;margin:.6rem 0 .9rem}
.badge{font-size:.72rem;font-weight:600;letter-spacing:.02em;padding:4px 10px;border-radius:99px;border:1px solid var(--line);background:var(--panel)}
.b-metric{color:var(--metric)} .b-skeleton{color:var(--skeleton)} .b-element{color:var(--element)} .b-spacing{color:var(--spacing)}
.flow{display:flex;flex-wrap:wrap;gap:10px;margin:.9rem 0}
.tile{background:var(--bg);border:1px solid var(--line);border-radius:12px;padding:10px 12px 8px;min-width:96px;
  display:flex;flex-direction:column;align-items:center;gap:2px;transition:box-shadow .15s,transform .15s}
.tile:hover{box-shadow:var(--shadow);transform:translateY(-1px)}
.tile .g,.tile .from{font-family:"Abhaya Libre","Noto Sans Sinhala","Iskoola Pota",serif}
.tile .g{font-size:2.3rem;line-height:1.15;font-weight:500}
.tile .ord{font-size:.68rem;color:var(--dim);align-self:flex-start;font-family:ui-monospace,monospace}
.tile .from{font-size:.86rem;color:var(--accent2)}
.tile .meta{font-size:.66rem;color:var(--dim);letter-spacing:.02em}
.t-mark .g,.t-composite .g{color:var(--accent)}
.t-form-family{border-style:dashed}
.t-form-family .g{font-size:1.6rem}
.t-conjunct-system{border-style:dashed;border-color:var(--accent)}
.t-conjunct-system .g{font-size:1.5rem}
.t-process{opacity:.85;border-style:dotted}
.t-process .g{font-size:1rem;font-weight:700;padding:.6rem 0}
.texts{margin:.9rem 0}
.texts h4{margin:.7rem 0 .2rem;font-size:.75rem;text-transform:uppercase;letter-spacing:.09em;color:var(--dim);font-weight:700}
.texts p{margin:.25rem 0;font-size:1.75rem;line-height:1.5}
.texts p.drill{color:var(--ink)}
.texts p.sent{font-size:1.5rem}
.gate{margin:1rem 0 .7rem;font-size:.95rem;background:var(--accent-soft);border:1px solid var(--accent-line);border-radius:12px;padding:11px 15px;color:var(--ink)}
.bar{position:relative;height:24px;border:1px solid var(--line);border-radius:99px;overflow:hidden;background:var(--bg)}
.bar div{height:100%;background:var(--spacing);opacity:.28}
.bar span{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font-size:.75rem;color:var(--ink)}
table{border-collapse:separate;border-spacing:0;width:100%;font-size:.92rem;margin:.9rem 0;background:var(--panel);border:1px solid var(--line);border-radius:14px;overflow:hidden}
th,td{border-bottom:1px solid var(--line);padding:10px 12px;text-align:left;vertical-align:top}
tr:last-child td{border-bottom:none}
th{font-size:.72rem;text-transform:uppercase;letter-spacing:.07em;color:var(--dim);background:var(--chip);font-weight:700}
td.big{font-size:1.5rem;line-height:1.3}
.rep{color:var(--spacing);font-weight:700}
.tablewrap{overflow-x:auto;border-radius:14px}
footer{margin:4.5rem 0 2.5rem;color:var(--dim);font-size:.85rem;border-top:1px solid var(--line);padding-top:1.4rem}
.two{display:grid;grid-template-columns:1fr 1fr;gap:32px}
@media(max-width:800px){.two{grid-template-columns:1fr}}
</style>
</head>
<body>
<div class="hero"><div class="wrap">
  <div class="mark sinh">අ</div>
  <h1>Sinhala Design Dependency Model</h1>
  <p class="sub">A mechanical, dependency-based development order for Sinhala fonts.
  Every design decision — a metric, a skeleton, an element, a spacing class, a mark form —
  is introduced exactly once by one glyph and inherited by everything that follows.
  Stages are computed conclusions of the graph, not opinions.</p>
  <p class="prov">Generated from <code>sinhala-design-dependencies.yaml</code> v${esc(data.meta.version)}
  · ${ordered.length} design units · ${data.stages.length} stages
  · based on research by ${esc((data.meta.based_on_research_by || []).join(', '))}
  · orthogonal to the lanka-glyphsets <a href="../../glyphsets/">levels</a></p>
</div></div>

<div class="wrap">

<h2 id="model">The model <small>what counts as a dependency</small></h2>
<div class="cards">${depCards}</div>

<div class="two">
  <div><h2>Rules <small>of the mechanical process</small></h2><ol class="rules">${ruleItems}</ol></div>
  <div><h2>Stage gates <small>every stage must pass all of these</small></h2><ul class="plain">${gateItems}</ul></div>
</div>

<h2>Metrics <small>global decisions — change one later and every descendant reopens</small></h2>
<div class="tablewrap"><table><tr><th>id</th><th>metric</th><th>committed by</th><th>stage</th><th>description</th></tr>${metricRows}</table></div>

<h2>Skeletons <small>one archetype glyph introduces each primary structure</small></h2>
<div class="cards">${skeletonCards}</div>

<h2>Structural elements <small>reusable motifs — each introduced once (cf. sinhala-anatomy.md)</small></h2>
<div class="cards">${elementCards}</div>

<h2 id="pipeline">The stages <small>glyphs in design order — each tile derives from what precedes it</small></h2>
${stageSections}

<h2 id="families">Mark form families <small>one row = one design decision covering many combinations</small></h2>
<div class="tablewrap"><table><tr><th>family</th><th>id</th><th>hosts</th><th>introduced</th><th>completes</th><th>convention</th></tr>${famRows}</table></div>
${(data.mark_systems.ispilla.unassigned_hosts || []).length
    ? `<p class="dim">Unassigned ි hosts (taxonomy gap): <span class="sinh">${esc(data.mark_systems.ispilla.unassigned_hosts.join(' '))}</span></p>`
    : `<p class="dim">${one(data.mark_systems.ispilla.noto_evidence || '')}</p>`}

<h2 id="spacing">Spacing classes <small>the representative (green) sets the sidebearing; members inherit it</small></h2>
<h4>Right side</h4>
<div class="tablewrap"><table><tr><th>class</th><th>rep</th><th>rep designed</th><th>members</th><th>note</th></tr>${spacingTable('right')}</table></div>
<h4>Left side</h4>
<div class="tablewrap"><table><tr><th>class</th><th>rep</th><th>rep designed</th><th>members</th><th>note</th></tr>${spacingTable('left')}</table></div>

<h2 id="ai">For AI font tools <small>this whole model is machine-consumable — the YAML carries the same guidance</small></h2>
<p>${one(data.ai_guidance.purpose)}</p>
<div class="two">
  <div><h4>Algorithm</h4><ol class="rules">${aiDo}</ol></div>
  <div><h4>Never</h4><ul class="plain">${aiDont}</ul>
  <h4>Form families</h4><p class="dim">${one(data.ai_guidance.form_families)}</p></div>
</div>

<h2>Levels × stages</h2>
<p>The lanka-glyphsets <b>levels</b> (<code>glyphsets/sinhala-0-kernel.yaml</code> …) define <i>what a font must
contain</i>; these <b>stages</b> define <i>in what order to design it</i>. Every entry carries a
<code>level</code> tag, so a shipping target is a computed slice: “design in stage order, stop when the
level inventory is covered.”</p>

<h2 id="gaps">Open gaps &amp; concerns <small>carried as data — resolve them in the YAML, then rebuild</small></h2>
<ul class="plain">${gapItems}</ul>

<footer class="wrap">
  Generated ${esc(generatedAt)} by <code>build.js</code> from <code>sinhala-design-dependencies.yaml</code>
  (v${esc(data.meta.version)}). To change the process: edit the YAML, run <code>npm run build</code> —
  this page and <code>stages.json</code> are always derived, never hand-edited.
  Typeface: <a href="https://fonts.google.com/specimen/Abhaya+Libre">Abhaya Libre</a>.
  · ${esc(data.meta.authors.join(', '))} / lanka-glyphsets
</footer>
</div>
</body>
</html>
`;

fs.writeFileSync(OUT_HTML, html);
fs.writeFileSync(OUT_JSON, JSON.stringify({ meta: data.meta, stages: stagesOut, glyphs: data.glyphs }, null, 2));
console.log(`✓ wrote ${path.relative(process.cwd(), OUT_HTML)} (${(html.length / 1024).toFixed(0)} kB) and stages.json`);

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

// The model index, the test-text schedule check and the drill generator live
// in testtexts.js, so glyphs-filters can ask the same questions without a build.
const TT = require('./testtexts');

const HERE = __dirname;
const OUT_HTML = path.join(HERE, 'index.html');
const OUT_JSON = path.join(HERE, 'stages.json');

const {
  data, glyphs, entries, byId, seq, ordered, stageByN,
  familyMembersByStage, validateText, genDrills, stageTexts,
} = TT;

const errors = [];
const warnings = [];

const familyJoins = new Map(); // stage -> [{family, forms}] for members after the introducing stage
for (const f of entries.filter(e => e.type === 'form-family')) {
  for (const [st, forms] of familyMembersByStage(f)) {
    if (st === f.stage) continue;
    if (!familyJoins.has(st)) familyJoins.set(st, []);
    familyJoins.get(st).push({ family: f.id, forms });
  }
}

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
    family_joins: familyJoins.get(s.n) || [],
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

// A multi-host family's tile shows only what is drawable at its own stage;
// the authored `display` (which lists every member) would claim later hosts.
// Single-host families keep `display`: it names irregular forms (ර් රැ) that
// host + mark can't spell.
function familyLabel(f) {
  const hosts = [...(f.hosts || []), ...(f.conjunct_hosts || [])];
  if (hosts.length < 2) return { disp: f.display || f.id, later: '' };
  const byStage = familyMembersByStage(f);
  const later = [...byStage].filter(([st]) => st !== f.stage).sort((a, b) => a[0] - b[0])
    .map(([st, forms]) => `s${st}: ${forms.join(' ')}`).join(' · ');
  return { disp: (byStage.get(f.stage) || []).join(' ') || f.display || f.id, later };
}

function tile(e) {
  const { disp, later } = e.type === 'form-family' ? familyLabel(e) : { disp: e.display || e.id, later: '' };
  const from = (e.parents || []).length ? `← ${(e.parents || []).join(' + ')}` : (e.stage === 0 ? '' : 'root');
  const meta = [TYPE_LABEL[e.type] || e.type, e.codepoint ? `U+${e.codepoint}` : null].filter(Boolean).join(' · ');
  const note = e.ai && e.ai.construction ? one(e.ai.construction) : '';
  return `<div class="tile t-${e.type}" title="${note}">
    <span class="ord">${e.stage}.${e.order}</span>
    <span class="g">${esc(disp)}</span>
    <span class="from">${esc(from)}</span>
    ${later ? `<span class="later sinh">later ${esc(later)}</span>` : ''}
    <span class="meta">${esc(meta)}</span>
  </div>`;
}

function joinsBlock(n) {
  const joins = familyJoins.get(n) || [];
  if (!joins.length) return '';
  return `<div class="texts"><h4>Family members joining this stage</h4>${joins.map(j =>
    `<p><span class="sinh big">${esc(j.forms.join(' '))}</span> <code>${esc(j.family)}</code></p>`).join('')}</div>`;
}

function textBlock(title, arr, cls) {
  if (!arr || !arr.length) return '';
  return `<div class="texts"><h4>${esc(title)}</h4>${arr.map(t => `<p class="sinh ${cls || ''}">${esc(t)}</p>`).join('')}</div>`;
}

const famRows = entries.filter(e => e.type === 'form-family').sort((a, b) => seq(a) - seq(b)).map(f => {
  const completes = Math.max(f.stage, ...familyMembersByStage(f).keys());
  const hosts = [...(f.hosts || []), ...(f.conjunct_hosts || [])];
  return `<tr><td class="sinh big">${esc(f.display || f.id)}</td><td><code>${esc(f.id)}</code></td>
    <td class="sinh">${esc(hosts.join(' ') || '—')}</td><td>${f.stage}</td><td>${completes}</td>
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
  ${joinsBlock(s.n)}
  ${textBlock('Generated drills', s.generated_drills, 'drill')}
  ${textBlock('Drills', ts.drills, 'drill')}
  ${textBlock('Words', ts.words && ts.words.length ? [ts.words.join('  ')] : null, '')}
  ${textBlock('Sentences', ts.sentences, 'sent')}
  <div class="gate"><b>Gate:</b> ${one(s.gate)}</div>
  <div class="bar"><div style="width:${pct}%"></div><span>${s.cumulative_count} / ${s.total} design units scheduled (${pct}%)</span></div>
</section>`;
}).join('\n');

// ---------------------------------------------------------------------------
// Design units tab: one detailed card per glyph entry, in schedule order.
// ---------------------------------------------------------------------------
const childrenOf = new Map(entries.map(e => [e.id, []]));
for (const e of ordered) for (const p of e.parents || []) if (childrenOf.has(p)) childrenOf.get(p).push(e.id);

// what each unit introduces (metrics, skeletons, elements, spacing reps)
const introduces = new Map(entries.map(e => [e.id, []]));
const intro = (id, k, t) => introduces.has(id) && introduces.get(id).push({ k, t });
for (const [mid, m] of Object.entries(data.metrics)) intro(m.committed_by, 'metric', m.name);
for (const [sid, sk] of Object.entries(data.skeletons)) intro(sk.introduced_by, 'skeleton', `${sk.name} skeleton`);
for (const [eid, el] of Object.entries(data.elements)) intro(el.introduced_by, 'element', `${el.name} element`);
for (const side of ['left', 'right']) {
  for (const [cid, cls] of Object.entries(data.spacing_classes[side])) intro(cls.rep, 'spacing', `${cid} (rep)`);
}

const unitLink = id => byId.has(id) ? `<a class="sinh ulink" href="#u-${encodeURIComponent(id)}">${esc(id)}</a>` : `<span class="sinh">${esc(id)}</span>`;
const dl = rows => `<dl class="facts">${rows.filter(([, v]) => v).map(([k, v]) => `<dt>${esc(k)}</dt><dd>${v}</dd>`).join('')}</dl>`;

function unitCard(e) {
  const kids = childrenOf.get(e.id) || [];
  const intros = introduces.get(e.id) || [];
  const sk = e.skeleton && data.skeletons[e.skeleton];
  const els = (e.elements || []).map(x => data.elements[x] ? `${esc(data.elements[x].name)} <code>${esc(x)}</code>` : `<code>${esc(x)}</code>`);
  const reqs = (e.requires || []).map(x => data.metrics[x] ? `${esc(data.metrics[x].name)} <code>${esc(x)}</code>` : `<code>${esc(x)}</code>`);
  const sp = e.spacing || e.form_spacing;
  const spacing = sp ? ['left', 'right'].filter(s => sp[s]).map(s => `${s} <code>${esc(sp[s])}</code>`).join(' · ') : '';
  const overrides = e.form_overrides ? Object.entries(e.form_overrides).map(([f, o]) =>
    `<span class="sinh">${esc(f)}</span> → ${Object.entries(o).map(([s, c]) => `${s} <code>${esc(c)}</code>`).join(', ')}`).join(' · ') : '';
  let members = '';
  if (e.type === 'form-family') {
    members = [...familyMembersByStage(e)].sort((a, b) => a[0] - b[0])
      .map(([st, forms]) => `<span class="dim">s${st}</span> <span class="sinh">${esc(forms.join(' '))}</span>`).join(' · ');
  }
  const disp = e.display || e.id;
  const search = [e.id, e.display, e.translit, e.type, e.codepoint, e.level, e.skeleton, ...(e.elements || []),
    e.ai && e.ai.construction].filter(Boolean).join(' ').toLowerCase();
  return `<article class="unit t-${esc(e.type)}" id="u-${esc(e.id)}" data-type="${esc(e.type)}" data-stage="${e.stage}" data-search="${esc(search)}">
  <div class="uhead">
    <div class="ug sinh">${esc(disp)}</div>
    <div class="utitle">
      <h3>${e.translit ? esc(e.translit) : `<code>${esc(e.id)}</code>`}
        <span class="uord">stage ${e.stage}.${e.order}</span></h3>
      <p class="dim">${esc(TYPE_LABEL[e.type] || e.type)}${e.codepoint ? ` · U+${esc(e.codepoint)}` : ''}${e.position ? ` · ${esc(e.position)}` : ''}${e.level ? ` · <code>${esc(e.level)}</code>` : ''}${e.frequency ? ` · ${esc(e.frequency)} frequency` : ''}</p>
      ${intros.length ? `<div class="badges">${intros.map(b => `<span class="badge b-${b.k}">introduces ${esc(b.t)}</span>`).join('')}</div>` : ''}
    </div>
  </div>
  ${e.ai && e.ai.construction ? `<p class="construction">${one(e.ai.construction)}</p>` : ''}
  ${dl([
    ['Derives from', (e.parents || []).length ? e.parents.map(unitLink).join(' ') : (e.stage === 0 ? '' : '<span class="dim">root — no parents</span>')],
    ['Feeds', kids.length ? kids.map(unitLink).join(' ') : ''],
    ['Skeleton', sk ? `${esc(sk.name)} <code>${esc(e.skeleton)}</code>` : ''],
    ['Elements', els.join(', ')],
    ['Commits / requires', reqs.join(', ')],
    ['Mark', e.mark ? `<span class="sinh">${esc(e.mark)}</span>${e.fused ? ' <span class="dim">· fused forms</span>' : ''}` : ''],
    ['Members', members],
    ['Forms', e.forms ? `<span class="sinh">${esc(e.forms.join(' '))}</span>` : ''],
    ['Spacing', spacing],
    ['Form overrides', overrides],
    ['Spacing note', e.spacing_note ? one(e.spacing_note) : ''],
  ])}
  ${e.ai && (e.ai.checks || []).length ? `<h4>Checks</h4><ul class="checks">${e.ai.checks.map(c => `<li>${one(c)}</li>`).join('')}</ul>` : ''}
</article>`;
}

const unitTypes = [...new Set(ordered.map(e => e.type))];
const unitsByStage = data.stages.map(s => {
  const us = ordered.filter(e => e.stage === s.n);
  if (!us.length) return '';
  return `<section class="ustage" data-stage="${s.n}"><h2><span class="snum">${s.n}</span> ${esc(s.name)} <small>${us.length} unit${us.length === 1 ? '' : 's'}</small></h2>
  <div class="units">${us.map(unitCard).join('\n')}</div></section>`;
}).join('\n');

// ---------------------------------------------------------------------------
// Lists tab: per-stage glyph names and cumulative test texts, copyable.
// Names come from the glyphs-filters Stages catalogue — the same derivation
// and naming authority as the Glyphs sidebar filters, so the two never drift.
// ---------------------------------------------------------------------------
const stageFilters = require(path.join(HERE, '..', 'glyphs-filters', 'catalogue'))
  .sections.find(s => s.id === 'Stages').filters;
// Matched by shape, not by prefix: the catalogue also carries "Stage N
// graphemes" filters, which `Stage `/`Through Stage ` would swallow.
const namesFor = re => new Map(stageFilters
  .map(f => [f, re.exec(f.name)])
  .filter(([, m]) => m)
  .map(([f, m]) => [Number(m[1]), f.glyphs]));
const stageNames = namesFor(/^Stage (\d+) —/);
const throughNames = namesFor(/^Through Stage (\d+)$/);
const stageGraphemes = namesFor(/^Stage (\d+) graphemes$/);

const copyBox = (label, text, cls) => `<div class="copybox">
    <div class="copyhead"><h4>${label}</h4><button class="copy" type="button">Copy</button></div>
    <pre class="${cls}">${esc(text)}</pre></div>`;

let cumTexts = [];
const listSections = data.stages.map(s => {
  cumTexts = cumTexts.concat(stageTexts(s.n));
  const own = stageNames.get(s.n) || [];
  const through = throughNames.get(s.n) || [];
  const graphemes = stageGraphemes.get(s.n) || [];
  if (!own.length && !cumTexts.length) return '';
  return `<section class="lstage" id="l-${s.n}"><h2><span class="snum">${s.n}</span> ${esc(s.name)}</h2>
  ${own.length ? copyBox(`Glyph names — new in this stage <span class="dim">${own.length}</span>`, own.join(' '), 'names') : ''}
  ${through.length ? copyBox(`Glyph names — through stage ${s.n} <span class="dim">${through.length}</span>`, through.join(' '), 'names') : ''}
  ${graphemes.length ? copyBox(`Composable graphemes — may be drawn atomically <span class="dim">${graphemes.length}</span>`, graphemes.join(' '), 'names') : ''}
  ${cumTexts.length ? copyBox(`Test text — stages 0–${s.n} cumulative <span class="dim">${cumTexts.length} lines</span>`, cumTexts.join('\n'), 'sinh ltext') : ''}
</section>`;
}).join('\n');

const html = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sinhala Design Dependency Model</title>
<meta name="description" content="A dependency-based, staged development process for Sinhala fonts — generated from sinhala-design-dependencies.yaml">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Abhaya+Libre:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<link rel="stylesheet" href="../_shared/bw.css">
<style>
/* Black-and-white palette: tokens from ../_shared/bw.css. */
:root{
  --panel:var(--bg); --ink:var(--fg); --dim:var(--muted);
  --chip:var(--soft); --accent:var(--fg); --accent2:var(--fg); --metric:var(--fg);
  --skeleton:var(--fg); --element:var(--fg); --spacing:var(--fg);
  --accent-soft:var(--soft); --accent-line:var(--fg);
  --shadow:none;
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--ink);
  font-family:var(--font-ui);
  font-size:16px;line-height:1.6;-webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility}
.sinh{font-family:"Abhaya Libre","Noto Sans Sinhala","Iskoola Pota",serif}
.wrap{max-width:1080px;margin:0 auto;padding:0 24px}
a{color:inherit;text-decoration:underline;text-underline-offset:2px}
code{font-family:var(--font-mono);font-size:.8em;background:var(--chip);color:var(--ink);padding:2px 6px;border:1px solid var(--line)}
h2{font-size:1.8rem;margin:3.4rem 0 .7rem;font-weight:700;letter-spacing:-.01em}
h2 small{display:block;font-weight:400;color:var(--dim);font-size:1rem;letter-spacing:0;margin-top:.15rem}
h4{font-weight:700;font-size:1rem;margin:1.2rem 0 .4rem}
.hero{padding:5rem 0 3rem;position:relative;overflow:hidden}
.hero .mark{position:absolute;right:-10px;top:-70px;font-size:18rem;opacity:.05;font-weight:800;pointer-events:none;color:var(--accent)}
.hero h1{font-size:2.8rem;margin:0 0 .5rem;font-weight:800;line-height:1.08;letter-spacing:-.02em}
.hero p.sub{font-size:1.18rem;color:var(--dim);max-width:52rem;margin:.5rem 0}
.hero .prov{font-size:.85rem;color:var(--dim);margin-top:1rem}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:16px;margin:1.2rem 0}
.card{background:var(--panel);border:1px solid var(--line);border-radius:0;padding:18px 20px;box-shadow:var(--shadow)}
.card h4{margin:.1rem 0 .45rem;font-size:1.05rem}
.card p{margin:.3rem 0;font-size:.92rem;color:var(--dim)}
.card .showcase{font-size:2.6rem;line-height:1.2;margin-bottom:.3rem;color:var(--ink)}
.dim{color:var(--dim)}
ol.rules li,ul.plain li{margin:.5rem 0}
section.stage{background:var(--panel);border:1px solid var(--line);border-radius:0;padding:24px 26px;margin:1.4rem 0;box-shadow:var(--shadow)}
section.stage header{display:flex;gap:18px;align-items:flex-start}
.snum{font-size:2rem;font-weight:800;color:var(--accent);min-width:2.6rem;height:2.6rem;
  display:flex;align-items:center;justify-content:center;line-height:1;background:var(--accent-soft);border-radius:0}
section.stage h3{margin:.15rem 0 .3rem;font-size:1.4rem;font-weight:700;letter-spacing:-.01em}
p.goal{margin:.2rem 0 .6rem;color:var(--dim);max-width:56rem}
.badges{display:flex;flex-wrap:wrap;gap:6px;margin:.6rem 0 .9rem}
.badge{font-size:.72rem;font-weight:600;letter-spacing:.02em;padding:4px 10px;border-radius:99px;border:1px solid var(--line);background:var(--panel)}
.b-metric{color:var(--metric)} .b-skeleton{color:var(--skeleton)} .b-element{color:var(--element)} .b-spacing{color:var(--spacing)}
.flow{display:flex;flex-wrap:wrap;gap:10px;margin:.9rem 0}
.tile{background:var(--bg);border:1px solid var(--line);border-radius:0;padding:10px 12px 8px;min-width:96px;
  display:flex;flex-direction:column;align-items:center;gap:2px;transition:box-shadow .15s,transform .15s}
.tile:hover{border-color:var(--fg)}
.tile .g,.tile .from{font-family:"Abhaya Libre","Noto Sans Sinhala","Iskoola Pota",serif}
.tile .g{font-size:2.3rem;line-height:1.15;font-weight:500}
.tile .ord{font-size:.68rem;color:var(--dim);align-self:flex-start;font-family:ui-monospace,monospace}
.tile .from{font-size:.86rem;color:var(--accent2)}
.tile .later{font-size:.78rem;color:var(--dim);max-width:16rem;text-align:center;font-family:"Abhaya Libre","Noto Sans Sinhala","Iskoola Pota",serif}
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
.gate{margin:1rem 0 .7rem;font-size:.95rem;background:var(--accent-soft);border:1px solid var(--accent-line);border-radius:0;padding:11px 15px;color:var(--ink)}
.bar{position:relative;height:24px;border:1px solid var(--line);border-radius:99px;overflow:hidden;background:var(--bg)}
.bar div{height:100%;background:var(--fg);opacity:.18}
.bar span{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font-size:.75rem;color:var(--ink)}
table{border-collapse:separate;border-spacing:0;width:100%;font-size:.92rem;margin:.9rem 0;background:var(--panel);border:1px solid var(--line);border-radius:0;overflow:hidden}
th,td{border-bottom:1px solid var(--line);padding:10px 12px;text-align:left;vertical-align:top}
tr:last-child td{border-bottom:none}
th{font-size:.72rem;text-transform:uppercase;letter-spacing:.07em;color:var(--dim);background:var(--chip);font-weight:700}
td.big{font-size:1.5rem;line-height:1.3}
.rep{color:var(--spacing);font-weight:700}
.tablewrap{overflow-x:auto;border-radius:0}
footer{margin:4.5rem 0 2.5rem;color:var(--dim);font-size:.85rem;border-top:1px solid var(--line);padding-top:1.4rem}
.two{display:grid;grid-template-columns:1fr 1fr;gap:32px}
@media(max-width:800px){.two{grid-template-columns:1fr}}
.tabs{position:sticky;top:0;z-index:10;background:var(--bg);border-bottom:1px solid var(--line)}
.tabs .wrap{display:flex;gap:4px}
.tabs button{font:inherit;font-size:.95rem;font-weight:600;color:var(--dim);background:none;border:0;border-bottom:3px solid transparent;padding:12px 14px 9px;cursor:pointer}
.tabs button:hover{color:var(--ink)}
.tabs button[aria-selected="true"]{color:var(--accent);border-bottom-color:var(--accent)}
[role="tabpanel"][hidden]{display:none}
.ufilter{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:2rem 0 .5rem}
.ufilter input{font:inherit;flex:1 1 240px;padding:9px 13px;border:1px solid var(--line);border-radius:0;background:var(--panel);color:var(--ink)}
.ufilter .chip{font:inherit;font-size:.8rem;font-weight:600;padding:6px 12px;border-radius:99px;border:1px solid var(--line);background:var(--panel);color:var(--dim);cursor:pointer}
.ufilter .chip[aria-pressed="true"]{background:var(--fg);border-color:var(--fg);color:var(--bg)}
.ucount{font-size:.85rem;color:var(--dim);margin:.2rem 0 0}
.ustage h2{display:flex;align-items:center;gap:12px;font-size:1.4rem;margin:2.4rem 0 .6rem}
.ustage h2 small{display:inline;margin:0}
.ustage .snum{font-size:1.2rem;min-width:2rem;height:2rem;border-radius:0}
.units{display:grid;grid-template-columns:repeat(auto-fill,minmax(440px,1fr));gap:16px}
@media(max-width:560px){.units{grid-template-columns:1fr}}
.unit{background:var(--panel);border:1px solid var(--line);border-radius:0;padding:18px 20px;box-shadow:var(--shadow);scroll-margin-top:64px}
.unit:target{border-color:var(--fg);outline:2px solid var(--fg)}
.unit.t-form-family,.unit.t-conjunct-system{border-style:dashed}
.uhead{display:flex;gap:16px;align-items:flex-start}
.ug{font-size:3rem;line-height:1.1;min-width:3.6rem;text-align:center;font-weight:500}
.unit.t-mark .ug,.unit.t-composite .ug{color:var(--accent)}
.unit.t-form-family .ug,.unit.t-conjunct-system .ug{font-size:1.7rem;max-width:12rem}
.unit.t-process .ug{font-family:inherit;font-size:1rem;font-weight:700;padding-top:.5rem}
.utitle h3{margin:.1rem 0 0;font-size:1.1rem;display:flex;gap:10px;align-items:baseline;flex-wrap:wrap}
.utitle p{margin:.1rem 0;font-size:.85rem}
.utitle .badges{margin:.4rem 0 0}
.uord{font-size:.72rem;font-weight:500;color:var(--dim);font-family:ui-monospace,monospace}
.construction{font-size:.93rem;margin:.8rem 0}
.facts{display:grid;grid-template-columns:max-content 1fr;gap:4px 14px;margin:.6rem 0;font-size:.88rem}
.facts dt{color:var(--dim);font-size:.72rem;text-transform:uppercase;letter-spacing:.06em;font-weight:700;padding-top:.2rem}
.facts dd{margin:0}
.facts .sinh{font-size:1.2rem}
.ulink{margin-right:.35rem}
.unit h4{font-size:.72rem;text-transform:uppercase;letter-spacing:.06em;color:var(--dim);margin:.8rem 0 .2rem}
ul.checks{margin:.2rem 0;padding-left:1.2rem;font-size:.88rem}
ul.checks li{margin:.2rem 0}
.lintro{margin:2rem 0 .5rem;color:var(--dim);max-width:56rem}
.lstage{background:var(--panel);border:1px solid var(--line);border-radius:0;padding:18px 22px;margin:1.2rem 0;box-shadow:var(--shadow);scroll-margin-top:64px}
.lstage h2{display:flex;align-items:center;gap:12px;font-size:1.3rem;margin:0 0 .4rem}
.lstage .snum{font-size:1.2rem;min-width:2rem;height:2rem;border-radius:0}
.copybox{margin:.8rem 0}
.copyhead{display:flex;align-items:center;justify-content:space-between;gap:12px}
.copyhead h4{margin:0;font-size:.75rem;text-transform:uppercase;letter-spacing:.09em;color:var(--dim);font-weight:700}
.copy{font:inherit;font-size:.8rem;font-weight:600;padding:5px 14px;border-radius:99px;border:1px solid var(--accent-line);background:var(--accent-soft);color:var(--accent);cursor:pointer}
.copy:hover{border-color:var(--accent)}
.copy.done{color:var(--bg);background:var(--fg)}
.copybox pre{margin:.4rem 0 0;padding:10px 13px;background:var(--bg);border:1px solid var(--line);border-radius:0;
  white-space:pre-wrap;word-break:break-word;max-height:16rem;overflow:auto}
.copybox pre.names{font-family:ui-monospace,monospace;font-size:.8rem;line-height:1.6}
.copybox pre.ltext{font-size:1.4rem;line-height:1.6}
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
  · orthogonal to the <a href="https://github.com/mooniak/lanka-glyphsets">lanka-glyphsets</a> levels</p>
</div></div>

<nav class="tabs" role="tablist"><div class="wrap">
  <button role="tab" id="tab-model" aria-controls="panel-model" aria-selected="true">Model &amp; stages</button>
  <button role="tab" id="tab-units" aria-controls="panel-units" aria-selected="false">Design units <span class="dim">${ordered.length}</span></button>
  <button role="tab" id="tab-lists" aria-controls="panel-lists" aria-selected="false">Glyph lists &amp; texts</button>
</div></nav>

<div class="wrap" role="tabpanel" id="panel-lists" aria-labelledby="tab-lists" hidden>
<p class="lintro">Per stage: the production glyph names (LankaGlyphSets <code>name-sinh</code>, identical to the
Glyphs sidebar filters from <code>tools/glyphs-filters</code>) new in that stage and cumulative, plus every
test text available by then — drills, words and sentences from stage 0 up to it. Paste names into
<i>Glyph › Add Glyphs…</i> and texts into an Edit tab.</p>
${listSections}
</div>

<div class="wrap" role="tabpanel" id="panel-units" aria-labelledby="tab-units" hidden>
<div class="ufilter">
  <input type="search" id="ufind" placeholder="Search glyph, transliteration, element, construction…" aria-label="Search design units">
  <button class="chip" data-type="" aria-pressed="true">all</button>
  ${unitTypes.map(t => `<button class="chip" data-type="${esc(t)}" aria-pressed="false">${esc(TYPE_LABEL[t] || t)}</button>`).join('')}
</div>
<p class="ucount" id="ucount"></p>
${unitsByStage}
</div>

<div class="wrap" role="tabpanel" id="panel-model" aria-labelledby="tab-model">

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
</div>

<footer class="wrap">
  Generated by <code>build.js</code> from <code>sinhala-design-dependencies.yaml</code>
  (v${esc(data.meta.version)}). To change the process: edit the YAML, run <code>npm run build</code> —
  this page and <code>stages.json</code> are always derived, never hand-edited.
  Typeface: <a href="https://fonts.google.com/specimen/Abhaya+Libre">Abhaya Libre</a>.
  · ${esc(data.meta.authors.join(', '))} / lanka-glyphsets
</footer>
<script>
(() => {
  const tabs = [...document.querySelectorAll('[role=tab]')];
  const show = (id, scroll) => {
    for (const t of tabs) {
      const on = t.id === id;
      t.setAttribute('aria-selected', on);
      document.getElementById(t.getAttribute('aria-controls')).hidden = !on;
    }
    if (scroll) document.querySelector('.tabs').scrollIntoView();
  };
  // a hash decides the tab: #units or #u-… opens units, #lists or #l-… the
  // lists, anything else the model
  const fromHash = () => {
    const h = decodeURIComponent(location.hash.slice(1));
    if (h === 'lists' || h.startsWith('l-')) {
      show('tab-lists');
      const el = h.startsWith('l-') && document.getElementById(h);
      if (el) el.scrollIntoView();
    } else if (h === 'units' || h.startsWith('u-')) {
      show('tab-units');
      const el = h.startsWith('u-') && document.getElementById(h);
      if (el) { el.hidden = false; el.closest('.ustage').hidden = false; el.scrollIntoView(); }
    } else if (h) show('tab-model');
  };
  for (const t of tabs) t.addEventListener('click', () => {
    history.replaceState(null, '', '#' + t.id.slice(4));
    show(t.id, window.scrollY > document.querySelector('.tabs').offsetTop);
  });
  window.addEventListener('hashchange', fromHash);

  // clipboard API needs a secure context; fall back to execCommand for file://
  const copyText = text => navigator.clipboard && window.isSecureContext
    ? navigator.clipboard.writeText(text)
    : new Promise((ok, fail) => {
      const ta = Object.assign(document.createElement('textarea'), { value: text });
      ta.style.position = 'fixed'; ta.style.opacity = '0';
      document.body.appendChild(ta); ta.select();
      const r = document.execCommand('copy'); ta.remove();
      r ? ok() : fail();
    });
  for (const b of document.querySelectorAll('.copy')) b.addEventListener('click', () => {
    copyText(b.closest('.copybox').querySelector('pre').textContent).then(() => {
      b.textContent = 'Copied'; b.classList.add('done');
      setTimeout(() => { b.textContent = 'Copy'; b.classList.remove('done'); }, 1400);
    }, () => { b.textContent = 'Copy failed'; });
  });

  const find = document.getElementById('ufind');
  const chips = [...document.querySelectorAll('.ufilter .chip')];
  const units = [...document.querySelectorAll('.unit')];
  let type = '';
  const filter = () => {
    const q = find.value.trim().toLowerCase();
    let n = 0;
    for (const u of units) {
      const ok = (!type || u.dataset.type === type) && (!q || u.dataset.search.includes(q));
      u.hidden = !ok; if (ok) n++;
    }
    for (const s of document.querySelectorAll('.ustage')) s.hidden = !s.querySelector('.unit:not([hidden])');
    document.getElementById('ucount').textContent = n + ' of ' + units.length + ' design units';
  };
  find.addEventListener('input', filter);
  for (const c of chips) c.addEventListener('click', () => {
    type = c.dataset.type;
    for (const x of chips) x.setAttribute('aria-pressed', x === c);
    filter();
  });
  filter();
  fromHash();
})();
</script>
</body>
</html>
`;

fs.writeFileSync(OUT_HTML, html);
fs.writeFileSync(OUT_JSON, JSON.stringify({ meta: data.meta, stages: stagesOut, glyphs: data.glyphs }, null, 2));
console.log(`✓ wrote ${path.relative(process.cwd(), OUT_HTML)} (${(html.length / 1024).toFixed(0)} kB) and stages.json`);

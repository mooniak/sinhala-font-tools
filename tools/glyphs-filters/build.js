#!/usr/bin/env node
/**
 * build.js — generate Glyphs 3 sidebar filters from this repo's models.
 *
 *   node build.js              write filters/CustomFilter MNIK Sinhala.plist
 *   node build.js --check      validate + report, write nothing
 *   node build.js --list       print the catalogue with member counts
 *   node build.js --split      one CustomFilter<Section>.plist per section
 *   node build.js --flat       no subfolders (one folder per section only)
 *   node build.js --title "…"  sidebar heading / filename suffix
 *   node build.js --out DIR    write somewhere else (e.g. beside a .glyphs file)
 *   node build.js --only Spacing,Stages
 *
 * The filename MUST start with `CustomFilter`; everything after it becomes the
 * sidebar heading (cf. Typotheque's `CustomFilter TPTQ Devanagari.plist`).
 * Folders are the `subGroup` key — see plist.js.
 *
 * Every filter is derived — see catalogue.js. Glyph names are LankaGlyphSets
 * (`name-sinh`), resolved through the vendored lankaglyphset-map.js.
 */

'use strict';

const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');

const S = require('./sources');
const { sections } = require('./catalogue');
const { toPlist } = require('./plist');

const DEFAULT_OUT = path.join(S.REPO, 'filters');
const DEFAULT_TITLE = 'MNIK Sinhala';

const argv = process.argv.slice(2);
const flag = n => argv.includes(n);
const opt = (n, d) => {
  const i = argv.indexOf(n);
  return i >= 0 && argv[i + 1] ? argv[i + 1] : d;
};

const CHECK = flag('--check');
const LIST = flag('--list');
const SPLIT = flag('--split');
const FLAT = flag('--flat');
const TITLE = opt('--title', DEFAULT_TITLE);
const OUT = path.resolve(opt('--out', DEFAULT_OUT));
const ONLY = opt('--only', null);
const only = ONLY ? new Set(ONLY.split(',').map(s => s.trim().toLowerCase())) : null;

const selected = sections.filter(s => !only || only.has(s.id.toLowerCase()));
if (only && selected.length === 0) {
  console.error(`no section matches --only ${ONLY}. Known: ${sections.map(s => s.id).join(', ')}`);
  process.exit(1);
}

// ---------------------------------------------------------------------------
// Report
// ---------------------------------------------------------------------------
const empty = [];
let filterCount = 0;
let glyphRefs = 0;

for (const sec of selected) {
  for (const f of sec.filters) {
    filterCount++;
    glyphRefs += f.glyphs.length;
    if (f.glyphs.length === 0) empty.push(`${sec.id}: ${f.name}  (${f.path})`);
  }
}

if (LIST) {
  for (const sec of selected) {
    console.log(`\n### ${sec.title}`);
    let group = null;
    for (const f of sec.filters) {
      if (f.group !== group) {
        group = f.group;
        if (group) console.log(`   ${group}`);
      }
      console.log(`  ${String(f.glyphs.length).padStart(4)}  ${f.name}`);
    }
  }
  console.log(`\n${filterCount} filters in ${selected.length} sections.`);
  process.exit(0);
}

// ---------------------------------------------------------------------------
// Tree — sections become folders, `group` becomes a nested folder.
// Empty filters are reported below, never written: an empty sidebar entry
// looks like a font problem when it is really a model hole.
// ---------------------------------------------------------------------------
const shorten = n => (n.includes(' · ') ? n.split(' · ').slice(1).join(' · ') : n);

function nodesForSection(sec) {
  const children = [];
  const groups = new Map();
  for (const f of sec.filters) {
    if (f.glyphs.length === 0) continue;
    if (!f.group || FLAT) {
      children.push({ name: f.name, glyphs: f.glyphs });
      continue;
    }
    if (!groups.has(f.group)) {
      const g = { name: f.group, children: [] };
      groups.set(f.group, g);
      children.push(g);
    }
    groups.get(f.group).children.push({ name: shorten(f.name), glyphs: f.glyphs });
  }
  return children;
}

const files = SPLIT
  ? selected.map(sec => ({
      file: `CustomFilter${sec.id}.plist`,
      nodes: nodesForSection(sec),
      label: sec.title,
    }))
  : [{
      file: `CustomFilter ${TITLE}.plist`,
      nodes: selected.map(sec => ({ name: sec.title, children: nodesForSection(sec) })),
      label: TITLE,
    }];

const rendered = files.map(f => ({ ...f, text: toPlist(f.nodes) }));

const unresolved = [...new Set(S.unresolved)];
if (unresolved.length) {
  console.warn(`WARNING: ${unresolved.length} sequence(s) had no LankaGlyphSets name and were ` +
    `dropped: ${unresolved.slice(0, 12).join(' ')}${unresolved.length > 12 ? ' …' : ''}`);
}
if (empty.length) {
  console.warn(`WARNING: ${empty.length} filter(s) are empty — the model has a hole there:`);
  for (const e of empty) console.warn(`  ${e}`);
}

const written = filterCount - empty.length;
console.log(`${written} filters, ${glyphRefs} glyph references, ${selected.length} sections.`);

if (CHECK) {
  console.log(`CHECK: nothing written. Would write ${rendered.map(r => r.file).join(', ')} to ${OUT}`);
  process.exit(0);
}

// ---------------------------------------------------------------------------
// Write
// ---------------------------------------------------------------------------
fs.mkdirSync(OUT, { recursive: true });

for (const r of rendered) {
  const dest = path.join(OUT, r.file);
  fs.writeFileSync(dest, r.text, 'utf8');
  try {
    execFileSync('plutil', ['-lint', dest], { stdio: 'pipe' });
  } catch (e) {
    console.error(`plutil rejected ${r.file}: ${e.stderr ? e.stderr.toString().trim() : e.message}`);
    process.exit(1);
  }
  const count = r.nodes.reduce(function tally(n, node) {
    return n + (node.children ? node.children.reduce(tally, 0) : 1);
  }, 0);
  console.log(`  wrote ${r.file}  (${count} filters)`);
}

const manifest = {
  generated_by: 'tools/glyphs-filters (node build.js)',
  model_version: S.model.meta.version,
  naming: 'lanka-glyphsets "name-sinh" via tools/glyphname-unicode-converter/lankaglyphset-map.js',
  files: rendered.map(r => r.file),
  sources: Object.fromEntries(
    Object.entries(S.PATHS).map(([k, v]) => [k, path.relative(S.REPO, v)])
  ),
  sections: selected.map(sec => ({
    id: sec.id,
    title: sec.title,
    filters: sec.filters
      .filter(f => f.glyphs.length > 0)
      .map(f => ({ name: f.name, group: f.group, count: f.glyphs.length, path: f.path, glyphs: f.glyphs })),
  })),
};
fs.writeFileSync(path.join(OUT, 'manifest.json'), JSON.stringify(manifest, null, 2) + '\n', 'utf8');
console.log('  wrote manifest.json');

const md = [];
md.push('# Glyphs sidebar filters — GENERATED');
md.push('');
md.push('Do not hand-edit. Regenerate with `node tools/glyphs-filters/build.js`.');
md.push('');
md.push('Copy the `CustomFilter*.plist` file(s) next to a `.glyphs`/`.glyphspackage` file');
md.push('(project-scoped) or into `~/Library/Application Support/Glyphs 3/` (global), then');
md.push('restart Glyphs. The sidebar heading is whatever follows `CustomFilter` in the');
md.push('filename; sections and groups appear as folders under it.');
md.push('');
md.push(`Model version ${S.model.meta.version}. Glyph names are LankaGlyphSets \`name-sinh\`.`);
md.push('');
for (const sec of selected) {
  md.push(`## ${sec.title}`);
  md.push('');
  md.push(sec.blurb);
  md.push('');
  md.push('| Folder | Filter | Glyphs | Generated from |');
  md.push('|---|---|---:|---|');
  for (const f of sec.filters) {
    if (f.glyphs.length === 0) continue;
    const cell = s => String(s).replace(/\|/g, '\\|');
    md.push(`| ${cell(f.group || '—')} | ${cell(f.name)} | ${f.glyphs.length} | \`${f.path}\` |`);
  }
  md.push('');
}
fs.writeFileSync(path.join(OUT, 'README.md'), md.join('\n'), 'utf8');
console.log('  wrote README.md');
console.log(`filters written to ${OUT}`);

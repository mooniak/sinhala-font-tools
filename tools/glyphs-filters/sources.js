/**
 * sources.js — load every data source the filter catalogue is generated from,
 * and resolve Sinhala character sequences to LankaGlyphSets glyph names.
 *
 * Nothing here is authored: the four sources below are the only truth, and
 * lankaglyphset-map.js (vendored from lanka-glyphsets) is the only naming
 * authority. If a filter's members look wrong, the model is wrong.
 */

'use strict';

const fs = require('fs');
const path = require('path');

const HERE = __dirname;
const REPO = path.resolve(HERE, '..', '..');

// js-yaml lives in the design-stages package; fall back to it so this tool
// needs no install of its own.
let yaml;
try {
  yaml = require('js-yaml');
} catch (e) {
  yaml = require(path.join(REPO, 'sinhala-design-stages/node_modules/js-yaml'));
}

const LGS = require(path.join(REPO, 'tools/glyphname-unicode-converter/lankaglyphset-map.js'));
const SHAPING = require(path.join(REPO, 'tools/_generated/shaping-exceptions.js'));
const LANKA = require(path.join(REPO, 'tools/_generated/lanka-glyph-data.js'));

const PATHS = {
  model: path.join(REPO, 'sinhala-design-stages/sinhala-design-dependencies.yaml'),
  spacing: path.join(REPO, 'sinhala-spacing.yaml'),
  composites: path.join(REPO, 'sinhala-composites.yaml'),
};

const loadYaml = p => yaml.load(fs.readFileSync(p, 'utf8'));

const model = loadYaml(PATHS.model);
const spacing = loadYaml(PATHS.spacing);
const composites = loadYaml(PATHS.composites);

const unresolved = [];

/** Sinhala character sequence -> LGS glyph name (null if the map can't name it). */
function name(seq) {
  let r = null;
  try {
    r = LGS.unicodeToName(seq);
  } catch (e) {
    r = null;
  }
  if (!r || !r.name) {
    unresolved.push(seq);
    return null;
  }
  return r.name;
}

const names = seqs => [...new Set(seqs.map(name).filter(Boolean))];

/**
 * The fused glyphs of a form family, as characters. sinhala-spacing.yaml has
 * already expanded the families marked `fused: true`; families that compose
 * (hal-trap, hal-ja) are expanded here from hosts + mark. conjunct_hosts are
 * already-assembled conjunct strings (e.g. ද්‍ර) that can't be model.glyphs
 * entry ids themselves, so they live outside `hosts` — see gap
 * conjunct-i-forms-resolution.
 */
function formGlyphs(familyId) {
  const fromSpacing = spacing.forms && spacing.forms[familyId];
  if (fromSpacing && fromSpacing.glyphs) return Object.keys(fromSpacing.glyphs);
  const fam = model.glyphs[familyId];
  if (!fam || !fam.mark || !fam.hosts) return [];
  const hosts = [...fam.hosts, ...(fam.conjunct_hosts || [])];
  return hosts.map(h => h + fam.mark);
}

/** The characters a model entry stands for (a letter, or a family's forms). */
function charsOf(id) {
  const e = model.glyphs[id];
  if (!e) return [];
  if (e.codepoint) return [id];
  if (e.type === 'form-family') return formGlyphs(id);
  return [];
}

/** Plain consonants, in model order — the hosts of every conjunct system. */
function consonants() {
  return Object.entries(model.glyphs)
    .filter(([id, e]) => e.type === 'base' && e.codepoint && id >= 'ක' && id <= 'ෆ')
    .map(([id]) => id);
}

/** Every base letter (consonants + the independent vowels typed as base). */
function bases() {
  return Object.entries(model.glyphs)
    .filter(([, e]) => e.type === 'base' && e.codepoint)
    .map(([id]) => id);
}

/** Transitive design descendants of a glyph, over the `parents` graph. */
function descendants(rootId) {
  const parents = new Map(Object.entries(model.glyphs).map(([id, e]) => [id, e.parents || []]));
  const out = new Set();
  let changed = true;
  while (changed) {
    changed = false;
    for (const [id, ps] of parents) {
      if (out.has(id)) continue;
      if (ps.some(p => p === rootId || out.has(p))) {
        out.add(id);
        changed = true;
      }
    }
  }
  return [...out];
}

module.exports = {
  REPO, PATHS,
  model, spacing, composites,
  LGS, SHAPING, LANKA,
  name, names, charsOf, formGlyphs, consonants, bases, descendants,
  unresolved,
};

# mnik-lankaglyphsets — Sinhala/Tamil glyph-dependency validator + OpenType feature generator

Two tools in one package, built around a single idea: **every glyph is a
dependency**. A feature rule needs its input glyphs and its output glyph to
exist in the font; the toolkit generates a broad candidate rule set, then
*validates* it against the font's actual inventory:

* **`mnik glyphsets validate`** — the dependency report: which rules are
  satisfiable, which glyphs *block* the rest (ranked by impact), which glyphs
  the font contains that **no rule consumes** (orphans, with an explanation of
  what kind of rule would consume them), plus anchor/variant findings.
* **`mnik glyphsets generate`** — emits `features.fea` containing exactly the
  satisfiable rules, and can compile them into a binary (`--compile`) or write
  them back into a Glyphs source (`--glyphs-out`) **without touching your
  hand-written features**.

```
$ mnik glyphsets validate --script sinhala --font Aggnni.glyphspackage
rules: 351 satisfiable, 29478 blocked
top blockers:
  zerowidthjoiner   blocks 29,478 rules  (akhn, rphf, vatu)
      hint: add a 'zerowidthjoiner' glyph (U+200D) — use `generate --fix-zwj`
orphaned glyphs: ka_repha-sinh — would be consumed by "sub ka-sinh repha-sinh
  by ka_repha-sinh" — blocked by missing: zerowidthjoiner
```

## Relationship to lanka-glyphsets

The [lanka-glyphsets](https://github.com/mooniak/lanka-glyphsets) repo is the
**home of the LankaGlyphset standard**: the glyphset YAML tiers
(`sinhala-0-kernel` … `sinhala-3-pro`, `tamil`) and the TypeScript name
generators. This package is the **font-side toolkit** that consumes the
standard — it bundles a copy of the YAMLs (`data/glyphsets/`) so it installs
self-contained, but the standard itself is defined *there*, not here. They
coexist; a change to the naming standard lands in lanka-glyphsets first.

## Install

```sh
cd font-directory/scripts/feature-generator
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"   # fonttools + pyyaml + glyphsLib + uharfbuzz + pytest
```

Console scripts: **`mnik`** (umbrella: `mnik glyphsets <cmd>`) and `lankafea`
(deprecated alias, forwards with a warning).

## Usage

```sh
# Dependency report (human), plus machine-readable JSON:
mnik glyphsets validate --script sinhala --font MySource.glyphspackage \
    --json report.json

# CI gate: exit 3 when blockers exist
mnik glyphsets validate --script sinhala --font My.ttf --fail-on-blockers

# Generate features gated on the font's glyphs:
mnik glyphsets generate --script sinhala --font MyFont.ttf -o features.fea

# Strip GSUB/GPOS/GDEF and compile fresh features into a binary:
mnik glyphsets generate --script tamil --font MyFont.ttf --compile out.ttf

# Add the bundled ZWJ/ZWNJ control glyphs (in place), then write features
# back into the SAME source — hand-written code is preserved:
mnik glyphsets generate --script sinhala --font MySource.glyphspackage \
    --fix-zwj --glyphs-out MySource.glyphspackage
```

`--level 0-3` picks the Sinhala glyphset tier (cumulative; Tamil ignores it).
`--no-yaml` runs standalone from the built-in codepoint tables.
`--inject DIR` merges hand-authored YAML/fea rules (gated like generated ones;
raw `.fea` passes through ungated).

## What the generator emits

Feature coverage per the [Sinhala shaping spec](https://github.com/n8willis/opentype-shaping-documents/blob/master/opentype-shaping-sinhala.md)
(script tag `sinh`; basic `akhn rphf pstf vatu`, presentation
`pres abvs blws psts`, GPOS `dist`):

| Feature | Rules |
|---|---|
| `akhn` | conjunct ligatures (`ka ් zwj ssa → kSsa`), incl. full cartesian C×C so kRa/jhRa form even without `rasign`; touching clusters (`C zwj ් C → xXaTouch`) |
| `rphf` | `ra ් zwj → repha` |
| `vatu` | `් zwj ya → yasign`, `් zwj ra → rasign`, rakar ligatures (`da + rasign → dRa`) |
| `abvs` | halant forms (`ka ් → k` — deliberately NOT in akhn, they would eat the reph/yansa triggers), i/ii vowel ligatures, yansaya+virama |
| `blws` | u/uu ligatures, da-shape `._c` below forms, yansaya+u-signs, shape-group variant selection |
| `psts` | spacing-sign ligatures, `sign+virama` (split-matra tails), **repha ligatures** (`ma + repha → ma_repha` — after the shaper repositions the reph), yansaya chains (`yasign_aasign + ් → yasign_aasign_virama`) |
| `dist` | touching-cluster advance shift |
| `aalt`/`ssNN` | from `.altN` glyphs present in the font |

Ordering rules that matter (learned the hard way, verified by HarfBuzz tests):
halant forms in abvs, repha ligatures in psts (last presentation feature, so
blws-formed carriers like `dU` exist), rakar ligatures in vatu (basic stage,
so `kRa` exists before vowel ligatures run).

### Architecture range: Abhaya ↔ Noto

Fonts legitimately range between two poles — **Abhaya Libre** (descriptive:
every outcome a precomposed glyph selected by GSUB) and **Noto Sans Sinhala**
(optimised: compact inventory, shape-group classes select sign variants,
GPOS mark attachment from anchors). The toolkit adapts by *presence*, not a
mode switch: precomposed candidates survive gating where the glyphs exist;
where the font instead has `sign.altN` variants, classes are **harvested from
the Glyphs source** and class-gated selection rules are emitted
(`sub @uSignAlt2Group usign' by usign.alt2`). Variants with no selecting
class, and signs with neither ligatures nor `_anchor` pairs, are reported by
the validator instead of guessed. `mark`/`mkmk` are **not** generated —
Glyphs auto-builds them from anchors at export.

## Glyphs sources

* `--font` accepts `.glyphs` and `.glyphspackage`; packages are read/written
  **natively** (`glyphspackage.py` owns the layout — `fontinfo.plist`,
  `order.plist`, capital-escaped `glyphs/*.glyph` — and delegates plist
  content to glyphsLib). `--glyphs-out X.glyphspackage` writes a real package.
* **Preservation**: only features/prefixes carrying the ownership marker
  (`# lankafea:generated v1 …`) and classes listed in the `lankafea-manifest`
  prefix are replaced on rewrite. Everything hand-written survives
  byte-identical. A hand-written feature whose tag we also generate is a
  *collision*: interactively you choose keep/replace per tag; non-interactive
  runs keep yours and warn; `--replace-tags a,b` / `--keep-tags a,b` predecide.
* `--fix-zwj` inserts the bundled, hand-authored ZWJ/ZWNJ control glyphs
  (`data/glyphs/*.glyph`, zero-width, layers remapped to your masters). A font
  without a real ZWJ glyph cannot match `් zwj` sequences — this is the #1
  blocker the validator finds in the fontmaster collection.

## Architecture

```
scripts.py     ScriptProfile + per-script codepoint tables
yamlloader.py  glyphset YAML -> typed specs
names.py       glyph-name construction (the ONLY namer)
nameparse.py   name -> meaning (inverse; powers orphan explanations)
inventory.py   glyph order + cmap + anchors + harvested classes
generators.py  per-feature candidate rules (broad; gated later)
adaptation.py  shape-group variant selection + anchor findings
injection.py   merge inject/*.yaml + *.fea (pre-gating)
aliases.py     adopt font's own control-glyph names (zwj)
validation.py  dependency analysis: analyze/gate/Blocker/Orphan/report
orphans.py     unconsumed-glyph detection + narratives
model.py       engine-agnostic IR
assembler.py   canonical feature order + serialize (text backend default)
compile.py     strip GSUB/GPOS/GDEF + compile into binary
glyphspackage.py  native .glyphspackage read/write
glyphsource.py    Glyphs-source inventory + preserving feature writeback
zwjfix.py      --fix-zwj control-glyph insertion
verify.py      feaLib syntax check + uharfbuzz shaping assertions
api.py         build_fea() / validate_font()  ;  cli.py  argparse CLI
```

Glyphset resolution: `MNIK_GLYPHSETS_DIR` (or legacy `LANKAFEA_GLYPHSETS_DIR`)
→ bundled package data → repo `glyphsets/`.

## Verify

```sh
.venv/bin/python -m pytest tests/ -q
```

31 tests: naming fidelity, validator blockers/orphans/JSON, HarfBuzz shaping
end-to-end (`ඛි→khI`, `ක්‍ෂ→kSsa`, `ර්‍ම→ma_repha`, `ම්‍යු→yasign_usign`,
`ක්‍ර→kRa`, Tamil equivalents), package roundtrip, preservation/collision
semantics, variant-class matching.

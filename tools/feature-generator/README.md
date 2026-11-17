# lankafea — Sinhala/Tamil glyph-dependency validator + OpenType feature generator

Two tools in one package, built around a single idea: **every glyph is a
dependency**. A feature rule needs its input glyphs and its output glyph to
exist in the font; the toolkit generates a broad candidate rule set, then
*validates* it against the font's actual inventory:

* **`lankafea validate`** — the dependency report: which rules are
  satisfiable, which glyphs *block* the rest (ranked by impact), which glyphs
  the font contains that **no rule consumes** (orphans, with an explanation of
  what kind of rule would consume them), plus anchor/variant findings.
* **`lankafea generate`** — emits `features.fea` containing exactly the
  satisfiable rules, and can compile them into a binary (`--compile`) or write
  them back into a Glyphs source (`--glyphs-out`) **without touching your
  hand-written features**.

```
$ lankafea validate --script sinhala --font Aggnni.glyphspackage
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
(`sinhala-0-kernel` … `sinhala-3-pro`, `tamil-0-kernel` … `tamil-2-pro`) and the TypeScript name
generators. This package is the **font-side toolkit** that consumes the
standard — it bundles a copy of the YAMLs (`data/glyphsets/`) so it installs
self-contained, but the standard itself is defined *there*, not here. They
coexist; a change to the naming standard lands in lanka-glyphsets first.

This package used to live in lanka-glyphsets (`tools/feature-generator/`) and
moved here, with its history, so that repo holds only the standard. Building
from source reads the YAMLs from a **sibling checkout**:

```
<workspace>/
  lanka-glyphsets/glyphsets/*.yaml      ← canonical standard
  sinhala-font-tools/tools/feature-generator/   ← this package
```

Point `LANKAFEA_GLYPHSETS_DIR` at a `glyphsets/` directory to use another
location (honoured by both `setup.py` and `lankafea` at runtime).

## Install

```sh
cd sinhala-font-tools/tools/feature-generator
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"   # fonttools + pyyaml + glyphsLib + uharfbuzz + pytest
```

Console script: **`lankafea`** (installed by the `mnik-lankafea` PyPI package)
(deprecated alias, forwards with a warning).

## Usage

```sh
# Dependency report (human), plus machine-readable JSON:
lankafea validate --script sinhala --font MySource.glyphspackage \
    --json report.json

# CI gate: exit 3 when blockers exist
lankafea validate --script sinhala --font My.ttf --fail-on-blockers

# Generate features gated on the font's glyphs:
lankafea generate --script sinhala --font MyFont.ttf -o features.fea

# Strip GSUB/GPOS/GDEF and compile fresh features into a binary:
lankafea generate --script tamil --font MyFont.ttf --compile out.ttf

# Add the bundled ZWJ/ZWNJ control glyphs (in place), then write features
# back into the SAME source — hand-written code is preserved:
lankafea generate --script sinhala --font MySource.glyphspackage \
    --fix-zwj --glyphs-out MySource.glyphspackage
```

`--level` picks the glyphset tier. **Sinhala** 0–3 chooses which tiers are loaded
(cumulative). **Tamil** 0–2 (Kernel / Core / Pro; a higher value means 2) only sets how
much of the standard the font is *required* to have: the rules are always generated from
every tier, and the level decides what the validator reports as missing. Default: all.
`--no-yaml` runs standalone from the built-in codepoint tables.

### Tamil

```sh
# What the standard asks for at Core level, and how each form is met:
lankafea validate --script tamil --level 1 --font MySource.glyphspackage

# A font not yet migrated to the standard's names: say which glyph is which.
# --adopt-legacy-names finds the deterministic renames (nna2 -> nnna, a dot-suffix on
# the other side of the namespace); --aliases names the rest.
lankafea validate --script tamil --font Old.glyphspackage \
    --adopt-legacy-names --aliases old-names.yaml
```

```yaml
# old-names.yaml — standard name: this font's name. Which numbered isign.altN is which
# shape group differs from font to font, so it cannot be derived.
isign-taml.ka: isign.alt5-taml
isign-taml.pa: isign.alt7-taml
```

A consonant + sign **form** is met by its own glyph (`kI-taml`) **or** by the sign's
shape-group alternate (`isign-taml.ka`): a font that draws ி with ligatures is not told
it lacks the alternate, and the reverse. A consonant in no group of a sign takes the plain
sign, so there is nothing to draw. The report says how each required form is met (this is
Ralex's source, with its alias table):

```
Tamil forms required at level 2: 79 — 40 by their own glyph, 28 by a shape-group alternate, 11 unmet
  unmet: jU-taml
  unmet: jUu-taml
  unmet: ssU-taml
  …
```

Where a form has a second route the unmet line says so: `unmet: kI-taml (or isign-taml.ka)`.

A designer narrows a shape group by defining a class of the same name in the source
(`@isign_ma = [ma-taml sha-taml ha-taml]`): a font that draws ஜி றி ழி as ligatures says so.
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

### Tamil

Tamil has its own model (`tamil.py`), not the Sinhala one with switches off: a syllable
never needs a joiner, and there is no reph, rakar, yansa, touching cluster or consonant +
consonant conjunct. About 140 candidate rules, not the ~8,200 the Sinhala model made for it.

| Feature | Rules |
|---|---|
| `akhn` | `க்ஷ` (`ka ் ssa → kSsa`) and `ஸ்ரீ` / `ஶ்ரீ` (`sa|sha ் ra ீ → shree`, one glyph for both spellings) |
| `abvs` | pulli forms (`ka ் → k`, where the font draws them); ி/ீ ligatures (`ka isign → kI`); then the shape-group alternates (`sub @isign_ka isign' by isign-taml.ka`) |
| `psts` | ு/ூ ligatures (`ka usign → kU`); then the hook alternate (`@usign_pa`: ங ப ய வ) |
| `ss09` | the traditional (pre-1978) orthography, kept out of the default features: ணா னா றா, ணை னை லை ளை (ை comes before its consonant after reordering), the `ai` alternate, and `ra-taml.alt` before pulli / anusvara / ி / ீ |

Ligatures are registered before the alternates, so a dedicated glyph beats the shape-group
one. Only the forms the standard enumerates are *required*; every other form is generated
too (Abhaya draws `nnI`, `kIi` …) but only when the font has its glyph, and a missing one
is never reported.

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
* **Non-exporting glyphs are ignored.** A glyph with Glyphs' *Export* switch off
  (`export = 0;`) is not in the compiled font, so it is treated as absent: it
  doesn't gate rules in, claim a codepoint, count as an `.altN` alternate, or
  stay in a harvested class. The validator reports one that blocks rules as
  "present in the source but marked non-exporting" rather than plain missing.
  The Glyphs plugin applies the same rule to the open font and re-generates
  (in auto mode) when you toggle Export.
* **Preservation**: only features/prefixes carrying the ownership marker
  (`# lankafea:generated v1 …`) and classes listed in the `lankafea-manifest`
  prefix are replaced on rewrite. Everything hand-written survives
  byte-identical. A hand-written feature whose tag we also generate is a
  *collision*: interactively you choose keep/replace per tag; non-interactive
  runs keep yours and warn; `--replace-tags a,b` / `--keep-tags a,b` predecide.
* **Both scripts in one source** (Abhaya Libre has Sinhala and Tamil, with `akhn`
  twice). Generate one script, then the other: only that script's generated code and
  classes are replaced; the class manifest and the `Languagesystems` prefix are merged;
  and a hand-written feature collides only if it can affect that script, so
  `--replace-tags akhn` for Tamil removes the `script taml;` one and keeps the Sinhala
  one. In such a source (or with `--scope-scripts on`) generated code is wrapped in
  `script taml; … script tml2; …` so one script's rules are not registered for the
  other. Single-script sources are written exactly as before.
* `--fix-zwj` inserts the bundled, hand-authored ZWJ/ZWNJ control glyphs
  (`data/glyphs/*.glyph`, zero-width, layers remapped to your masters). A font
  without a real ZWJ glyph cannot match `් zwj` sequences — this is the #1
  blocker the validator finds in the fontmaster collection.

## Architecture

```
scripts.py     ScriptProfile + per-script codepoint tables
yamlloader.py  glyphset YAML -> typed specs (tiers, shape groups, Grantha)
names.py       glyph-name construction (the ONLY namer); split_ns reads both
               positions of a dot-suffix
nameparse.py   name -> meaning (inverse; powers orphan explanations)
inventory.py   glyph order + cmap + anchors + harvested classes
generators.py  per-feature candidate rules, Sinhala model (broad; gated later)
tamil.py       the Tamil model: forms met by a ligature OR a shape-group
               alternate, ss09 traditional forms, requirement resolver
ownership.py   what is ours to rewrite in a Glyphs source, per script
adaptation.py  shape-group variant selection + anchor findings
injection.py   merge inject/*.yaml + *.fea (pre-gating)
aliases.py     adopt the font's own names (zwj; --aliases; legacy Tamil names)
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

Glyphset resolution: `LANKAFEA_GLYPHSETS_DIR` (or legacy `MNIK_GLYPHSETS_DIR`)
→ bundled package data → sibling `lanka-glyphsets/glyphsets/`.

## Verify

```sh
.venv/bin/python -m pytest tests/ -q
```

127 tests: naming fidelity, validator blockers/orphans/JSON, HarfBuzz shaping
end-to-end (`ඛි→khI`, `ක්‍ෂ→kSsa`, `ර්‍ම→ma_repha`, `ම්‍යු→yasign_usign`,
`ක්‍ර→kRa`), package roundtrip, preservation/collision semantics, variant-class
matching, and for Tamil: both routes shaped (`கி→kI-taml` or `ka-taml isign-taml.ka`),
`ss09`, the either/or reporting, anchors, aliases, both scripts in one source, and the
Glyphs plugin's own writeback against a stand-in Glyphs API.

**Acceptance** (needs the sibling `font-repos` checkout; skipped without it): for Ralex,
Yaldevi and Abhaya Libre, shape the 24 × 13 consonant × sign grid plus the Tamil test texts
with the hand-written features and with the generated ones, and require every difference to
be explained:

```sh
.venv/bin/python tests/acceptance_tamil.py [ralex|yaldevi|abhaya]
```

Abhaya Libre matches exactly (default features and `ss09`). Ralex and Yaldevi differ only
where a glyph the font already has is now reachable (a ligature its own features never form,
or Yaldevi's `kSsa`/`shree` in its stale build); see the report for the glyphs.

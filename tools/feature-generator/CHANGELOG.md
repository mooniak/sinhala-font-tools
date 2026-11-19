# Changelog

All notable changes to the **`mnik-lankafea`** PyPI package are documented here.
Once Tier 2 (Release Please) is enabled, entries below are generated from
Conventional Commits — see [../../docs/versioning.md](../../docs/versioning.md).

## Unreleased

- **Per-font settings file** (`sources/lankafea.yaml`, found beside the source; `--config`,
  `--no-config`): one section per script with `inject`, `assign`, `dist`, `numerals` and
  `featureNames`. See `docs/font-config.md`. First used by Abhaya Libre.
- **New generators** (presence-gated, so a font without the glyphs gets nothing):
  - `RakarSignVariants` (`blws`): ු/ූ take `usign.rasign` / `uusign.rasign` after a rakar
    ligature with no drawn u/uu form (`kRa usign → kRa usign.rasign`).
  - Yansaya Da forms in `DaShape` (ss01): `dya._c`, `dy._c`, `dyaa._c`, `dyaa_virama._c`,
    `dyU._c`, `dyUu._c`, matched whether the yansaya already carries its vowel or not.
  - `AnusvaraSha` (`dlig` by default): ං + ශ and its forms → `anusvarayaSha` ….
  - `FaAlternates`: every ෆ form → its ප + f alternate (`fa → fpa`, `fU → fpU` …) in the
    stylistic set the standard lists them under (ss02 Fa).
  - Numeral sets, only when a font routes them (`numerals:`): ASCII digits → Lith digits,
    the Lith ten-ligatures, ASCII digits → archaic numbers. Registered for DFLT and latn as
    well as sinh, because a run of ASCII digits is shaped as DFLT.
- **`dist` amount** comes from the font settings (default −90).
- **Stylistic set names**: `featureNames` from the font settings, else the standard's name
  for the set ("ss01 Da Forms" → "Da Forms"); a set made by routing is named too.
- **`rlig`** has a place in the canonical feature order (after `psts`).
- **Writing back into the source itself only changes its layout code**: `--glyphs-out` with
  the source's own path replaces the `classes`, `featurePrefixes` and `features` blocks of
  the existing file and leaves every other byte alone (a glyphsLib round trip re-quotes
  names, rewrites master metrics and `order.plist`). Writing to another path is as before.
- The standard's stylistic sets are read whether they are nested under "Stylistic
  alternates" (ss01) or a category of their own (ss02 Fa, ss03 in `sinhala-3-pro.yaml`).
- The new candidate rules, and the existing `_virama` Da-form spellings, are optional:
  they no longer show up as blockers in `validate`.
- **Sinhala acceptance** reads the font's settings file, and its synthetic font now has the
  source's advances and glyphsLib's GDEF classes, so mark filtering and zero-width glyphs
  (`touch-sinh`) behave as in the real build. Its numbers match a HarfBuzz comparison of two
  real Abhaya builds exactly.
- **Da forms are optional now** (breaking for fonts that relied on the old default): the
  below-base `._c` forms on da-shaped bases (`daa._c`, `nyaa._c`, `nDaa._c` …) used to be
  generated into default `blws`/`psts`, so දා always became `daa._c`. The standard lists them
  under **ss01 Da Forms**, and they now go in one `DaShape` lookup in that stylistic set (the
  tag is read from the standard). A font that wants them under `dlig` too copies the group
  with `assign`. The virama tail of ෝ is matched both as `aasign_virama` (formed by `psts`
  before a stylistic set runs) and as `aasign` + `virama`, so දෝ gives `daa_virama._c` under
  the set. Abhaya Libre refactor plan item G6.
- **Sinhala acceptance** (`tests/acceptance_sinhala.py`, `test_sinhala_acceptance.py`): compiles
  a font's hand-written features and the generated ones into one synthetic font and compares
  their shaping over a corpus built from the standard, plus the test texts, for the default
  features and each stylistic feature. Differences are sorted into the known items of the
  Abhaya Libre refactor plan; any that fit no item fail the test. `--freeze` keeps a copy of the
  hand-written features as the baseline, for when the source no longer has them.
- **`migrate` renames Sinhala glyphs too**: `--aliases` may target any name in the standard's
  `-sinh` or `-taml` namespace (anchors are still renamed on Tamil glyphs only). First used for
  Abhaya Libre's Lith digits (`sinZerolith` → `lithzero-sinh`, alias table in
  `tests/fixtures/sinhala-aliases/abhaya.yaml`).
- **Fix:** an inject rule with context and several outputs (`sub: [touch, "ka_repha'"], by: [ka,
  repha-sinh.001]`) was taken for a ligature and written as invalid `.fea`. It is now a
  contextual multiple substitution, and a contextual single or ligature rule is classed by its
  marked inputs. First used for Abhaya Libre's touching-cluster repaya
  (`sources/lankafea/touch-reph.yaml` in that repo); the Sinhala acceptance test reads a
  font's inject directory.
- **Fix:** `migrate` left a renamed glyph unquoted when its new name needs quotes in a plist
  (`glyphname = lithzero-sinh;`). It now writes `"lithzero-sinh"`, the way Glyphs does.
- **`python -m lankafea.migrate`** renames a Tamil `.glyphspackage` to the standard's glyph
  and anchor names (dry run by default, `--apply` to write; undo with git). Glyph renames come
  from `--aliases` / `--adopt-legacy-names` and are applied by whole name across glyphs,
  components, classes, features and `order.plist`; legacy anchors (`Anchor-N`) become `virama`
  / `isign` / `iisign` / `usign` / `uusign`, read from the sign glyphs themselves. Works on a
  `.glyphspackage` or a single `.glyphs` file (both anchor formats); only Tamil glyphs have
  anchors renamed. First used on Ralex and Vineetha.
  `--no-anchors` renames glyphs only. Anchor clashes (two legacy anchors that would become
  the same name, as in Yaldevi) are reported as problems instead of written; a stylistic
  alternate keeps its own anchor. **Fix:** `uusign` took `_usign` when it shared a legacy
  anchor with `usign`; unquoted anchor names (`name = _MatraI.alt3;`) were not seen.
- **`migrate --adopt-legacy-names`** also moves every remaining `stem.suffix-taml` to
  `stem-taml.suffix` (Yaldevi's own extras: `iisign.alt2-taml`, `rI.alt-taml`), and renames anchors
  only on the standard's own shape-group alternates.
- **Fix:** writing features back into a package dropped an explicit master `name`
  (Yaldevi's `ExtraLight` master came back as "Light Extra" and renamed its UFO); it is now kept.
- **Fix:** writing features back into a package renamed every glyph whose name starts with a
  dot (`.part.al_comp` was saved as `.part.al_comp.glyph` instead of Glyphs' `_part.al_comp.glyph`),
  leaving a duplicate file in the source.
- **Tamil has its own model** (`tamil.py`), replacing the Sinhala one run with a few
  switches off, for the LankaGlyphset standard 1.0.0 (`tamil-{0-kernel,1-core,2-pro}.yaml`,
  which replace `tamil.yaml`). A consonant + sign form is met by its own glyph **or** by the
  sign's shape-group alternate, so a font is not asked for the route it did not take. About
  140 candidate rules instead of ~8,200. `akhn`: க்ஷ, ஸ்ரீ / ஶ்ரீ; `abvs`: ி/ீ; `psts`: ு/ூ
  (was routed to `blws`); the traditional orthography in `ss09`, never in the default
  features. The report lists each required form and how it is met.
- **`--level` means something for Tamil**: 0–2 sets how much of the standard is required.
- **Fixes:** ன is `nnna` (the old `nna2` produced `nna2a-taml`); Tamil `.alt` glyphs are no
  longer turned into `ss01`–`ss07`.
- **Anchors:** the Tamil sign anchors (`isign`/`_isign` …) are checked, accepting the legacy
  names (`tm_halant`, `MatraI.altN`) and reading `Anchor-N` from the mark glyph; only a
  consonant with no dedicated glyph for a sign needs the anchor.
- **R1 — both scripts in one source.** Ownership, the class manifest, the `Languagesystems`
  prefix and hand-written collisions are per script (`ownership.py`), so Sinhala and Tamil
  can be generated one after the other; generated code is scoped with `script taml;` in such
  a source (`--scope-scripts`). The Glyphs plugin uses the same rules (`script=`).
- **R2 — variants.** Both positions of a dot-suffix (`a.alt-sinh`, `a-sinh.alt`) are
  recognised by the alternate finder, the Noto adaptation, orphan detection and the name
  parser; numbered `.001` variants are described rather than missed. `--aliases FILE` and
  `--adopt-legacy-names` check a font before it is migrated to the standard's names.
  **This changes Sinhala output.** A font whose alternates are named after the namespace
  (`fa-sinh.alt`, `isign-sinh.alt1`: Maname, Dinamina, Aggnni) used to get rules built from
  names like `fa-sinh-sinh` that matched nothing, so they were dropped and listed as bogus
  blockers. They now produce working `aalt` / `ssNN` rules. Orphan detection also sees glyphs
  with that suffix, so it reports more of them (`rasign-sinh.long`, `ka_repha-sinh.001`).
  Fonts with the older spelling (`fa.alt-sinh`), and Abhaya Libre, generate the same `.fea`.
- A class lankafea wrote itself is no longer harvested as the designer's from a Glyphs source.
- `setup.py` removes bundled glyphset files the standard no longer has.

- Glyphs sources and the Lanka Features plugin now ignore glyphs marked
  non-exporting (Export off): they no longer gate rules in, claim codepoints,
  appear as `.altN` alternates, or stay in harvested classes. Blockers that are
  non-exporting say so in the report. The plugin's auto-generate also reacts to
  toggling Export. `FontInventory.non_exporting` records the ignored names.
- Feature assignments: route generated rule groups (lookups) and `.altN`
  alternate indices to `dlig` / `hlig` / `liga` / `clig` / `calt` / `ssNN`
  (move or copy), via `build_fea(assign=...)`, `--assign FILE.json`, and a
  Feature Assignments dialog in the Glyphs plugin (stored in `font.userData`).

## 0.3.0

- Bundles the LankaGlyphset standard `0.3.0`, which adds Unicode values for the
  30 Sinhala numerals (lith digits + archaic numbers) in the Pro tier.

## 0.2.0

- glyph-dependency validator + OpenType (GSUB/GPOS) feature generator for Sinhala
  & Tamil fonts, presence-gated on the glyphs actually in the font. Bundles the
  LankaGlyphset standard YAMLs into the wheel at build time.

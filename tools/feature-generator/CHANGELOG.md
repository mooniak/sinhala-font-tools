# Changelog

All notable changes to the **`mnik-lankafea`** PyPI package are documented here.
Once Tier 2 (Release Please) is enabled, entries below are generated from
Conventional Commits — see [../../docs/versioning.md](../../docs/versioning.md).

## Unreleased

- **`python -m lankafea.migrate`** renames a Tamil `.glyphspackage` to the standard's glyph
  and anchor names (dry run by default, `--apply` to write; undo with git). Glyph renames come
  from `--aliases` / `--adopt-legacy-names` and are applied by whole name across glyphs,
  components, classes, features and `order.plist`; legacy anchors (`Anchor-N`) become `virama`
  / `isign` / `iisign` / `usign` / `uusign`, read from the sign glyphs themselves. Works on a
  `.glyphspackage` or a single `.glyphs` file (both anchor formats); only Tamil glyphs have
  anchors renamed. First used on Ralex and Vineetha.
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

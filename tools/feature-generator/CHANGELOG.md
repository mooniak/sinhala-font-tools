# Changelog

All notable changes to the **`mnik-lankafea`** PyPI package are documented here.
Once Tier 2 (Release Please) is enabled, entries below are generated from
Conventional Commits — see [../../docs/versioning.md](../../docs/versioning.md).

## Unreleased

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

# Changelog

All notable changes to the **`mnik-lankafea`** PyPI package are documented here.
Once Tier 2 (Release Please) is enabled, entries below are generated from
Conventional Commits — see [../../docs/versioning.md](../../docs/versioning.md).

## 0.3.0

- Bundles the LankaGlyphset standard `0.3.0`, which adds Unicode values for the
  30 Sinhala numerals (lith digits + archaic numbers) in the Pro tier.

## 0.2.0

- glyph-dependency validator + OpenType (GSUB/GPOS) feature generator for Sinhala
  & Tamil fonts, presence-gated on the glyphs actually in the font. Bundles the
  LankaGlyphset standard YAMLs into the wheel at build time.

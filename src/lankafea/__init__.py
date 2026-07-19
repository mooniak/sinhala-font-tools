"""lankafea — OpenType feature generator for LankaGlyphset Sinhala & Tamil fonts.

Pipeline (see the project plan): YAML glyphsets + a target font's glyph inventory
-> candidate substitution/positioning rules -> presence-gating -> features.fea
(always) -> optional strip-and-recompile into a .ttf/.otf.

Public entry points live in :mod:`lankafea.api`.
"""

__version__ = "0.2.0"  # x-release-please-version

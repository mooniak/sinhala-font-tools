"""Read a font's glyph inventory — the presence gate for rule emission.

Mirrors the pattern in ``tools/font-coverage/font_coverage.py``. Gating is done on
the glyph ORDER (never cmap): precomposed ligature outputs such as ``kSsa-sinh`` are
legitimately unencoded but must still be treated as present.

The inventory also carries the cp→name cmap mapping (for ZWJ aliasing and
orphan detection) and, for Glyphs sources, per-glyph anchor names (for the
anchor-coverage validation).
"""

from __future__ import annotations

from pathlib import Path

from fontTools.ttLib import TTFont


class FontInventory:
    def __init__(self, glyphs: set[str], cmap: set[int],
                 cmap_names: dict[int, str] | None = None,
                 anchors: dict[str, set[str]] | None = None,
                 source_classes: dict[str, list[str]] | None = None,
                 glyph_info: dict[str, dict] | None = None):
        self.glyphs = glyphs
        self.cmap = cmap
        self.cmap_names = cmap_names or {}
        self.anchors = anchors or {}          # glyph name -> anchor names (Glyphs sources)
        self.source_classes = source_classes or {}  # harvested @classes (Glyphs sources)
        # glyph name -> {"category", "subCategory"} (Glyphs sources only; empty
        # for compiled binaries, which don't carry Glyphs' glyph info).
        self.glyph_info = glyph_info or {}

    @classmethod
    def from_font(cls, path: Path | str) -> "FontInventory":
        tt = TTFont(str(path), fontNumber=0, lazy=True)
        try:
            glyphs = set(tt.getGlyphOrder())
            try:
                cmap_names = dict(tt.getBestCmap())
            except Exception:
                cmap_names = {}
        finally:
            tt.close()
        return cls(glyphs, set(cmap_names.keys()), cmap_names)

    @classmethod
    def from_names(cls, names) -> "FontInventory":
        """Build an inventory directly from a set of glyph names (for tests / dry runs)."""
        return cls(set(names), set())

    def has(self, name: str) -> bool:
        return name in self.glyphs

    def name_for(self, codepoint: int) -> str | None:
        """The font's glyph name for a codepoint, if encoded."""
        return self.cmap_names.get(codepoint)

    @property
    def encoded_names(self) -> set[str]:
        return set(self.cmap_names.values())

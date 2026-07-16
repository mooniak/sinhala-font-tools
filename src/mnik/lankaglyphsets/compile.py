"""Strip existing OpenType features and compile generated ones into a font."""

from __future__ import annotations

from pathlib import Path

from fontTools.ttLib import TTFont
from fontTools.feaLib.builder import addOpenTypeFeatures


STRIP_TABLES = ("GSUB", "GPOS", "GDEF")


def strip_features(font: TTFont) -> list[str]:
    """Delete layout tables so they are rebuilt cleanly from the new .fea.

    GDEF is dropped too so mark-attachment / UseMarkFilteringSet class defs are
    regenerated consistently by feaLib.
    """
    removed = []
    for tag in STRIP_TABLES:
        if tag in font:
            del font[tag]
            removed.append(tag)
    return removed


def strip_and_build(font_path: Path | str, fea_path: Path | str,
                    out_path: Path | str) -> list[str]:
    font = TTFont(str(font_path))  # not lazy: we mutate + save
    removed = strip_features(font)
    addOpenTypeFeatures(font, str(fea_path))
    font.save(str(out_path))
    font.close()
    return removed

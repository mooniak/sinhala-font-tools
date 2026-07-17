"""Verification: static .fea syntax check + optional shaping assertions."""

from __future__ import annotations

from dataclasses import dataclass
from io import StringIO
from pathlib import Path


@dataclass
class ShapeCheck:
    text: str          # Unicode string to shape
    expect: str        # glyph name expected in the shaped output (namespaced)
    label: str = ""


@dataclass
class ShapeResult:
    check: ShapeCheck
    ok: bool
    glyphs: list[str]


def check_syntax(fea_text: str, glyph_names: set[str]) -> None:
    """Parse the .fea against a glyph set; raises FeatureLibError on bad syntax."""
    from fontTools.feaLib.parser import Parser
    Parser(StringIO(fea_text), glyphNames=set(glyph_names)).parse()


def shape_checks(font_path: Path | str, checks: list[ShapeCheck]) -> list[ShapeResult]:
    """Shape each check with HarfBuzz; assert the expected glyph appears.

    Requires uharfbuzz (optional dependency). Reuses the same default-feature shaping
    approach as tools/font-coverage/font_coverage.py.
    """
    import uharfbuzz as hb

    blob = hb.Blob.from_file_path(str(font_path))
    face = hb.Face(blob)
    font = hb.Font(face)

    results: list[ShapeResult] = []
    for chk in checks:
        buf = hb.Buffer()
        buf.add_str(chk.text)
        buf.guess_segment_properties()
        hb.shape(font, buf, {})
        names = [font.glyph_to_string(i.codepoint) for i in buf.glyph_infos]
        results.append(ShapeResult(chk, chk.expect in names, names))
    return results

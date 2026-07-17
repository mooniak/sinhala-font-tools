"""Native .glyphspackage read/write."""

from __future__ import annotations

from lankafea.glyphspackage import (
    escape_glyph_filename, read_glyphspackage, unescape_glyph_filename,
    write_glyphspackage,
)
from lankafea.scripts import get_profile

from make_font import build_test_glyphs_source


def test_filename_escaping():
    # Verified against Glyphs.app's own package output (aggnni).
    assert escape_glyph_filename("tTha_repha-sinh") == "tT_ha_repha-sinh"
    assert escape_glyph_filename("lU-sinh") == "lU_-sinh"
    assert escape_glyph_filename("ka-sinh") == "ka-sinh"
    for name in ("tTha_repha-sinh", "lU-sinh", "kSsa-sinh", "a-sinh", "kRIi-sinh"):
        assert unescape_glyph_filename(escape_glyph_filename(name)) == name


def test_package_roundtrip(tmp_path):
    profile = get_profile("sinhala", 3)
    src = build_test_glyphs_source(profile, tmp_path / "src.glyphspackage")

    font = read_glyphspackage(src)
    names = [g.name for g in font.glyphs]
    assert "kSsa-sinh" in names and len(names) > 100

    out = tmp_path / "rt.glyphspackage"
    write_glyphspackage(font, out)
    font2 = read_glyphspackage(out)
    assert [g.name for g in font2.glyphs] == names
    assert {g.name: g.unicode for g in font2.glyphs} == \
           {g.name: g.unicode for g in font.glyphs}

    # glyphsLib's own package loader agrees.
    from glyphsLib import GSFont
    assert [g.name for g in GSFont(str(out)).glyphs] == names


def test_rewrite_only_touches_changed_files(tmp_path):
    profile = get_profile("sinhala", 3)
    src = build_test_glyphs_source(profile, tmp_path / "src.glyphspackage")
    font = read_glyphspackage(src)
    out = tmp_path / "w.glyphspackage"
    write_glyphspackage(font, out)

    target = out / "glyphs" / "ka-sinh.glyph"
    before = target.stat().st_mtime_ns
    write_glyphspackage(read_glyphspackage(out), out)     # no content change
    assert target.stat().st_mtime_ns == before

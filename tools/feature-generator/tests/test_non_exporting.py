"""Glyphs marked non-exporting ("Export" off) must be invisible to generation.

A non-exporting glyph is absent from the compiled font, so a rule that names it
would fail to compile (or be silently dropped by Glyphs). The inventory has to
treat it exactly like a glyph that isn't there.
"""

from __future__ import annotations

import pytest

from lankafea.api import build_fea, validate_font
from lankafea.glyphsource import inventory_from_glyphs
from lankafea.glyphspackage import load_source, save_source
from lankafea.scripts import get_profile
from lankafea.validation import NON_EXPORTING_HINT

from make_font import build_test_glyphs_source

LIGATURE = "kSsa-sinh"     # output of the ka + virama + ZWJ + ssa akhn rule


def _source(tmp_path, ext, edit):
    """A test source; ``edit(font)`` is applied before the final save."""
    profile = get_profile("sinhala", 3)
    src = build_test_glyphs_source(profile, tmp_path / f"src{ext}")
    font = load_source(src)
    edit(font)
    save_source(font, src)
    return src


def _glyph(font, name):
    return next(g for g in font.glyphs if g.name == name)


@pytest.fixture(params=[".glyphs", ".glyphspackage"])
def ext(request):
    return request.param


def test_baseline_exports_everything(tmp_path, ext):
    """Control: with Export on, the ligature is in the inventory and the rules."""
    src = _source(tmp_path, ext, lambda font: None)
    inv = inventory_from_glyphs(src)
    assert LIGATURE in inv.glyphs
    assert inv.non_exporting == set()
    assert LIGATURE in build_fea("sinhala", inv, level=3).fea


def test_non_exporting_glyph_is_left_out_of_the_inventory(tmp_path, ext):
    src = _source(tmp_path, ext,
                  lambda font: setattr(_glyph(font, LIGATURE), "export", False))
    inv = inventory_from_glyphs(src)
    assert LIGATURE not in inv.glyphs
    assert LIGATURE not in inv.glyph_info
    assert inv.non_exporting == {LIGATURE}


def test_rules_naming_a_non_exporting_glyph_are_dropped(tmp_path, ext):
    src = _source(tmp_path, ext,
                  lambda font: setattr(_glyph(font, LIGATURE), "export", False))
    result = build_fea("sinhala", inventory_from_glyphs(src), level=3)
    assert LIGATURE not in result.fea
    # …and the report names it as the blocker, with the reason.
    blocker = next(b for b in result.report.blockers if b.glyph == LIGATURE)
    assert blocker.hint == NON_EXPORTING_HINT


def test_validate_font_flags_the_same_blocker(tmp_path, ext):
    src = _source(tmp_path, ext,
                  lambda font: setattr(_glyph(font, LIGATURE), "export", False))
    report = validate_font("sinhala", inventory_from_glyphs(src), level=3)
    blocker = next(b for b in report.blockers if b.glyph == LIGATURE)
    assert blocker.hint == NON_EXPORTING_HINT


def test_truly_missing_glyph_keeps_its_own_hint(tmp_path, ext):
    """Only non-exporting glyphs get the Export hint, not every blocker."""
    def drop_zwj(font):
        font.glyphs = [g for g in font.glyphs if g.name != "zerowidthjoiner"]

    src = _source(tmp_path, ext, drop_zwj)
    result = build_fea("sinhala", inventory_from_glyphs(src), level=3)
    blocker = next(b for b in result.report.blockers if b.glyph == "zerowidthjoiner")
    assert blocker.hint and blocker.hint != NON_EXPORTING_HINT


def test_non_exporting_glyph_does_not_claim_a_codepoint(tmp_path, ext):
    """A non-exporting stand-in encoded at U+0D9A must not shadow the real glyph
    (cmap_names keeps the first claimant, so the decoy is placed ahead of it)."""
    from glyphsLib.classes import GSGlyph

    def edit(font):
        _glyph(font, "ka-sinh").unicode = "0D9A"
        decoy = GSGlyph("decoy-notexported")
        decoy.unicode = "0D9A"
        decoy.export = False
        font.glyphs = [decoy] + list(font.glyphs)

    src = _source(tmp_path, ext, edit)
    inv = inventory_from_glyphs(src)
    assert inv.cmap_names[0x0D9A] == "ka-sinh"
    assert "decoy-notexported" not in inv.glyphs


def test_non_exporting_members_are_pruned_from_source_classes(tmp_path, ext):
    from glyphsLib.classes import GSClass

    def edit(font):
        font.classes.append(GSClass("MyShapes", "ka-sinh kha-sinh ga-sinh"))
        _glyph(font, "kha-sinh").export = False

    src = _source(tmp_path, ext, edit)
    inv = inventory_from_glyphs(src)
    assert inv.source_classes["MyShapes"] == ["ka-sinh", "ga-sinh"]


def test_alternates_that_do_not_export_are_not_offered(tmp_path, ext):
    """`.altN` discovery reads inventory.glyphs, so it inherits the filter."""
    from glyphsLib.classes import GSGlyph

    def edit(font):
        for name, export in (("ka-sinh.alt1", True), ("kha-sinh.alt1", False)):
            g = GSGlyph(name)
            g.export = export
            font.glyphs.append(g)

    src = _source(tmp_path, ext, edit)
    inv = inventory_from_glyphs(src)
    assert "ka-sinh.alt1" in inv.glyphs
    assert "kha-sinh.alt1" not in inv.glyphs
    assert "kha-sinh.alt1" in inv.non_exporting

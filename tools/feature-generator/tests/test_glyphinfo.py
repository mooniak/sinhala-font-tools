"""Glyph-info validator: Sinhala dependent vowel signs must be spacing marks."""

from __future__ import annotations

import json

from lankafea.glyphinfo import (SPACING_MARK_GLYPHS, check_glyph_info)
from lankafea.glyphsource import inventory_from_glyphs


# ---- unit: the check itself ---------------------------------------------- #

def test_unset_and_wrong_info_are_flagged():
    present = {"aesign-sinh", "esign-sinh", "yasign-sinh", "ka-sinh"}
    glyph_info = {
        "aesign-sinh": {"category": None, "subCategory": None},            # unset
        "esign-sinh": {"category": "Letter", "subCategory": "Spacing"},    # wrong cat
        "yasign-sinh": {"category": "Mark", "subCategory": "Nonspacing"},  # wrong sub
        "ka-sinh": {"category": "Letter", "subCategory": None},            # not a target
    }
    res = check_glyph_info(present, glyph_info)
    assert res["available"] is True
    assert res["present"] == 3          # ka-sinh is not a target sign
    assert res["ok"] == 0
    flagged = {f["glyph"] for f in res["findings"]}
    assert flagged == {"aesign-sinh", "esign-sinh", "yasign-sinh"}
    reasons = {f["glyph"]: f["reason"] for f in res["findings"]}
    assert "unset" in reasons["aesign-sinh"]
    assert "Category=Letter" in reasons["esign-sinh"]
    assert "Subcategory=Nonspacing" in reasons["yasign-sinh"]


def test_correct_info_passes():
    present = {"aesign-sinh", "osign-sinh"}
    glyph_info = {g: {"category": "Mark", "subCategory": "Spacing"} for g in present}
    res = check_glyph_info(present, glyph_info)
    assert res["present"] == 2 and res["ok"] == 2 and res["findings"] == []


def test_absent_targets_are_ignored():
    res = check_glyph_info(set(), {"whatever": {"category": "Mark", "subCategory": "Spacing"}})
    assert res["present"] == 0 and res["findings"] == []


def test_binary_font_without_glyph_info_is_skipped():
    # present targets but no per-glyph info (a compiled .ttf) -> not assessable
    res = check_glyph_info(set(SPACING_MARK_GLYPHS), glyph_info={})
    assert res["available"] is False and res["findings"] == []


# ---- integration: source read + report wiring ---------------------------- #

def test_inventory_captures_category_from_source(tmp_path):
    from glyphsLib.classes import GSFont, GSGlyph, GSFontMaster
    font = GSFont()
    font.familyName = "GlyphInfoTest"
    m = GSFontMaster(); m.name = "Regular"; font.masters.append(m)

    good = GSGlyph("aasign-sinh")
    good.category, good.subCategory = "Mark", "Spacing"
    bad = GSGlyph("aesign-sinh")                       # left unset
    font.glyphs.extend([good, bad])

    from lankafea.glyphspackage import save_source
    out = tmp_path / "glyphinfo.glyphs"
    save_source(font, out)

    inv = inventory_from_glyphs(out)
    assert inv.glyph_info["aasign-sinh"] == {"category": "Mark", "subCategory": "Spacing"}
    assert inv.glyph_info["aesign-sinh"] == {"category": None, "subCategory": None}

    res = check_glyph_info(inv.glyphs, inv.glyph_info)
    assert res["available"] and res["present"] == 2 and res["ok"] == 1
    assert [f["glyph"] for f in res["findings"]] == ["aesign-sinh"]


def test_report_renders_glyph_info(tmp_path):
    from lankafea.validation import ValidationReport
    r = ValidationReport()
    r.glyph_info_available = True
    r.glyph_info_present = 2
    r.glyph_info_findings = [
        {"glyph": "aesign-sinh", "category": None, "sub_category": None,
         "reason": "Category=unset (want Mark); Subcategory=unset (want Spacing)"},
    ]
    text = r.to_text()
    assert "spacing marks with wrong/unset" in text
    assert "aesign-sinh" in text
    payload = json.loads(r.to_json())
    assert payload["glyph_info"]["present"] == 2
    assert payload["glyph_info"]["findings"][0]["glyph"] == "aesign-sinh"

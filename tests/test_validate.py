"""Dependency validator: blockers, orphans, JSON report."""

from __future__ import annotations

import json

from mnik.lankaglyphsets.api import validate_font
from mnik.lankaglyphsets.inventory import FontInventory
from mnik.lankaglyphsets.scripts import get_profile

from make_font import aggnni_like_extras, build_test_font


def test_missing_zwj_is_reported_as_blocker(tmp_path):
    """A font without zerowidthjoiner must name it as the blocker for
    akhn/rphf/vatu instead of silently dropping the rules (the aggnni bug)."""
    profile = get_profile("sinhala", 3)
    font = build_test_font(profile, tmp_path / "nozwj.ttf",
                           extra_glyphs=aggnni_like_extras(profile),
                           with_zwj=False)
    inv = FontInventory.from_font(font)
    report = validate_font("sinhala", inv, level=3)

    zwj = next((b for b in report.blockers if b.glyph == "zerowidthjoiner"), None)
    assert zwj is not None, "zerowidthjoiner missing from blockers"
    assert {"akhn", "rphf", "vatu"} <= set(zwj.features)
    assert zwj.hint and "fix-zwj" in zwj.hint
    assert zwj.samples


def test_with_zwj_forms_are_satisfiable(tmp_path):
    profile = get_profile("sinhala", 3)
    font = build_test_font(profile, tmp_path / "zwj.ttf",
                           extra_glyphs=aggnni_like_extras(profile),
                           with_zwj=True)
    inv = FontInventory.from_font(font)
    report = validate_font("sinhala", inv, level=3)

    assert report.per_feature["rphf"].satisfiable == 1
    assert report.per_feature["vatu"].satisfiable >= 2   # rasign + yasign (+ rakar)
    assert not any(b.glyph == "zerowidthjoiner" for b in report.blockers)
    # The repha/yasign families are consumed -> not orphaned.
    orphaned = {o.glyph for o in report.orphans}
    assert "ka_repha-sinh" not in orphaned
    assert "yasign_usign-sinh" not in orphaned


def test_unconsumed_glyph_is_orphaned(tmp_path):
    profile = get_profile("sinhala", 3)
    font = build_test_font(profile, tmp_path / "orph.ttf",
                           extra_glyphs=["zzzunknown-sinh"], with_zwj=True)
    inv = FontInventory.from_font(font)
    report = validate_font("sinhala", inv, level=3)
    assert "zzzunknown-sinh" in {o.glyph for o in report.orphans}


def test_json_report_roundtrips(tmp_path):
    profile = get_profile("sinhala", 3)
    font = build_test_font(profile, tmp_path / "j.ttf", with_zwj=False)
    inv = FontInventory.from_font(font)
    report = validate_font("sinhala", inv, level=3)

    data = json.loads(report.to_json())
    assert set(data) == {"per_feature", "blockers", "orphans", "dead_classes",
                         "anchor_findings", "collisions", "counts", "glyph_info"}
    # a compiled binary carries no Glyphs glyph info, so the check is unavailable
    assert data["glyph_info"] == {"available": False, "present": 0, "findings": []}
    assert data["counts"]["kept_rules"] == report.kept_rules
    assert any(b["glyph"] == "zerowidthjoiner" for b in data["blockers"])
    # text report renders without error
    assert "blockers" in report.to_text() or report.blockers == []

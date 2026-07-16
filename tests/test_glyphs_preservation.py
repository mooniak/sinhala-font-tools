"""--glyphs-out preservation: hand-authored layout code must survive."""

from __future__ import annotations

import pytest

from mnik.lankaglyphsets.api import build_fea
from mnik.lankaglyphsets.glyphsource import (
    MARKER, inventory_from_glyphs, write_features_to_glyphs,
)
from mnik.lankaglyphsets.scripts import get_profile

from make_font import build_test_glyphs_source


HAND_CALT = "# my precious hand-tuned rules\nsub ka-sinh ka-sinh by kSsa-sinh;"
HAND_AKHN = "sub ka-sinh virama-sinh zerowidthjoiner ssa-sinh by kSsa-sinh;"


def _source_with_user_code(tmp_path, ext=".glyphs"):
    from glyphsLib.classes import GSClass, GSFeature, GSFeaturePrefix

    from mnik.lankaglyphsets.glyphspackage import load_source, save_source

    profile = get_profile("sinhala", 3)
    src = build_test_glyphs_source(profile, tmp_path / f"src{ext}")
    font = load_source(src)
    font.features.append(GSFeature("calt", HAND_CALT))
    font.features.append(GSFeature("akhn", HAND_AKHN))          # collides
    font.featurePrefixes.append(GSFeaturePrefix("MyPrefix", "# custom prefix"))
    font.classes.append(GSClass("MyClass", "ka-sinh kha-sinh"))
    save_source(font, src)
    return profile, src


def _build(profile, src):
    inv = inventory_from_glyphs(src)
    return build_fea("sinhala", inv, level=3, validate=True)


def test_user_code_survives_and_collision_kept(tmp_path):
    profile, src = _source_with_user_code(tmp_path)
    result = _build(profile, src)
    out = tmp_path / "out.glyphs"
    summary = write_features_to_glyphs(
        result.doc, profile.language_systems, src, out)

    assert summary["collisions"]["akhn"] == "keep"
    assert summary["preserved_features"] == 2                    # calt + akhn

    from mnik.lankaglyphsets.glyphspackage import load_source
    font = load_source(out)
    calt = next(f for f in font.features if f.name == "calt")
    assert calt.code == HAND_CALT                                # byte-identical
    akhn = next(f for f in font.features if f.name == "akhn")
    assert akhn.code == HAND_AKHN                                # user's kept
    assert any(p.name == "MyPrefix" for p in font.featurePrefixes)
    assert any(c.name == "MyClass" for c in font.classes)
    # generated features carry the ownership marker
    abvs = next(f for f in font.features if f.name == "abvs")
    assert abvs.code.startswith(MARKER)


def test_replace_tags_overrides_collision(tmp_path):
    profile, src = _source_with_user_code(tmp_path)
    result = _build(profile, src)
    out = tmp_path / "out.glyphs"
    summary = write_features_to_glyphs(
        result.doc, profile.language_systems, src, out,
        replace_tags={"akhn"})
    assert summary["collisions"]["akhn"] == "replace"

    from mnik.lankaglyphsets.glyphspackage import load_source
    font = load_source(out)
    akhn = next(f for f in font.features if f.name == "akhn")
    assert akhn.code.startswith(MARKER)


def test_second_run_is_idempotent(tmp_path):
    profile, src = _source_with_user_code(tmp_path)
    result = _build(profile, src)
    out1 = tmp_path / "out1.glyphs"
    write_features_to_glyphs(result.doc, profile.language_systems, src, out1)

    # Re-run ON the previous output: our marked code is replaced, user's kept.
    result2 = _build(profile, out1)
    out2 = tmp_path / "out2.glyphs"
    summary2 = write_features_to_glyphs(
        result2.doc, profile.language_systems, out1, out2)
    assert summary2["stripped_features"] > 0                      # ours replaced
    assert summary2["collisions"].get("akhn") == "keep"

    from mnik.lankaglyphsets.glyphspackage import load_source
    f1, f2 = load_source(out1), load_source(out2)
    tags1 = sorted(f.name for f in f1.features)
    tags2 = sorted(f.name for f in f2.features)
    assert tags1 == tags2
    assert next(f for f in f2.features if f.name == "calt").code == HAND_CALT
    # no duplicate manifest/Languagesystems prefixes accumulate
    names2 = [p.name for p in f2.featurePrefixes]
    assert names2.count("lankafea-manifest") == 1
    assert names2.count("Languagesystems") == 1


@pytest.mark.parametrize("ext", [".glyphspackage"])
def test_glyphs_out_writes_real_package(tmp_path, ext):
    profile, src = _source_with_user_code(tmp_path, ext=ext)
    result = _build(profile, src)
    out = tmp_path / f"out{ext}"
    write_features_to_glyphs(result.doc, profile.language_systems, src, out)

    assert out.is_dir(), "--glyphs-out must write a real package directory"
    assert (out / "fontinfo.plist").exists()
    assert (out / "order.plist").exists()
    assert (out / "glyphs").is_dir()
    # capital-escape filenames
    assert (out / "glyphs" / "kS_sa-sinh.glyph").exists()

    from glyphsLib import GSFont
    font = GSFont(str(out))                                       # Glyphs-compatible
    assert any(f.name == "abvs" for f in font.features)

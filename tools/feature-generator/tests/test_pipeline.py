"""End-to-end: generate -> gate -> assemble -> strip+compile -> shape."""

from __future__ import annotations

from pathlib import Path

import pytest

from lankafea.api import build_fea
from lankafea.compile import strip_and_build
from lankafea.inventory import FontInventory
from lankafea.scripts import get_profile
from lankafea.verify import shape_checks, ShapeCheck

from make_font import aggnni_like_extras, build_test_font, build_test_glyphs_source


# ---- naming unit checks (port fidelity) ----------------------------------- #

def test_name_construction():
    from lankafea.scripts import SINHALA
    from lankafea import names
    assert names.base_a(SINHALA, 0x0D9A) == "ka"
    assert names.drop_a("ka") == "k"
    assert names.cluster_stem(SINHALA, [0x0D9A, 0x0DC2], ["conj"]) == "kSsa"
    assert names.cluster_stem(SINHALA, [0x0D9A], [], vowel=0x0DD2) == "kI"


# ---- generation + gating -------------------------------------------------- #

@pytest.mark.parametrize("script,level", [("sinhala", 3), ("tamil", 0)])
def test_build_fea_valid_syntax(script, level):
    profile = get_profile(script, level)
    from lankafea.yamlloader import load_specs
    from lankafea.names import with_ns
    specs = load_specs(profile)
    names = {g.full_name for g in specs.glyphs}
    names |= {"zerowidthjoiner", with_ns("touch", profile.namespace),
              with_ns("rasign", profile.namespace), with_ns("repha", profile.namespace),
              with_ns("yasign", profile.namespace)}
    inv = FontInventory.from_names(names)
    result = build_fea(script, inv, level=level, validate=True)  # raises on bad syntax
    assert result.report.kept_rules > 50
    assert "akhn" in result.fea


# ---- full pipeline: compile into a real font + shape ---------------------- #

@pytest.mark.parametrize("script,level,text,expect", [
    ("sinhala", 3, "ඛි", "khI-sinh"),         # kha + isign -> khI (abvs)
    ("sinhala", 3, "කු", "kU-sinh"),          # ka + usign -> kU  (blws)
    ("sinhala", 3, "ක්‍ෂ", "kSsa-sinh"),   # ka + virama + zwj + ssa -> kSsa (akhn)
    ("tamil", 0, "கி", "kI-taml"),            # ka + isign -> kI (abvs)
    ("tamil", 0, "கு", "kU-taml"),            # ka + usign -> kU (blws)
    ("tamil", 0, "க்ஷ", "kSsa-taml"),    # ka + virama + ssa -> kSsa (akhn)
])
def test_compile_and_shape(tmp_path, script, level, text, expect):
    profile = get_profile(script, level)
    base_font = build_test_font(profile, tmp_path / "base.ttf")
    inv = FontInventory.from_font(base_font)
    result = build_fea(script, inv, level=level, validate=True)
    fea_path = tmp_path / "features.fea"
    fea_path.write_text(result.fea, encoding="utf-8")

    out_font = tmp_path / "built.ttf"
    removed = strip_and_build(base_font, fea_path, out_font)
    assert out_font.exists()

    # GSUB must have been compiled in.
    from fontTools.ttLib import TTFont
    tt = TTFont(str(out_font))
    assert "GSUB" in tt
    feature_tags = {fr.FeatureTag for fr in tt["GSUB"].table.FeatureList.FeatureRecord}
    tt.close()
    assert "akhn" in feature_tags

    # Shaping: the precomposed glyph must appear in the shaped output.
    results = shape_checks(out_font, [ShapeCheck(text, expect)])
    r = results[0]
    assert r.ok, f"{script} {text!r} -> {r.glyphs} (expected {expect})"


# ---- formed-sign ligatures (repha / yansaya / rakar) ----------------------- #

@pytest.mark.parametrize("text,expect", [
    ("ර්‍ම", "ma_repha-sinh"),        # ra+virama+zwj, ma -> reph moves to ma -> ligature (psts)
    ("ම්‍යු", "yasign_usign-sinh"),  # ma, virama+zwj+ya -> yasign; + usign (blws chain)
    ("ක්‍ර", "kRa-sinh"),             # ka+virama+zwj+ra -> rakar conjunct (akhn cartesian)
])
def test_formed_sign_ligatures_shape(tmp_path, text, expect):
    profile = get_profile("sinhala", 3)
    base_font = build_test_font(profile, tmp_path / "base.ttf",
                                extra_glyphs=aggnni_like_extras(profile))
    inv = FontInventory.from_font(base_font)
    result = build_fea("sinhala", inv, level=3, validate=True)
    fea_path = tmp_path / "features.fea"
    fea_path.write_text(result.fea, encoding="utf-8")
    out_font = tmp_path / "built.ttf"
    strip_and_build(base_font, fea_path, out_font)
    r = shape_checks(out_font, [ShapeCheck(text, expect)])[0]
    assert r.ok, f"{text!r} -> {r.glyphs} (expected {expect})"


# ---- standalone / YAML-free mode ------------------------------------------ #

def test_bundled_glyphsets_dir():
    from lankafea import scripts
    # Default resolution uses the bundled package data (self-contained install).
    assert (scripts.glyphsets_dir() / "tamil.yaml").exists()


@pytest.mark.parametrize("script,level,text,expect", [
    ("sinhala", 3, "ඛි", "khI-sinh"),
    ("sinhala", 3, "ක්‍ෂ", "kSsa-sinh"),
    ("tamil", 0, "கி", "kI-taml"),
])
def test_yaml_free_shapes(tmp_path, script, level, text, expect):
    """use_yaml=False derives everything from the codepoint tables + font glyphs."""
    profile = get_profile(script, level)
    base_font = build_test_font(profile, tmp_path / "base.ttf")
    inv = FontInventory.from_font(base_font)
    result = build_fea(script, inv, level=level, use_yaml=False, validate=True)
    fea_path = tmp_path / "features.fea"
    fea_path.write_text(result.fea, encoding="utf-8")
    out_font = tmp_path / "built.ttf"
    strip_and_build(base_font, fea_path, out_font)
    r = shape_checks(out_font, [ShapeCheck(text, expect)])[0]
    assert r.ok, f"[no-yaml] {script} {text!r} -> {r.glyphs} (expected {expect})"


# ---- Glyphs source (.glyphspackage) read + write-back --------------------- #

@pytest.mark.parametrize("ext", [".glyphs", ".glyphspackage"])
def test_glyphs_source_roundtrip(tmp_path, ext):
    from lankafea.glyphsource import inventory_from_glyphs, write_features_to_glyphs

    profile = get_profile("sinhala", 3)
    src = build_test_glyphs_source(profile, tmp_path / f"src{ext}")

    inv = inventory_from_glyphs(src)
    assert "ka-sinh" in inv.glyphs and "kSsa-sinh" in inv.glyphs

    result = build_fea("sinhala", inv, level=3, validate=True)
    assert result.report.kept_rules > 50

    out = tmp_path / f"out{ext}"
    summary = write_features_to_glyphs(
        result.doc, profile.language_systems, src, out)
    assert summary["written_features"] >= 5

    # Reload and confirm the generated features are present in the source.
    from glyphsLib import GSFont
    font = GSFont(str(out))
    tags = {f.name for f in font.features}
    assert "akhn" in tags and "abvs" in tags
    akhn = next(f for f in font.features if f.name == "akhn")
    assert "kSsa-sinh" in akhn.code

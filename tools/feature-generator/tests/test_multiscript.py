"""R1: writing generated features into a source that holds Sinhala AND Tamil.

Abhaya Libre has both scripts, with the same feature tags twice (``akhn`` for sinh,
``akhn`` for taml/tml2). Generating one script must leave the other's code, classes and
hand-written features alone.
"""

from __future__ import annotations

import pytest

from lankafea.api import build_fea
from lankafea.compile import strip_and_build
from lankafea.glyphsource import (
    MARKER, inventory_from_glyphs, write_features_to_glyphs,
)
from lankafea.glyphspackage import load_source, save_source
from lankafea.inventory import FontInventory
from lankafea.ownership import (
    collides, header, is_multi_script, manifest_code, owned_by, owned_class_names,
    owner_script, parse_manifest, scoped_tags,
)
from lankafea.scripts import get_profile
from lankafea.verify import shape_names
from lankafea.yamlloader import load_specs

from make_font import build_test_font, build_test_glyphs_source

HAND_SINH_AKHN = "script sinh;\nsub ka-sinh virama-sinh zerowidthjoiner ssa-sinh by kSsa-sinh;"
HAND_TAML_AKHN = ("script taml;\nsub ka-taml virama-taml ssa-taml by kSsa-taml;\n"
                  "script tml2;\nsub ka-taml virama-taml ssa-taml by kSsa-taml;")
HAND_UNSCOPED_ABVS = "sub ka-taml isign-taml by kI-taml;"


def mixed_source(tmp_path, ext=".glyphs", hand=True):
    """A source with both scripts' glyphs and (optionally) hand-written layout code."""
    from glyphsLib.classes import GSClass, GSFeature, GSFeaturePrefix, GSGlyph

    sinh, taml = get_profile("sinhala", 3), get_profile("tamil", 2)
    src = build_test_glyphs_source(sinh, tmp_path / f"src{ext}")
    font = load_source(src)
    have = {g.name for g in font.glyphs}
    for g in load_specs(taml).glyphs:
        if g.full_name not in have:
            font.glyphs.append(GSGlyph(g.full_name))
            have.add(g.full_name)
    if hand:
        font.features.append(GSFeature("akhn", HAND_SINH_AKHN))
        font.features.append(GSFeature("akhn", HAND_TAML_AKHN))
        font.featurePrefixes.append(GSFeaturePrefix("MyPrefix", "# custom prefix"))
        font.classes.append(GSClass("MyClass", "ka-sinh ka-taml"))
    save_source(font, src)
    return src


def generate(script, src, out, **kw):
    inv = inventory_from_glyphs(src)
    level = 3 if script == "sinhala" else 2
    result = build_fea(script, inv, level=level, validate=True)
    summary = write_features_to_glyphs(
        result.doc, result.profile.language_systems, src, out,
        script=script, **kw)
    return result, summary


def codes(font, tag):
    return [f.code for f in font.features if f.name == tag]


# ---- ownership, as pure functions ----------------------------------------------- #

def test_owner_is_read_from_the_script_line_or_inferred_from_names():
    assert owner_script(header("tamil", scoped=True) + "\nsub ka-sinh") == "tamil"
    assert owner_script(MARKER + "\nsub ka-taml virama-taml by k-taml;") == "tamil"
    assert owner_script(MARKER + "\nsub ka-sinh by x-sinh; sub a-taml by b-taml;") is None
    assert owner_script(MARKER + "\n# nothing script specific") is None


def test_generated_blocks_belong_to_their_own_script_only():
    sinhala_block = MARKER + "\nsub ka-sinh virama-sinh by k-sinh;"
    assert owned_by(sinhala_block, "sinhala") and not owned_by(sinhala_block, "tamil")
    assert owned_by(sinhala_block, None)                      # single-script: all ours
    unknown = MARKER + "\n# no glyph names"
    assert owned_by(unknown, "sinhala") and owned_by(unknown, "tamil")
    assert not owned_by("sub ka-sinh by x;", "sinhala")       # hand-written is never ours


def test_a_hand_written_feature_collides_only_if_it_can_affect_the_script():
    assert collides(HAND_UNSCOPED_ABVS, "tamil") and collides(HAND_UNSCOPED_ABVS, "sinhala")
    assert collides(HAND_TAML_AKHN, "tamil") and not collides(HAND_TAML_AKHN, "sinhala")
    assert collides(HAND_SINH_AKHN, "sinhala") and not collides(HAND_SINH_AKHN, "tamil")
    assert scoped_tags(HAND_TAML_AKHN) == {"taml", "tml2"}
    assert collides(HAND_SINH_AKHN, None)                     # no script given: as before


def test_manifest_is_kept_per_script():
    m1 = manifest_code(None, "sinhala", True, ["uSign", "iSign"])
    m2 = manifest_code(m1, "tamil", True, ["isign_ka"])
    assert parse_manifest(m2) == {"sinhala": ["uSign", "iSign"], "tamil": ["isign_ka"]}
    assert owned_class_names(m2, "tamil") == {"isign_ka"}
    assert owned_class_names(m2, "sinhala") == {"uSign", "iSign"}
    assert owned_class_names(m2, None) == {"uSign", "iSign", "isign_ka"}
    # rerunning Tamil rewrites only its own line
    m3 = manifest_code(m2, "tamil", True, ["isign_ka", "usign_pa"])
    assert parse_manifest(m3)["sinhala"] == ["uSign", "iSign"]
    assert parse_manifest(m3)["tamil"] == ["isign_ka", "usign_pa"]


def test_legacy_manifest_names_are_owned_by_whoever_their_members_belong_to():
    legacy = MARKER + "\n# classes: tamilcls sinhcls"
    code = {"tamilcls": "ka-taml virama-taml", "sinhcls": "ka-sinh"}
    assert owned_class_names(legacy, "tamil", code) == {"tamilcls"}
    assert owned_class_names(legacy, "sinhala", code) == {"sinhcls"}


def test_multi_script_detection():
    assert is_multi_script(["ka-sinh", "ka-taml"])
    assert not is_multi_script(["ka-sinh", "kI-sinh", "zerowidthjoiner"])
    assert is_multi_script(["isign-taml.ka", "usign.rasign-sinh"])      # either dot-suffix order


# ---- the writeback -------------------------------------------------------------- #

def test_scripts_are_generated_one_after_the_other_without_clobbering(tmp_path):
    src = mixed_source(tmp_path, hand=False)
    _, s1 = generate("sinhala", src, tmp_path / "step1.glyphs")
    _, s2 = generate("tamil", tmp_path / "step1.glyphs", tmp_path / "step2.glyphs")

    font = load_source(tmp_path / "step2.glyphs")
    sinhala_after = [f for f in font.features if owner_script(f.code) == "sinhala"]
    tamil_after = [f for f in font.features if owner_script(f.code) == "tamil"]
    assert sinhala_after and tamil_after
    # Tamil's run did not touch what the Sinhala run wrote
    f1 = load_source(tmp_path / "step1.glyphs")
    assert sorted(f.code for f in f1.features) == sorted(f.code for f in sinhala_after)
    assert s2["stripped_features"] == 0                          # nothing of Tamil's to strip yet
    # both scripts' languagesystems, once
    ls = [p for p in font.featurePrefixes if p.name == "Languagesystems"]
    assert len(ls) == 1
    for line in ("languagesystem sinh dflt;", "languagesystem taml dflt;",
                 "languagesystem tml2 dflt;"):
        assert line in ls[0].code
    # and one manifest listing each script's classes
    manifests = [p for p in font.featurePrefixes if p.name == "lankafea-manifest"]
    assert len(manifests) == 1
    listed = parse_manifest(manifests[0].code)
    assert listed["tamil"] == ["ra_alt_next"]    # the one class this font's glyphs reach


def test_rerunning_one_script_leaves_the_other_byte_identical(tmp_path):
    src = mixed_source(tmp_path, hand=False)
    generate("sinhala", src, tmp_path / "a.glyphs")
    generate("tamil", tmp_path / "a.glyphs", tmp_path / "b.glyphs")
    before = load_source(tmp_path / "b.glyphs")
    sinhala_before = sorted((f.name, f.code) for f in before.features
                            if owner_script(f.code) == "sinhala")
    classes_before = {c.name: c.code for c in before.classes}
    # (guard against comparing two empty lists: both scripts must really be there)
    assert sinhala_before and "ra_alt_next" in classes_before

    _, summary = generate("tamil", tmp_path / "b.glyphs", tmp_path / "c.glyphs")
    after = load_source(tmp_path / "c.glyphs")
    assert summary["stripped_features"] > 0                      # Tamil's own, replaced
    assert sorted((f.name, f.code) for f in after.features
                  if owner_script(f.code) == "sinhala") == sinhala_before
    assert {c.name: c.code for c in after.classes} == classes_before
    tamil_tags = sorted(f.name for f in after.features if owner_script(f.code) == "tamil")
    assert tamil_tags == sorted(f.name for f in before.features
                                if owner_script(f.code) == "tamil")        # not duplicated


def test_a_replace_takes_out_the_collision_of_that_script_only(tmp_path):
    """Two hand-written akhn: one sinh, one taml/tml2. --replace-tags akhn for Tamil
    must remove the Tamil one and keep the Sinhala one."""
    src = mixed_source(tmp_path)
    _, summary = generate("tamil", src, tmp_path / "out.glyphs", replace_tags={"akhn"})
    assert summary["collisions"]["akhn"] == "replace"
    font = load_source(tmp_path / "out.glyphs")
    akhn = codes(font, "akhn")
    assert HAND_SINH_AKHN in akhn                                # Sinhala's survives
    assert HAND_TAML_AKHN not in akhn                            # Tamil's is replaced
    generated = [c for c in akhn if c.startswith(MARKER)]
    assert len(generated) == 1 and owner_script(generated[0]) == "tamil"


def test_by_default_the_hand_written_one_of_the_same_script_wins(tmp_path):
    src = mixed_source(tmp_path)
    _, summary = generate("tamil", src, tmp_path / "out.glyphs")
    assert summary["collisions"]["akhn"] == "keep"
    akhn = codes(load_source(tmp_path / "out.glyphs"), "akhn")
    assert HAND_TAML_AKHN in akhn and HAND_SINH_AKHN in akhn
    assert not any(c.startswith(MARKER) for c in akhn)           # generated akhn not written


def test_another_scripts_hand_written_feature_is_not_a_collision(tmp_path):
    from glyphsLib.classes import GSFeature
    src = mixed_source(tmp_path, hand=False)
    font = load_source(src)
    font.features.append(GSFeature("akhn", HAND_SINH_AKHN))      # only Sinhala has one
    save_source(font, src)
    _, summary = generate("tamil", src, tmp_path / "out.glyphs")
    assert "akhn" not in summary["collisions"]                   # no clash: written alongside
    akhn = codes(load_source(tmp_path / "out.glyphs"), "akhn")
    assert HAND_SINH_AKHN in akhn
    assert any(c.startswith(MARKER) and owner_script(c) == "tamil" for c in akhn)


def test_an_unscoped_hand_written_feature_collides_with_both(tmp_path):
    from glyphsLib.classes import GSFeature
    src = mixed_source(tmp_path, hand=False)
    font = load_source(src)
    font.features.append(GSFeature("abvs", HAND_UNSCOPED_ABVS))
    save_source(font, src)
    assert generate("tamil", src, tmp_path / "t.glyphs")[1]["collisions"]["abvs"] == "keep"
    assert generate("sinhala", src, tmp_path / "s.glyphs")[1]["collisions"]["abvs"] == "keep"


def test_hand_written_code_and_classes_survive_both_runs(tmp_path):
    src = mixed_source(tmp_path)
    generate("sinhala", src, tmp_path / "a.glyphs")
    generate("tamil", tmp_path / "a.glyphs", tmp_path / "b.glyphs")
    font = load_source(tmp_path / "b.glyphs")
    assert any(p.name == "MyPrefix" and p.code == "# custom prefix" for p in font.featurePrefixes)
    assert next(c for c in font.classes if c.name == "MyClass").code == "ka-sinh ka-taml"


def test_generated_code_is_scoped_in_a_multi_script_source(tmp_path):
    src = mixed_source(tmp_path, hand=False)
    generate("tamil", src, tmp_path / "out.glyphs")
    font = load_source(tmp_path / "out.glyphs")
    abvs = next(c for c in codes(font, "abvs") if owner_script(c) == "tamil")
    assert abvs.startswith(MARKER + "\n# lankafea:script tamil\n")
    first, second = abvs.index("script taml;"), abvs.index("script tml2;")
    assert first < second
    assert "lookup SignLigatures_abvs {" in abvs[first:second]          # defined once…
    assert "lookup SignLigatures_abvs;" in abvs[second:]                # …referenced again


def test_a_single_script_source_is_written_unscoped_as_before(tmp_path):
    src = build_test_glyphs_source(get_profile("tamil", 2), tmp_path / "t.glyphs")
    _, _ = generate("tamil", src, tmp_path / "out.glyphs")
    abvs = codes(load_source(tmp_path / "out.glyphs"), "abvs")[0]
    assert "script taml;" not in abvs and "lankafea:script" not in abvs


def test_scoping_can_be_forced(tmp_path):
    src = build_test_glyphs_source(get_profile("tamil", 2), tmp_path / "t.glyphs")
    generate("tamil", src, tmp_path / "out.glyphs", scope_scripts=True)
    assert "script tml2;" in codes(load_source(tmp_path / "out.glyphs"), "abvs")[0]


def test_scoped_features_compile_and_register_for_both_tamil_scripts(tmp_path):
    """The `lookup X;` references really do register the lookup for tml2 as well."""
    from fontTools.ttLib import TTFont
    profile = get_profile("tamil", 2)
    base = build_test_font(profile, tmp_path / "base.ttf")
    inv = FontInventory.from_font(base)
    result = build_fea("tamil", inv, level=2)
    from lankafea.feacomposer_adapter import TextBackend
    fea = "languagesystem taml dflt;\nlanguagesystem tml2 dflt;\n"
    fea += "\n".join(f"@{c.name} = [{' '.join(c.members)}];" for c in result.doc.classes) + "\n"
    fea += "\n".join(TextBackend().emit_feature(f, ["taml", "tml2"]) for f in result.doc.features)
    path = tmp_path / "scoped.fea"
    path.write_text(fea, encoding="utf-8")
    built = tmp_path / "built.ttf"
    strip_and_build(base, path, built)
    tt = TTFont(str(built))
    scripts = {r.ScriptTag: r for r in tt["GSUB"].table.ScriptList.ScriptRecord}
    assert {"taml", "tml2"} <= set(scripts)
    tt.close()
    assert shape_names(built, "கி") == ["kI-taml"]
    assert shape_names(built, "க்ஷ") == ["kSsa-taml"]


def test_the_inventory_does_not_harvest_classes_lankafea_wrote(tmp_path):
    """Otherwise last run's isign_ka would become the designer's override next run."""
    src = mixed_source(tmp_path, hand=False)
    generate("tamil", src, tmp_path / "out.glyphs")
    font = load_source(tmp_path / "out.glyphs")
    assert any(c.name == "ra_alt_next" for c in font.classes)          # we wrote it…
    inv = inventory_from_glyphs(tmp_path / "out.glyphs")
    assert "ra_alt_next" not in inv.source_classes                      # …so it is not "the designer's"
    # while a class the designer made is still harvested
    from glyphsLib.classes import GSClass
    font = load_source(tmp_path / "out.glyphs")
    font.classes.append(GSClass("isign_ma", "ma-taml"))
    save_source(font, tmp_path / "out.glyphs")
    assert inventory_from_glyphs(tmp_path / "out.glyphs").source_classes["isign_ma"] == ["ma-taml"]

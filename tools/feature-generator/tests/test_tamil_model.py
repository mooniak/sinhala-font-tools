"""The Tamil model: forms met by a ligature OR a shape-group alternate, shaped for real.

Fonts here are built from the standard's own names (empty outlines, correct cmap), so
every behaviour is checked end to end: generate -> compile -> HarfBuzz.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lankafea.api import build_fea, validate_font
from lankafea.compile import strip_and_build
from lankafea.inventory import FontInventory
from lankafea.scripts import (
    TAMIL_GRANTHA, TAMIL_GROUPS, TAMIL_TRADITIONAL_FORMS, get_profile,
)
from lankafea.tamil import build_units
from lankafea.verify import shape_names
from lankafea.yamlloader import load_specs, synth_specs

from make_font import build_test_font

PROFILE = get_profile("tamil", 2)
SPECS = load_specs(PROFILE)
STANDARD = {g.full_name for g in SPECS.glyphs} | {"zerowidthjoiner"}

# Group alternates the standard names, as glyphs (they are not YAML entries).
ALTERNATES = {f"{sign}-taml.{group}" for sign, groups in TAMIL_GROUPS.items() for group in groups}
# The forms a shape-group alternate can also meet: ligatures the alternate-style font omits.
GROUP_FORMS = {f"{(m[:-1] if m.endswith('a') else m)}{abbr}-taml"
               for sign, abbr in (("isign", "I"), ("iisign", "Ii"), ("usign", "U"))
               for members in TAMIL_GROUPS.get(sign, {}).values() for m in members}


def build_and_shape(tmp_path: Path, exclude=(), extra=()):
    """Build a font, generate features for it, compile them in; return its path."""
    font = build_test_font(PROFILE, tmp_path / "base.ttf",
                           extra_glyphs=list(extra), exclude_glyphs=set(exclude))
    inv = FontInventory.from_font(font)
    result = build_fea("tamil", inv, level=2, validate=True)
    fea = tmp_path / "f.fea"
    fea.write_text(result.fea, encoding="utf-8")
    built = tmp_path / "built.ttf"
    strip_and_build(font, fea, built)
    return built, result


# ---- the model ----------------------------------------------------------------- #

def test_nnna_not_nna2():
    """The naming bug: ன was `nna2`, so a form read `nna2a-taml`. It is `nnna`."""
    from lankafea.scripts import TAMIL
    assert TAMIL.consonants[0x0BA9] == "nnna"
    result = build_fea("tamil", FontInventory.from_names(STANDARD), level=2)
    assert "nnnU-taml" in result.fea and "nna2" not in result.fea


def test_builtin_tables_equal_the_yaml():
    """--no-yaml uses built-in copies of the groups; they must not drift."""
    assert SPECS.groups == TAMIL_GROUPS
    assert SPECS.grantha == list(TAMIL_GRANTHA)
    traditional = {g.name for g in SPECS.glyphs if g.category.startswith("ss09 ")}
    assert traditional == set(TAMIL_TRADITIONAL_FORMS) | {"ra.alt"}
    assert synth_specs(PROFILE).groups == SPECS.groups


def test_dot_suffix_goes_after_the_namespace():
    units = build_units(SPECS)
    assert units["kI"].alt_glyph == "isign-taml.ka"
    assert units["ra.alt"].glyph == "ra-taml.alt"
    assert units["ngU"].alt_glyph == "usign-taml.pa"
    assert units["nnAi"].alt_glyph == "aisign-taml.la"


def test_few_hundred_candidates_not_thousands():
    """The Sinhala model generated about 8,200 candidate rules for Tamil; the Tamil
    model writes a few hundred at most (class rules cover a whole shape group)."""
    from lankafea.tamil import generate_tamil
    doc = generate_tamil(SPECS)
    candidates = sum(len(lk.rules) for f in doc.features for lk in f.lookups)
    assert 100 < candidates < 500, candidates


def test_feature_routing():
    """க்ஷ/ஸ்ரீ in akhn, ி/ீ in abvs, ு/ூ in psts, the traditional forms in ss09;
    no pres, no blws, no rphf/vatu, no conjuncts but க்ஷ."""
    result = build_fea("tamil", FontInventory.from_names(STANDARD | ALTERNATES), level=2)
    where: dict[str, set[str]] = {}
    for f in result.doc.features:
        for lk in f.lookups:
            for r in lk.rules:
                where.setdefault(f.tag, set()).add(str(r.output))
    assert set(where) == {"akhn", "abvs", "psts", "ss09"}
    assert where["akhn"] == {"kSsa-taml", "shree-taml"}
    assert {"kI-taml", "ttIi-taml", "isign-taml.ka"} <= where["abvs"]
    assert {"kU-taml", "kUu-taml", "usign-taml.pa"} <= where["psts"]
    assert not any(o.startswith(("kU-", "kUu-")) for o in where["abvs"])    # not blws, not abvs
    assert {"nnAa-taml", "lAi-taml", "aisign-taml.la", "ra-taml.alt"} <= where["ss09"]


def test_traditional_forms_stay_out_of_the_default_features():
    """lAi / nnAa would otherwise rewrite every modern ணை / ணா."""
    result = build_fea("tamil", FontInventory.from_names(STANDARD | ALTERNATES), level=2)
    default = {r.output for f in result.doc.features if f.tag != "ss09"
               for lk in f.lookups for r in lk.rules}
    for name in ("nnAa-taml", "rrAa-taml", "lAi-taml", "llAi-taml", "ra-taml.alt",
                 "aisign-taml.la"):
        assert name not in default


# ---- shaping, both routes ------------------------------------------------------ #

def test_ligature_font_forms_its_ligatures(tmp_path):
    font, _ = build_and_shape(tmp_path)
    assert shape_names(font, "கி") == ["kI-taml"]
    assert shape_names(font, "டீ") == ["ttIi-taml"]
    assert shape_names(font, "கு") == ["kU-taml"]
    assert shape_names(font, "கூ") == ["kUu-taml"]
    assert shape_names(font, "க்ஷ") == ["kSsa-taml"]
    assert shape_names(font, "க்ஷி") == ["kSsI-taml"]      # kSsa formed in akhn, then ி in abvs


def test_ஸ்ரீ_and_ஶ்ரீ_are_one_glyph(tmp_path):
    font, _ = build_and_shape(tmp_path)
    assert shape_names(font, "ஸ்ரீ") == ["shree-taml"]
    assert shape_names(font, "ஶ்ரீ") == ["shree-taml"]


def test_alternate_font_selects_the_shape_group_glyph(tmp_path):
    """No kI-taml at all: ி next to க takes isign-taml.ka instead."""
    font, result = build_and_shape(tmp_path, exclude=GROUP_FORMS, extra=ALTERNATES)
    assert shape_names(font, "கி") == ["ka-taml", "isign-taml.ka"]
    assert shape_names(font, "ஙி") == ["nga-taml", "isign-taml.pa"]
    assert shape_names(font, "ஙு") == ["nga-taml", "usign-taml.pa"]     # the hook
    assert shape_names(font, "லீ") == ["la-taml", "iisign-taml.la"]
    assert shape_names(font, "ணி") == ["nna-taml", "isign-taml"]        # no group: plain sign
    # ...and a form that has no group still needs, and gets, its own glyph.
    assert shape_names(font, "டி") == ["ttI-taml"]
    assert shape_names(font, "கு") == ["kU-taml"]


def test_a_dedicated_glyph_beats_the_alternate(tmp_path):
    """Yaldevi draws ஙி as a ligature and also lists ng in the group."""
    font, _ = build_and_shape(tmp_path, exclude=GROUP_FORMS - {"ngI-taml"}, extra=ALTERNATES)
    assert shape_names(font, "ஙி") == ["ngI-taml"]
    assert shape_names(font, "பி") == ["pa-taml", "isign-taml.pa"]


# ---- the traditional orthography: ss09 ---------------------------------------- #

def test_traditional_forms_only_with_ss09(tmp_path):
    font, _ = build_and_shape(tmp_path, extra=ALTERNATES)
    assert shape_names(font, "ணா") == ["nna-taml", "aasign-taml"]            # modern
    assert shape_names(font, "ணா", {"ss09": True}) == ["nnAa-taml"]          # traditional
    assert shape_names(font, "றா", {"ss09": True}) == ["rrAa-taml"]
    # ை comes before its consonant once the shaper has reordered it
    assert shape_names(font, "லை") == ["aisign-taml", "la-taml"]
    assert shape_names(font, "லை", {"ss09": True}) == ["lAi-taml"]
    assert shape_names(font, "ணை", {"ss09": True}) == ["nnAi-taml"]


def test_alternate_ra_is_a_real_glyph(tmp_path):
    font, _ = build_and_shape(tmp_path)
    assert shape_names(font, "ரி") == ["ra-taml", "isign-taml"]               # modern: plain ரி
    assert shape_names(font, "ர்", {"ss09": True}) == ["ra-taml.alt", "virama-taml"]
    assert shape_names(font, "ர") == ["ra-taml"]                              # alone: unchanged


# ---- either/or in the validator ------------------------------------------------ #

def _report(names, level=2, **kw):
    return validate_font("tamil", FontInventory.from_names(set(names)), level=level, **kw)


def test_ligature_font_is_not_asked_for_the_alternate():
    r = _report(STANDARD)                       # standard glyphs, no alternates
    assert r.blockers == []
    assert not any("isign-taml.ka" in b.glyph for b in r.blockers)
    assert r.forms_unmet == []


def test_alternate_font_is_not_asked_for_the_ligatures():
    r = _report((STANDARD - GROUP_FORMS) | ALTERNATES)
    assert r.blockers == []
    assert r.forms_unmet == []
    met = {f["form"]: f["met"] for f in r.forms}
    assert met["kI-taml"] == "alternate" and met["pU-taml"] == "alternate"
    assert met["ttI-taml"] == "glyph" and met["kU-taml"] == "glyph"


def test_neither_route_is_unmet_and_names_both_glyphs():
    r = _report(STANDARD - {"kI-taml"})
    assert [f["form"] for f in r.forms_unmet] == ["kI-taml"]
    kI = next(b for b in r.blockers if b.glyph == "kI-taml")
    assert "isign-taml.ka" in kI.hint
    # the other route is blocked too, and says what would also work
    alt = next(b for b in r.blockers if b.glyph == "isign-taml.ka")
    assert alt.hint and "kI-taml" in alt.hint


def test_forms_without_a_group_have_no_second_route():
    r = _report(STANDARD - {"ttI-taml"})
    assert [f["form"] for f in r.forms_unmet] == ["ttI-taml"]
    assert next(b for b in r.blockers if b.glyph == "ttI-taml").hint is None


def test_forms_the_standard_does_not_enumerate_are_never_reported():
    """nnI, rI, llI and every ீ but ட ல ஸ take the plain sign; absent is fine."""
    for absent in ("nnI-taml", "rI-taml", "kIi-taml", "kAa-taml", "k-taml"):
        assert absent not in STANDARD
    r = _report(STANDARD)
    assert r.blockers == [] and r.dropped_rules == 0


def test_level_sets_what_is_required():
    core_only = STANDARD - {"kI-taml"}               # a Core form
    assert _report(core_only, level=0).forms_unmet == []      # Kernel font: fine
    assert [f["form"] for f in _report(core_only, level=1).forms_unmet] == ["kI-taml"]
    pro_only = STANDARD - {"nnAa-taml"}
    assert _report(pro_only, level=1).forms_unmet == []
    assert [f["form"] for f in _report(pro_only, level=2).forms_unmet] == ["nnAa-taml"]


def test_level_above_the_top_means_all_of_it():
    assert get_profile("tamil", 3).level == 2 == get_profile("tamil", 9).level


def test_kernel_requirement_count():
    """Kernel: 38 forms + க்ஷ + ஸ்ரீ. Core adds 31. Pro adds 7 forms + ra.alt."""
    assert len(_report(STANDARD, level=0).forms) == 40
    assert len(_report(STANDARD, level=1).forms) == 71
    assert len(_report(STANDARD, level=2).forms) == 79


def test_json_report_carries_forms_only_for_tamil():
    data = json.loads(_report(STANDARD - {"kI-taml"}).to_json())
    assert data["forms"]["unmet"] == ["kI-taml"]
    assert data["forms"]["level"] == 2 and data["forms"]["required"] == 79
    assert "forms" not in json.loads(validate_font(
        "sinhala", FontInventory.from_names({"ka-sinh"}), level=3).to_json())


def test_text_report_names_unmet_forms():
    text = _report(STANDARD - {"kI-taml"}).to_text()
    assert "Tamil forms required at level 2: 79" in text
    assert "unmet: kI-taml (or isign-taml.ka)" in text


# ---- a designer's own class narrows a shape group ------------------------------ #

def test_source_class_overrides_the_standard_members():
    """The standard's `ma` group has six members; a font that draws ja/rra/zha as
    ligatures says so with its own class of the same name."""
    names = STANDARD | ALTERNATES
    inv = FontInventory(set(names), set(),
                        source_classes={"isign_ma": ["ma-taml", "sha-taml", "ha-taml"]})
    result = build_fea("tamil", inv, level=2)
    cls = next(c for c in result.doc.classes if c.name == "isign_ma")
    assert cls.members == ["ma-taml", "sha-taml", "ha-taml"]
    default = build_fea("tamil", FontInventory.from_names(names), level=2)
    assert len(next(c for c in default.doc.classes if c.name == "isign_ma").members) == 6


# ---- naming: aliases for a font not yet migrated --------------------------------- #

def _legacy_inventory():
    """A pre-standard font: ன is nna2, a Ralex-style alt number stands for a group."""
    names = set(STANDARD)
    for new, old in (("nnna-taml", "nna2-taml"), ("nnnU-taml", "nna2-u-taml"),
                     ("nnnUu-taml", "nna2-uu-taml"), ("nnnI-taml", "nna2-i-taml")):
        if new in names:
            names.remove(new)
        names.add(old)
    names.add("ra.alt-taml")
    return names


def test_legacy_names_are_adopted_on_request():
    inv = FontInventory.from_names(_legacy_inventory())
    plain = validate_font("tamil", inv, level=2)
    assert any(b.glyph == "nnna-taml" for b in plain.blockers)      # the standard's name is missing
    adopted = validate_font("tamil", inv, level=2, adopt_legacy_names=True)
    assert not any(b.glyph in ("nnna-taml", "nnnU-taml", "nnnUu-taml") for b in adopted.blockers)


def test_alias_table_names_the_fonts_own_glyphs():
    names = (STANDARD - {"kI-taml"}) | {"isign.alt5-taml"}          # alt5 is the `ka` group here
    inv = FontInventory.from_names(names)
    assert [f["form"] for f in validate_font("tamil", inv, level=2).forms_unmet] == ["kI-taml"]
    r = validate_font("tamil", inv, level=2, aliases={"isign-taml.ka": "isign.alt5-taml"})
    assert r.forms_unmet == []
    fea = build_fea("tamil", inv, level=2, aliases={"isign-taml.ka": "isign.alt5-taml"}).fea
    assert "by isign.alt5-taml" in fea and "isign-taml.ka" not in fea


def test_alias_file_loads_yaml_and_json(tmp_path):
    from lankafea.aliases import load_alias_file
    (tmp_path / "a.yaml").write_text("isign-taml.ka: isign.alt5-taml\n", encoding="utf-8")
    (tmp_path / "a.json").write_text('{"isign-taml.ka": "isign.alt5-taml"}', encoding="utf-8")
    assert load_alias_file(tmp_path / "a.yaml") == load_alias_file(tmp_path / "a.json") \
        == {"isign-taml.ka": "isign.alt5-taml"}


# ---- anchors -------------------------------------------------------------------- #

def _anchor_inventory(sign_anchor, base_anchor, lacking=0):
    from lankafea.adaptation import anchor_findings
    names = {f"{s}a-taml" for s in ("k", "ca", "t")} | {"ka-taml", "ca-taml", "ta-taml"}
    names |= {"isign-taml"}
    anchors = {"isign-taml": {sign_anchor}}
    for i, c in enumerate(("ka-taml", "ca-taml", "ta-taml")):
        if i >= lacking:
            anchors[c] = {base_anchor}
    inv = FontInventory(names, set(), anchors=anchors)
    return anchor_findings(inv, {}, PROFILE, SPECS)


def test_standard_anchor_names_are_clean():
    assert not any("naming" in f for f in _anchor_inventory("_isign", "isign"))


@pytest.mark.parametrize("sign_anchor,base_anchor", [
    ("_MatraI.alt5", "MatraI.alt5"),      # Yaldevi
    ("_Anchor-1", "Anchor-1"),            # Ralex: read from the mark glyph itself
])
def test_legacy_anchor_names_are_accepted_but_noted(sign_anchor, base_anchor):
    findings = _anchor_inventory(sign_anchor, base_anchor)
    assert not any("lack" in f for f in findings)
    assert any("anchor naming" in f and "'isign'" in f for f in findings)


def test_missing_base_anchor_is_found():
    findings = _anchor_inventory("_isign", "isign", lacking=2)
    assert any("lack the 'isign' anchor" in f for f in findings)


def test_a_consonant_with_its_own_glyph_needs_no_anchor():
    from lankafea.adaptation import anchor_findings
    names = {"ka-taml", "isign-taml", "kI-taml"}
    inv = FontInventory(names, set(), anchors={"isign-taml": {"_isign"}})   # ka has no anchor
    assert not any("lack" in f for f in anchor_findings(inv, {}, PROFILE, SPECS))

"""Generators added for the Abhaya Libre refactor (plan Phases 1 and 2): .rasign sign
variants (G3), yansaya Da forms (G5), ං + ශ (S1), the ss02 Fa set (S2), numeral sets
(S3), and the per-font settings (dist, featureNames, sources/lankafea.yaml)."""

from __future__ import annotations

import pytest

from lankafea.api import build_fea
from lankafea.fontconfig import find_config, load_font_config
from lankafea.inventory import FontInventory

import acceptance_sinhala as A

ZWJ, VIRAMA = "‍", "්"
KA, RA, YA, DA, FA, SHA = "ක", "ර", "ය", "ද", "ෆ", "ශ"
SINHALA_CMAP = {0x0D9A: "ka-sinh", 0x0DBB: "ra-sinh", 0x0DBA: "ya-sinh", 0x0DAF: "da-sinh",
                0x0DC6: "fa-sinh", 0x0DC1: "sha-sinh", 0x0DCA: "virama-sinh",
                0x0DD4: "usign-sinh", 0x0DD6: "uusign-sinh", 0x0DCF: "aasign-sinh",
                0x0D82: "anusvaraya-sinh", 0x200D: "zerowidthjoiner",
                **{0x0DE6 + d: f"lith{w}-sinh" for d, w in enumerate(
                    ["zero", "one", "two", "three", "four", "five", "six", "seven",
                     "eight", "nine"])},
                **{0x30 + d: w for d, w in enumerate(
                    ["zero", "one", "two", "three", "four", "five", "six", "seven",
                     "eight", "nine"])}}


def inventory(*extra: str) -> FontInventory:
    names = set(SINHALA_CMAP.values()) | {"rasign-sinh", "yasign-sinh", "touch-sinh",
                                          "space"} | set(extra)
    return FontInventory(names, set(SINHALA_CMAP), dict(SINHALA_CMAP))


def shaper(tmp_path, inv: FontInventory, **kw):
    r = build_fea("sinhala", inv, validate=True, **kw)
    sh = A.Shaper(A.synthetic_font(inv, r.fea, tmp_path / "t.ttf"))
    return r, (lambda text, feats=None: sh.shape(text, feats)[0])


def layout(result):
    return {f.tag: [lk.name for lk in f.lookups] for f in result.doc.features}


# ---- G3: .rasign u/uu after rakar --------------------------------------------- #

def test_rakar_takes_rasign_u_variant(tmp_path):
    inv = inventory("kRa-sinh", "usign.rasign-sinh", "uusign.rasign-sinh")
    _, shape = shaper(tmp_path, inv)
    assert shape(KA + VIRAMA + ZWJ + RA + "ු") == ["kRa-sinh", "usign.rasign-sinh"]
    assert shape(KA + VIRAMA + ZWJ + RA + "ූ") == ["kRa-sinh", "uusign.rasign-sinh"]
    assert shape(KA + "ු") == ["ka-sinh", "usign-sinh"]        # no rakar, plain sign


def test_drawn_rakar_u_ligature_wins(tmp_path):
    inv = inventory("kRa-sinh", "kRU-sinh", "usign.rasign-sinh")
    _, shape = shaper(tmp_path, inv)
    assert shape(KA + VIRAMA + ZWJ + RA + "ු") == ["kRU-sinh"]


# ---- G5: yansaya Da forms (ss01) ------------------------------------------------ #

def test_yansaya_da_forms_in_ss01_only(tmp_path):
    inv = inventory("dya._c-sinh", "dyaa._c-sinh", "dyU._c-sinh", "yasign_usign-sinh")
    _, shape = shaper(tmp_path, inv)
    dya = DA + VIRAMA + ZWJ + YA
    assert shape(dya) == ["da-sinh", "yasign-sinh"]
    assert shape(dya, {"ss01": True}) == ["dya._c-sinh"]
    assert shape(dya + "ා", {"ss01": True}) == ["dyaa._c-sinh"]
    assert shape(dya + "ු", {"ss01": True}) == ["dyU._c-sinh"]


# ---- S1: ං + ශ ------------------------------------------------------------------ #

def test_anusvara_sha_is_optional_and_routable(tmp_path):
    inv = inventory("anusvarayaSha-sinh")
    r, shape = shaper(tmp_path, inv)
    text = KA + "ං" + SHA
    assert shape(text) == ["ka-sinh", "anusvaraya-sinh", "sha-sinh"]
    assert shape(text, {"dlig": True}) == ["ka-sinh", "anusvarayaSha-sinh"]
    r = build_fea("sinhala", inv, assign={"groups": [{"group": "AnusvaraSha", "to": "ss03"}]},
                  options={"featureNames": {"ss03": "Archaic ligatures"}})
    assert layout(r)["ss03"] == ["AnusvaraSha"] and "dlig" not in layout(r)
    # A set made by routing is named too.
    assert 'name "Archaic ligatures";' in r.fea


# ---- S2: the ss02 Fa set -------------------------------------------------------- #

def test_fa_forms_take_their_fp_alternate_in_ss02(tmp_path):
    inv = inventory("fpa-sinh", "fU-sinh", "fpU-sinh")
    _, shape = shaper(tmp_path, inv)
    assert shape(FA) == ["fa-sinh"]
    assert shape(FA, {"ss02": True}) == ["fpa-sinh"]
    assert shape(FA + "ු", {"ss02": True}) == ["fpU-sinh"]


# ---- S3: numeral sets ------------------------------------------------------------ #

LITH_TENS = [f"lith{w}_lithzero-sinh" for w in
             ["one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]]
ARCHAIC = [f"archaic{w}-sinh" for w in
           ["one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
            "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety",
            "onehundred", "onethousand"]]
NUMERALS = {"lith": "ss07", "lithTens": "rlig", "archaic": "ss08"}


def test_numerals_only_when_the_font_routes_them():
    inv = inventory(*LITH_TENS, *ARCHAIC)
    tags = set(layout(build_fea("sinhala", inv)))
    assert not tags & {"ss07", "ss08", "rlig"}


def test_numeral_sets(tmp_path):
    inv = inventory(*LITH_TENS, *ARCHAIC)
    _, shape = shaper(tmp_path, inv, options={"numerals": NUMERALS})
    # ASCII digits are shaped as DFLT, so the sets must be registered there too.
    assert shape("7", {"ss07": True}) == ["lithseven-sinh"]
    assert shape("10", {"ss07": True}) == ["lithone_lithzero-sinh"]
    assert shape("90", {"ss08": True}) == ["archaicninety-sinh"]
    assert shape("100", {"ss08": True}) == ["archaiconehundred-sinh"]
    assert shape("1000", {"ss08": True}) == ["archaiconethousand-sinh"]
    # Lith digits typed as such ligate by default (rlig); ෯෦ is ninety (Abhaya's B2).
    assert shape("෯෦") == ["lithnine_lithzero-sinh"]
    assert shape("12") == ["one", "two"]


# ---- per-font settings ----------------------------------------------------------- #

def test_dist_amount_and_feature_names():
    inv = inventory(*LITH_TENS)
    r = build_fea("sinhala", inv, options={
        "dist": -113, "numerals": {"lith": "ss07"},
        "featureNames": {"ss07": 'Lith "numerals"'}})
    assert "pos touch-sinh <0 0 -113 0>;" in r.fea
    assert 'featureNames {\n        name "Lith numerals";' in r.fea
    assert "<0 0 -90 0>" in build_fea("sinhala", inv).fea          # the default


def test_feature_name_defaults_to_the_standards():
    from lankafea.scripts import get_profile
    from lankafea.yamlloader import load_specs
    specs = load_specs(get_profile("sinhala", 3))
    r = build_fea("sinhala", FontInventory.from_names({g.full_name for g in specs.glyphs}))
    names = {f.tag: f.names for f in r.doc.features}
    assert names["ss01"] == "Da Forms" and names["ss02"] == "Fa"


def test_font_config_file(tmp_path):
    src = tmp_path / "sources"
    (src / "lankafea").mkdir(parents=True)
    (src / "lankafea" / "extra.yaml").write_text("lookups: []\n", encoding="utf-8")
    (src / "Font.glyphspackage").mkdir()
    (src / "lankafea.yaml").write_text(
        "sinhala:\n"
        "  inject: [lankafea]\n"
        "  assign: {groups: [{group: DaShape, to: dlig, mode: copy}]}\n"
        "  dist: -113\n"
        "  numerals: {lith: ss07}\n"
        "  colour: blue\n"
        "tamil:\n"
        "  dist: 5\n", encoding="utf-8")
    path = find_config(src / "Font.glyphspackage")
    assert path == (src / "lankafea.yaml").resolve()
    cfg = load_font_config(path, "sinhala")
    assert [p.name for p in cfg.inject_paths] == ["extra.yaml"]
    assert cfg.assign["groups"][0]["group"] == "DaShape"
    assert cfg.options == {"dist": -113, "numerals": {"lith": "ss07"}}
    assert any("colour" in w for w in cfg.warnings)
    assert load_font_config(path, "tamil").options == {"dist": 5}
    assert load_font_config(None, "sinhala").options == {}

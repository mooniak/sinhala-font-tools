"""Da forms (daa._c ...): optional, in the stylistic set the standard names ("ss01 Da
Forms"), never in default shaping. Plan item G6 of the Abhaya Libre refactor."""

from __future__ import annotations

import pytest

from lankafea.api import build_fea
from lankafea.compile import strip_and_build
from lankafea.generators import da_shape_feature
from lankafea.inventory import FontInventory
from lankafea.scripts import get_profile
from lankafea.yamlloader import load_specs

from make_font import build_test_font


def layout(result):
    return {f.tag: [lk.name for lk in f.lookups] for f in result.doc.features}


def test_feature_comes_from_the_standard():
    assert da_shape_feature(load_specs(get_profile("sinhala", 3))) == "ss01"


def test_not_in_default_features():
    specs = load_specs(get_profile("sinhala", 3))
    r = build_fea("sinhala", FontInventory.from_names({g.full_name for g in specs.glyphs}))
    lay = layout(r)
    assert lay["ss01"][0] == "DaShape"
    for f in r.doc.features:
        if f.tag == "ss01":
            continue
        for lk in f.lookups:
            assert not any("._c" in str(rule.output) for rule in lk.rules), (f.tag, lk.name)


def test_no_da_forms_without_the_glyphs():
    """A Core-tier font has no ._c glyphs, so nothing is generated for them."""
    specs = load_specs(get_profile("sinhala", 1))
    r = build_fea("sinhala", FontInventory.from_names({g.full_name for g in specs.glyphs}),
                  level=1)
    assert "DaShape" not in sum(layout(r).values(), [])


@pytest.fixture(scope="module")
def shaper(tmp_path_factory):
    """Shape with a compiled test font that has every Pro glyph, Da forms copied to dlig."""
    import uharfbuzz as hb
    tmp = tmp_path_factory.mktemp("da")
    profile = get_profile("sinhala", 3)
    base = build_test_font(profile, tmp / "base.ttf")
    r = build_fea("sinhala", FontInventory.from_font(base), level=3, validate=True,
                  assign={"groups": [{"group": "DaShape", "to": "dlig", "mode": "copy"}]})
    fea = tmp / "features.fea"
    fea.write_text(r.fea, encoding="utf-8")
    out = tmp / "built.ttf"
    strip_and_build(base, fea, out)
    font = hb.Font(hb.Face(hb.Blob.from_file_path(str(out))))

    def shape(text, features=None):
        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        hb.shape(font, buf, features or {})
        return [font.glyph_to_string(i.codepoint) for i in buf.glyph_infos]
    return shape


@pytest.mark.parametrize("text,expect", [
    ("දා", "daa._c-sinh"),
    ("දැ", "dae._c-sinh"),
    ("ඤා", "nyaa._c-sinh"),
    ("න්‍දා", "nDaa._c-sinh"),
    ("දෝ", "daa_virama._c-sinh"),     # ෝ = ෙ + ා + ්: the tail after psts made aasign_virama
])
def test_shapes_only_under_ss01_or_dlig(shaper, text, expect):
    assert expect not in shaper(text)
    assert expect in shaper(text, {"ss01": True})
    assert expect in shaper(text, {"dlig": True})

"""Inject files: rule kinds, including contextual ones, render as valid .fea."""

from __future__ import annotations

from pathlib import Path

from lankafea.feacomposer_adapter import TextBackend
from lankafea.injection import _rule_from_spec, load_injection
from lankafea.scripts import get_profile


def emit(spec: dict) -> str:
    return TextBackend()._emit_rule(_rule_from_spec(spec, "sinh"))


def test_plain_rules_keep_their_kinds():
    assert _rule_from_spec({"sub": "ka", "by": "kI"}, "sinh").kind == "single"
    assert _rule_from_spec({"sub": ["ka", "isign"], "by": "kI"}, "sinh").kind == "ligature"
    assert _rule_from_spec({"sub": "kI", "by": ["ka", "isign"]}, "sinh").kind == "multiple"


def test_a_contextual_multiple_substitution():
    spec = {"sub": ["touch", "ka_repha'"], "by": ["ka", "repha-sinh.001"]}
    assert _rule_from_spec(spec, "sinh").kind == "multiple"
    assert emit(spec) == "sub touch-sinh ka_repha-sinh' by ka-sinh repha-sinh.001;"


def test_contextual_single_and_ligature_substitutions():
    single = {"sub": ["@First", "touch", "repha'"], "by": "repha-sinh.003"}
    assert _rule_from_spec(single, "sinh").kind == "single"
    assert emit(single) == "sub @First touch-sinh repha-sinh' by repha-sinh.003;"
    lig = {"sub": ["touch", "ka_repha'", "isign'"], "by": "kI"}
    assert _rule_from_spec(lig, "sinh").kind == "ligature"
    assert emit(lig) == "sub touch-sinh ka_repha-sinh' isign-sinh' by kI-sinh;"


def test_contextual_rules_compile_and_shape(tmp_path: Path):
    import uharfbuzz as hb
    from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
    from fontTools.fontBuilder import FontBuilder
    from fontTools.ttLib.tables._g_l_y_f import Glyph

    (tmp_path / "touch.yaml").write_text(
        "lookups:\n"
        "  - name: Join\n"
        "    feature: psts\n"
        "    rules:\n"
        "      - {sub: [ka, \"pa'\"], by: [pa, repha-sinh.001]}\n",
        encoding="utf-8")
    inj = load_injection([tmp_path / "touch.yaml"], get_profile("sinhala"))
    lookup = inj.doc.features[0].lookups[0]
    body = "\n".join(TextBackend()._emit_lookup(lookup, "    "))
    fea = f"languagesystem sinh dflt;\nfeature psts {{\n{body}\n}} psts;\n"

    order = [".notdef", "ka-sinh", "pa-sinh", "repha-sinh.001"]
    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap({0x0D9A: "ka-sinh", 0x0DB4: "pa-sinh"})
    fb.setupGlyf({n: Glyph() for n in order})
    fb.setupHorizontalMetrics({n: (600, 0) for n in order})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({"familyName": "T", "styleName": "Regular"})
    fb.setupOS2()
    fb.setupPost()
    addOpenTypeFeaturesFromString(fb.font, fea)
    path = tmp_path / "t.ttf"
    fb.font.save(str(path))

    font = hb.Font(hb.Face(hb.Blob.from_file_path(str(path))))
    buf = hb.Buffer()
    buf.add_str("කප")
    buf.guess_segment_properties()
    hb.shape(font, buf, {})
    assert [font.glyph_to_string(i.codepoint) for i in buf.glyph_infos] == [
        "ka-sinh", "pa-sinh", "repha-sinh.001"]

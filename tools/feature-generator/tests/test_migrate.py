"""Tamil migration: glyph/anchor renaming and the file-name convention it must not break."""

from __future__ import annotations

from lankafea.glyphspackage import escape_glyph_filename
from lankafea.migrate import _token_regex, glyph_file, plan_anchor_renames, rewrite_anchors


def test_leading_dot_is_stored_as_underscore():
    # Glyphs stores .part.al_comp as _part.al_comp.glyph; writing it back must not rename it.
    assert escape_glyph_filename(".part.al_comp") == "_part.al_comp"
    assert escape_glyph_filename(".notdef") == "_notdef"
    assert escape_glyph_filename("kSsa-taml") == "kS_sa-taml"


def test_glyph_file_matches_glyphs_convention():
    assert glyph_file("nnnAa-taml") == "nnnA_a-taml.glyph"


def test_rename_matches_whole_names_only():
    rx = _token_regex(["isign-taml.alt1"])
    assert rx.sub("X", "sub ka-taml isign-taml.alt1;") == "sub ka-taml X;"
    assert rx.sub("X", "isign-taml.alt12") == "isign-taml.alt12"
    assert rx.sub("X", "xisign-taml.alt1") == "xisign-taml.alt1"


def _glyph(*anchors):
    body = ",\n".join(f'{{\nname = "{n}";' + (f"\npos = ({p});" if p else "") + "\n}" for n, p in anchors)
    return f"anchors = (\n{body}\n);"


def test_anchor_split_for_shared_u_sign_and_missing_pos():
    texts = {
        "usign-taml": _glyph(("_Anchor-2", "-270,589")),
        "uusign-taml": _glyph(("_Anchor-2", "-270,589")),
        "usign-taml.alt1": _glyph(("_Anchor-4", None)),
        "ka-taml": _glyph(("Anchor-2", "10,20")),
    }
    mapping, problems = plan_anchor_renames(texts, {"usign-taml.alt1": "usign-taml.pa"})
    assert not problems
    assert mapping == {"Anchor-2": ["usign", "uusign"], "Anchor-4": ["usign"]}
    base = rewrite_anchors(texts["ka-taml"], mapping, False, [], "ka-taml")
    assert 'name = "usign";' in base and 'name = "uusign";' in base and "Anchor-2" not in base
    sign = rewrite_anchors(texts["usign-taml.alt1"], mapping, True, [], "usign-taml.alt1")
    assert 'name = "_usign";' in sign and "pos" not in sign       # no pos stays no pos


def test_v2_glyphs_position_lines_are_carried_over():
    # Vineetha.glyphs is the older text format: `position = "{x, y}";`, not `pos = (x,y);`
    base = 'anchors = (\n{\nname = "Anchor-0";\nposition = "{328, 476}";\n}\n);'
    out = rewrite_anchors(base, {"Anchor-0": ["virama"]}, False, [], "ka-taml")
    assert out == base.replace("Anchor-0", "virama")


def test_only_tamil_glyphs_have_anchors_renamed():
    from lankafea.migrate import is_tamil
    assert is_tamil("ka-taml") and is_tamil("isign-taml.pa")
    assert not is_tamil("ka-sinh") and not is_tamil("dottedCircle")


def test_uusign_keeps_its_own_name_when_it_shares_an_anchor_with_usign():
    text = _glyph(("_Anchor-2", "-270,589"))
    mapping = {"Anchor-2": ["usign", "uusign"]}
    assert 'name = "_uusign";' in rewrite_anchors(text, mapping, True, [], "uusign-taml", "uusign")
    assert 'name = "_usign";' in rewrite_anchors(text, mapping, True, [], "usign-taml", "usign")


def test_explicit_master_name_survives_a_rewrite():
    from lankafea.glyphspackage import restore_master_names
    before = 'id = "AAA";\nname = ExtraLight;\nuserData = {\n};'
    after = 'id = "AAA";\nuserData = {\n};'
    assert restore_master_names(before, after) == before
    assert restore_master_names(before, before) == before        # nothing to restore


def test_sinhala_names_are_renamed_too():
    # Abhaya Libre's Lith digits: sinZerolith is the standard's lithzero-sinh.
    from types import SimpleNamespace
    from lankafea.migrate import plan_glyph_renames
    inv = SimpleNamespace(glyphs={"sinZerolith", "sinOne_Zerolith", "zwj", "ka-sinh"})
    renames, problems = plan_glyph_renames(inv, {
        "lithzero-sinh": "sinZerolith",
        "lithone_lithzero-sinh": "sinOne_Zerolith",
        "zerowidthjoiner": "zwj",           # not a namespaced standard name: left alone
    })
    assert not problems
    assert renames == {"sinZerolith": "lithzero-sinh", "sinOne_Zerolith": "lithone_lithzero-sinh"}


def test_sinhala_rename_clash_is_reported():
    from types import SimpleNamespace
    from lankafea.migrate import plan_glyph_renames
    inv = SimpleNamespace(glyphs={"sinZerolith", "lithzero-sinh"})
    renames, problems = plan_glyph_renames(inv, {"lithzero-sinh": "sinZerolith"})
    assert not renames and problems and "clash" in problems[0]


def test_a_rename_that_needs_quotes_gets_them():
    # sinZerolith is written bare; its standard name has a hyphen, which Glyphs quotes.
    from lankafea.migrate import quote_bare_names
    names = ["lithzero-sinh", "lithone_lithzero-sinh"]
    glyph = "{\nglyphname = lithzero-sinh;\nlayers = (\n{\ncomponents = (\n{\nname = lithzero-sinh;\n}\n);"
    out = quote_bare_names(glyph, names)
    assert 'glyphname = "lithzero-sinh";' in out and 'name = "lithzero-sinh";' in out
    order = "(\nlithone_lithzero-sinh,\nlithzero-sinh\n)"
    assert quote_bare_names(order, names) == '(\n"lithone_lithzero-sinh",\n"lithzero-sinh"\n)'
    # already quoted, and names inside feature code, are left alone
    code = 'glyphname = "lithzero-sinh";\ncode = "sub one by lithone-sinh;\\012sub lithzero-sinh;";'
    assert quote_bare_names(code, names) == code

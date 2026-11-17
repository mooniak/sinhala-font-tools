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

"""R2: a glyph's dot-suffix may sit before the namespace (`isign.alt1-sinh`, what the
Sinhala data produces) or after it (`isign-sinh.alt1`, what docs/naming-standard.md says
and what Ralex, Maname, Dinamina and Aggnni use). Both must work.

Before this, the alternate finder only understood the first; for the second it built
rules from names like `isign-sinh-sinh` that matched nothing, dropped them silently and
listed them as blockers."""

from __future__ import annotations

import pytest

from lankafea.api import build_fea, validate_font
from lankafea.inventory import FontInventory
from lankafea.names import split_ns, with_ns
from lankafea.nameparse import parse

from lankafea.scripts import SINHALA

BASE = {"zerowidthjoiner", "isign-sinh", "fa-sinh"}
BEFORE = BASE | {"isign.alt1-sinh", "isign.alt2-sinh", "fa.alt-sinh"}     # suffix before
AFTER = BASE | {"isign-sinh.alt1", "isign-sinh.alt2", "fa-sinh.alt"}       # suffix after


def test_split_ns_reads_both_positions():
    assert split_ns("ka-sinh", "sinh") == ("ka", "")
    assert split_ns("isign.alt3-sinh", "sinh") == ("isign", "alt3")
    assert split_ns("isign-sinh.alt3", "sinh") == ("isign", "alt3")
    assert split_ns("isign-taml.ka", "taml") == ("isign", "ka")
    assert split_ns("ka_repha-sinh.001", "sinh") == ("ka_repha", "001")
    assert split_ns("zerowidthjoiner", "sinh") is None
    assert split_ns("ka-taml", "sinh") is None
    assert split_ns("ka-sinhala", "sinh") is None            # not the namespace


def test_with_ns_places_the_dot_suffix_as_asked():
    assert with_ns("isign.ka", "taml") == "isign.ka-taml"                     # the legacy order
    assert with_ns("isign.ka", "taml", dot_after=True) == "isign-taml.ka"
    assert with_ns("ka", "taml", dot_after=True) == "ka-taml"


@pytest.mark.parametrize("names", [BEFORE, AFTER], ids=["suffix-before", "suffix-after"])
def test_alternates_become_aalt_and_stylistic_sets_in_both_spellings(names):
    fea = build_fea("sinhala", FontInventory.from_names(names), level=3).fea
    assert "-sinh-sinh" not in fea                          # the old bug
    alt1 = "isign.alt1-sinh" if "isign.alt1-sinh" in names else "isign-sinh.alt1"
    alt2 = alt1.replace("alt1", "alt2")
    assert f"sub isign-sinh from [isign-sinh {alt1} {alt2}];" in fea
    assert f"sub isign-sinh by {alt1};" in fea              # ss01
    assert f"sub isign-sinh by {alt2};" in fea              # ss02
    fa = "fa.alt-sinh" if "fa.alt-sinh" in names else "fa-sinh.alt"
    assert f"sub fa-sinh by {fa};" in fea                   # alt (no number) is index 1


def test_both_spellings_give_the_same_structure():
    def shape(names):
        r = build_fea("sinhala", FontInventory.from_names(names), level=3)
        return {f.tag: [len(lk.rules) for lk in f.lookups] for f in r.doc.features
                if f.tag in ("aalt", "ss01", "ss02")}
    assert shape(BEFORE) == shape(AFTER) != {}


def test_the_bogus_blockers_are_gone():
    report = validate_font("sinhala", FontInventory.from_names(AFTER), level=3)
    assert not any("sinh-sinh" in b.glyph or "sinh.alt-sinh" in b.glyph for b in report.blockers)
    assert report.per_feature["aalt"].satisfiable > 0


def test_orphan_detection_sees_a_suffix_after_the_namespace():
    names = BASE | {"rasign-sinh.long", "ka_repha-sinh.001", "ka_repha-sinh"}
    report = validate_font("sinhala", FontInventory.from_names(names), level=3)
    orphans = {o.glyph: o.reason for o in report.orphans}
    assert "rasign-sinh.long" in orphans
    assert "ka_repha-sinh.001" in orphans
    assert "numbered variant .001" in orphans["ka_repha-sinh.001"]


def test_names_parse_the_same_in_either_position():
    a = parse("isign.alt1-sinh", SINHALA, "sinh")
    b = parse("isign-sinh.alt1", SINHALA, "sinh")
    assert a is not None and b is not None and a.description == b.description
    assert parse("ka_repha-sinh.001", SINHALA, "sinh").kind == "alt"

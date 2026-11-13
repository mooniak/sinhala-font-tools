"""Feature assignments: rule groups and alternate indices routed to dlig / ssNN."""

from __future__ import annotations

import pytest

from lankafea.api import build_fea, describe_assignables
from lankafea.assign import parse_assign
from lankafea.inventory import FontInventory
from lankafea.scripts import get_profile
from lankafea.yamlloader import load_specs


@pytest.fixture(scope="module")
def inv():
    specs = load_specs(get_profile("sinhala", 3))
    names = {g.full_name for g in specs.glyphs}
    names |= {"zerowidthjoiner", "touch-sinh", "rasign-sinh", "repha-sinh",
              "yasign-sinh", "isign.alt-sinh", "isign.alt2-sinh",
              "isign.alt3-sinh", "kasign.alt2-sinh"}
    return FontInventory.from_names(names)


def layout(result):
    return {f.tag: [lk.name for lk in f.lookups] for f in result.doc.features}


def test_default_unchanged(inv):
    lay = layout(build_fea("sinhala", inv))
    assert lay["ss01"] == ["StylisticSet01"] and lay["ss02"] == ["StylisticSet02"]
    assert "dlig" not in lay


def test_move_group_to_dlig(inv):
    r = build_fea("sinhala", inv, assign={
        "groups": [{"group": "VowelLig_blws", "to": "dlig"}]})
    lay = layout(r)
    assert lay["dlig"] == ["VowelLig_blws"]
    assert "blws" not in lay                       # emptied feature disappears
    assert "feature dlig" in r.fea


def test_consumer_warning(inv):
    r = build_fea("sinhala", inv, assign={
        "groups": [{"group": "RakarLigatures", "to": "dlig"}]})
    assert any("RakarLigatures" in w and "VowelLig_psts" in w
               for w in r.assign_warnings)


def test_copy_keeps_original(inv):
    lay = layout(build_fea("sinhala", inv, assign={
        "groups": [{"group": "RakarLigatures", "to": "ss05", "mode": "copy"}]}))
    assert "RakarLigatures" in lay["vatu"]
    assert lay["ss05"] == ["RakarLigatures_ss05"]


def test_alt_index_to_dlig_and_none(inv):
    r = build_fea("sinhala", inv, assign={"alts": {"2": "dlig", "3": "none"}})
    lay = layout(r)
    assert lay["dlig"] == ["Alternates02_dlig"]
    assert "ss02" not in lay and "ss03" not in lay and "ss01" in lay
    assert "AllAlternates" in lay["aalt"]          # aalt still sees every alternate


def test_unknown_input_is_warning_not_error(inv):
    r = build_fea("sinhala", inv, assign={
        "groups": [{"group": "NoSuch", "to": "dlig"},
                   {"group": "TouchLigatures", "to": "bogus"}],
        "alts": {"x": "ss01", "4": "nope"}})
    text = " ".join(r.assign_warnings)
    assert "NoSuch" in text and "bogus" in text and "nope" in text
    assert "dlig" not in layout(r)


def test_parse_roundtrip():
    a = parse_assign({"groups": [{"group": "G", "to": "ss03"}], "alts": {"2": "dlig"}})
    assert parse_assign(a.to_plain()).to_plain() == a.to_plain()


def test_describe_assignables(inv):
    d = describe_assignables("sinhala", inv)
    names = {g.name for g in d.groups}
    assert {"TouchLigatures", "RakarLigatures", "VowelLig_abvs"} <= names
    assert [(a.index, a.count) for a in d.alts] == [(1, 1), (2, 2), (3, 1)]

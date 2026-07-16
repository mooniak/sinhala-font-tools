"""Shape-group variant selection + class harvest."""

from __future__ import annotations

from mnik.lankaglyphsets.adaptation import _matching_class, add_variant_selection
from mnik.lankaglyphsets.inventory import FontInventory
from mnik.lankaglyphsets.model import FeatureDoc
from mnik.lankaglyphsets.scripts import get_profile


def test_matching_class_noto_vocabulary():
    classes = ["uSignAlt2Group", "uSignAlt3Group", "iVowelAlt2", "iVowelAlt",
               "rephAltGroup", "rakarAlt3Group", "vaShapeGroup"]
    assert _matching_class("usign", 2, classes) == "uSignAlt2Group"
    assert _matching_class("iisign", 2, classes) == "iVowelAlt2"
    assert _matching_class("isign", 1, classes) == "iVowelAlt"       # digit-less = alt1
    assert _matching_class("repha", 1, classes) == "rephAltGroup"
    assert _matching_class("rasign", 3, classes) == "rakarAlt3Group"
    assert _matching_class("usign", 9, classes) is None


def test_variant_selection_rules_and_findings():
    profile = get_profile("sinhala", 3)
    inv = FontInventory(
        glyphs={"ka-sinh", "usign-sinh", "usign-sinh.alt2", "isign-sinh.alt3"},
        cmap=set(),
        source_classes={"uSignAlt2Group": ["ka-sinh"]},
    )
    doc = FeatureDoc()
    findings = add_variant_selection(doc, profile, inv)

    blws = next(f for f in doc.features if f.tag == "blws")
    rule = blws.lookups[0].rules[0]
    assert rule.inputs == ["@uSignAlt2Group", "usign-sinh'"]
    assert rule.output == "usign-sinh.alt2"
    # harvested class is registered for gating/serialization
    assert any(c.name == "uSignAlt2Group" for c in doc.classes)
    # isign.alt3 has no class -> reported, not guessed
    assert any("isign-sinh.alt3" in f for f in findings)

"""Glyph-info validation: Sinhala dependent vowel signs must be *spacing marks*.

The Sinhala matras (dependent vowel signs) below advance the pen — they are
Category **Mark**, Subcategory **Spacing** in Glyphs. If a source leaves that glyph
info unset (Glyphs then auto-guesses, often as *Letter* or a *Nonspacing* mark) the
GDEF class comes out wrong, which breaks mark positioning and cursor movement.

This validator reports every target sign, present in the source, whose Category /
Subcategory is not exactly Mark / Spacing (unset counts as wrong). It needs the
per-glyph info a Glyphs source carries (``FontInventory.glyph_info``); on a compiled
binary that info is absent, so the check is skipped.
"""

from __future__ import annotations

from dataclasses import dataclass

EXPECTED_CATEGORY = "Mark"
EXPECTED_SUBCATEGORY = "Spacing"

# Sinhala dependent vowel signs that must be spacing marks (LankaGlyphset -sinh
# namespace). Order preserved for stable reporting.
SPACING_MARK_GLYPHS: list[str] = [
    "aaesign-sinh",
    "aesign-sinh",
    "aisign-sinh",
    "ausign-sinh",
    "esign-sinh",
    "eesign-sinh",
    "vocalicllsign-sinh",
    "vocaliclsign-sinh",
    "osign-sinh",
    "oosign-sinh",
    "vocalicrsign-sinh",
    "vocalicrrsign-sinh",
    "usign.rasign-sinh",
    "uusign.rasign-sinh",
    "aasign-sinh",
    "aasign_virama-sinh",
    "yasign-sinh",
    "anusvaraya-sinh",
    "visargaya-sinh",
]


@dataclass
class GlyphInfoFinding:
    """One target sign whose glyph info is not Mark / Spacing."""

    glyph: str
    category: str | None
    sub_category: str | None

    @property
    def category_ok(self) -> bool:
        return self.category == EXPECTED_CATEGORY

    @property
    def subcategory_ok(self) -> bool:
        return self.sub_category == EXPECTED_SUBCATEGORY

    @property
    def reason(self) -> str:
        parts = []
        if not self.category_ok:
            parts.append(f"Category={self.category or 'unset'} (want {EXPECTED_CATEGORY})")
        if not self.subcategory_ok:
            parts.append(f"Subcategory={self.sub_category or 'unset'} "
                         f"(want {EXPECTED_SUBCATEGORY})")
        return "; ".join(parts)

    def to_dict(self) -> dict:
        return {"glyph": self.glyph, "category": self.category,
                "sub_category": self.sub_category, "reason": self.reason}


def check_glyph_info(present: set[str],
                     glyph_info: dict[str, dict] | None) -> dict:
    """Flag present target signs whose Category/Subcategory is not Mark/Spacing.

    ``glyph_info`` maps glyph name -> ``{"category", "subCategory"}`` (from a Glyphs
    source). Returns a summary dict::

        {"available": bool,      # False when the source carries no glyph info
         "present": int,         # target signs found in the font
         "ok": int,              # of those, correctly Mark/Spacing
         "findings": [ {glyph, category, sub_category, reason}, ... ]}

    Absent target glyphs are ignored — their non-existence is the dependency
    validator's concern, not this one's.
    """
    if not glyph_info:
        return {"available": False, "present": 0, "ok": 0, "findings": []}
    present_targets = [g for g in SPACING_MARK_GLYPHS if g in present]
    findings: list[GlyphInfoFinding] = []
    for name in present_targets:
        info = glyph_info.get(name) or {}
        finding = GlyphInfoFinding(name, info.get("category"), info.get("subCategory"))
        if not (finding.category_ok and finding.subcategory_ok):
            findings.append(finding)
    return {
        "available": True,
        "present": len(present_targets),
        "ok": len(present_targets) - len(findings),
        "findings": [f.to_dict() for f in findings],
    }

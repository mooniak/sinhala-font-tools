"""Fix Category/Subcategory on the Sinhala spacing-mark signs.

Companion to ``glyphinfo.check_glyph_info`` — that module only reports; this one
sets ``category``/``subCategory`` on the glyph object so the source actually
carries the info Glyphs would otherwise auto-guess (often wrong; see
``glyphinfo.py`` docstring).
"""

from __future__ import annotations

from pathlib import Path

from .glyphinfo import SPACING_MARK_GLYPHS

EXPECTED_CATEGORY = "Mark"
EXPECTED_SUBCATEGORY = "Spacing"

# The Sinhala dependent vowel signs + other spacing marks this fix targets —
# the full glyphinfo.check_glyph_info() set, so nothing it reports is ever
# left as an "outside fix-source's target list" note.
TARGET_GLYPHS: list[str] = SPACING_MARK_GLYPHS


def fix_glyph_info(font, names: list[str] = TARGET_GLYPHS,
                    category: str = EXPECTED_CATEGORY,
                    sub_category: str = EXPECTED_SUBCATEGORY) -> list[str]:
    """Set Category/Subcategory on present target glyphs in a loaded GSFont.

    Returns the list of glyph names actually changed (already-correct glyphs
    are left untouched and not counted).
    """
    targets = set(names)
    changed: list[str] = []
    for glyph in font.glyphs:
        if glyph.name not in targets:
            continue
        if glyph.category == category and glyph.subCategory == sub_category:
            continue
        glyph.category = category
        glyph.subCategory = sub_category
        changed.append(glyph.name)
    return changed


NBSPACE_UNICODE = "00A0"

# name -> (unicode, fixed width per master). CR/NULL widths vary wildly across
# existing sources (0/600/682 seen) with no consistent derivation, so newly
# created ones get 0 (non-rendering control characters, matching
# zerowidthjoiner/zerowidthnonjoiner's convention) — user-confirmed default.
# Existing CR/NULL glyphs are left untouched (only missing ones are created).
FIXED_WIDTH_CONTROL_GLYPHS: list[tuple[str, str, int]] = [
    ("CR", "000D", 0),
    ("NULL", "0000", 0),
]


def _add_missing_glyph(font, name: str, unicode_value: str, width: int) -> bool:
    if any(g.name == name for g in font.glyphs):
        return False
    from glyphsLib.classes import GSGlyph, GSLayer

    glyph = GSGlyph(name)
    glyph.unicode = unicode_value
    for master in font.masters:
        layer = GSLayer()
        layer.layerId = master.id
        layer.width = width
        glyph.layers.append(layer)
    font.glyphs.append(glyph)
    return True


def fix_font_extras(font) -> list[str]:
    """Set fsType to no-embedding-restrictions; ensure ``nbspace`` (U+00A0)
    exists with the same per-master width as ``space``; ensure ``CR``/``NULL``
    (U+000D/U+0000) exist (zero-width if newly created).

    Returns the list of fields/glyphs actually changed.
    """
    changed: list[str] = []

    if font.customParameters["fsType"] != []:
        font.customParameters["fsType"] = []
        changed.append("fsType")

    space = next((g for g in font.glyphs if g.name == "space"), None)
    if space is not None:
        nbspace = next((g for g in font.glyphs if g.name == "nbspace"), None)
        if nbspace is None:
            from glyphsLib.classes import GSGlyph, GSLayer

            nbspace = GSGlyph("nbspace")
            nbspace.unicode = NBSPACE_UNICODE
            for space_layer in space.layers:
                layer = GSLayer()
                layer.layerId = space_layer.layerId
                layer.width = space_layer.width
                nbspace.layers.append(layer)
            font.glyphs.append(nbspace)
            changed.append("nbspace (created)")
        else:
            for space_layer in space.layers:
                nb_layer = next((l for l in nbspace.layers
                                 if l.layerId == space_layer.layerId), None)
                if nb_layer is not None and nb_layer.width != space_layer.width:
                    nb_layer.width = space_layer.width
                    changed.append("nbspace width")

    for name, unicode_value, width in FIXED_WIDTH_CONTROL_GLYPHS:
        if _add_missing_glyph(font, name, unicode_value, width):
            changed.append(f"{name} (created)")

    if _fix_blank_notdef(font):
        changed.append(".notdef (design filled in)")
    if _add_mooniak_brand_glyph(font):
        changed.append("mooniak (created)")

    return changed


def _bundled_glyph(name: str):
    """Parse a bundled data/glyphs/<name>.glyph file into a fresh GSGlyph.

    Bundled files are v3 syntax (see zwjfix.py); parsed fresh on every call so
    layer objects taken from it are safe to mutate/move without cross-font
    contamination.
    """
    from importlib import resources

    from glyphsLib.classes import GSGlyph
    from glyphsLib.parser import Parser

    ref = resources.files("mnik.lankaglyphsets").joinpath(f"data/glyphs/{name}.glyph")
    text = ref.read_text(encoding="utf-8")
    return Parser(current_type=GSGlyph, format_version=3).parse(text)


def _remapped_layers(bundled, master_ids: list[str]):
    """Bundled glyph's layers, retargeted onto ``master_ids`` (in order,
    duplicating the last bundled layer if there are more target masters than
    bundled layers — same convention as zwjfix's ``_remap_layers``)."""
    bundled_layers = list(bundled.layers)
    out = []
    for idx, mid in enumerate(master_ids):
        layer = bundled_layers[min(idx, len(bundled_layers) - 1)]
        layer.layerId = mid
        layer.associatedMasterId = ""
        out.append(layer)
    return out


def _fix_blank_notdef(font) -> bool:
    """Fill in a BLANK ``.notdef`` with the bundled Mooniak design.

    Fonts that already have their own (non-blank) .notdef artwork are left
    untouched — this only backfills the empty-box QA gap, it does not impose
    one design on every font.
    """
    notdef = next((g for g in font.glyphs if g.name == ".notdef"), None)
    if notdef is None or not notdef.layers:
        return False
    is_blank = all(not layer.shapes for layer in notdef.layers)
    if not is_blank:
        return False
    master_ids = [layer.layerId for layer in notdef.layers]
    notdef.layers = _remapped_layers(_bundled_glyph("_notdef"), master_ids)
    return True


def _add_mooniak_brand_glyph(font) -> bool:
    """Add the bundled ``mooniak`` brand glyph if the font has neither it nor
    the newer ``pushpa-lksymbol`` brand mark."""
    if any(g.name in ("mooniak", "pushpa-lksymbol") for g in font.glyphs):
        return False
    master_ids = [m.id for m in font.masters]
    if not master_ids:
        return False
    from glyphsLib.classes import GSGlyph

    glyph = GSGlyph("mooniak")
    for layer in _remapped_layers(_bundled_glyph("mooniak"), master_ids):
        glyph.layers.append(layer)
    font.glyphs.append(glyph)
    return True

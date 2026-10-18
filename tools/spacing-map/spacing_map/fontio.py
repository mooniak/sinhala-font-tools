"""Reading side of the .glyphspackage: sidebearings and metrics keys.

Sidebearings are NOT stored in a Glyphs source — only each layer's `width` is.
LSB/RSB are derived from the layer's outline bounds, exactly as Glyphs displays
them: LSB = bounds.x, RSB = width - (bounds.x + bounds.width). glyphsLib
resolves component references when computing bounds, so composites measure
correctly. Empty layers (no contours, no components) have no sidebearings.

Metrics keys live at glyph level (`leftMetricsKey`) and may be overridden per
layer. A key is normally a glyph name — that is the inheritance this tool
writes — but Glyphs also accepts formulae (`=|H`, `=ka-sinh+10`), so keys are
reported verbatim and only compared as equal/not-equal to the expected name.
"""
from glyphsLib import GSFont


def load_font(path):
    return GSFont(str(path))


def masters(font):
    return [(m.id, m.name) for m in font.masters]


def glyph_index(font):
    """name -> GSGlyph, plus codepoint -> name for unicode resolution."""
    by_name = {g.name: g for g in font.glyphs}
    by_unicode = {}
    for g in font.glyphs:
        for u in (g.unicodes or ([g.unicode] if g.unicode else [])):
            try:
                by_unicode.setdefault(int(u, 16), g.name)
            except (TypeError, ValueError):
                continue
    return by_name, by_unicode


def layer_of(glyph, master_id):
    return next((l for l in glyph.layers if l.layerId == master_id), None)


def sidebearings(layer):
    """-> {'width', 'lsb', 'rsb'} or None when the layer is empty/missing."""
    if layer is None:
        return None
    bounds = layer.bounds
    if bounds is None:
        return None
    origin, size = bounds.origin, bounds.size
    if size.width == 0 and size.height == 0:
        return None
    return {
        "width": round(layer.width, 1),
        "lsb": round(origin.x, 1),
        "rsb": round(layer.width - (origin.x + size.width), 1),
    }


def metrics_keys(glyph, layer):
    """-> {'left': (value, scope), 'right': (value, scope)}; scope is 'layer',
    'glyph' or None. A layer key overrides the glyph-level one."""
    out = {}
    for side, attr in (("left", "leftMetricsKey"), ("right", "rightMetricsKey")):
        lv = getattr(layer, attr, None) if layer is not None else None
        gv = getattr(glyph, attr, None)
        if lv:
            out[side] = (lv, "layer")
        elif gv:
            out[side] = (gv, "glyph")
        else:
            out[side] = (None, None)
    return out

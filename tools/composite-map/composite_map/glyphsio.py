"""Thin helpers over glyphsLib for reading/classifying glyph layers.

Kept separate so both the read-only map builder and the mutating rebuild
engine share one definition of "atomic / composite / mixed".
"""
from glyphsLib import GSFont


def load_font(path):
    return GSFont(str(path))


def master_layer(glyph, master_id):
    """The layer for a given master id, or None if the glyph lacks one."""
    return next((layer for layer in glyph.layers if layer.layerId == master_id), None)


def layer_class(layer):
    """Structural class of a single layer.

    - composite: only component references, no drawn contours
    - atomic:    only drawn contours (single/merged outline), no components
    - mixed:     both — typically a base component plus a still-drawn sign
    - empty:     neither
    """
    if layer is None:
        return "missing"
    n_paths = len(layer.paths)
    n_comps = len(layer.components)
    if n_paths and n_comps:
        return "mixed"
    if n_comps:
        return "composite"
    if n_paths:
        return "atomic"
    return "empty"


def glyph_class(glyph, master_id):
    return layer_class(master_layer(glyph, master_id))


def is_sinhala(name):
    """Glyph names in these sources carry a script suffix, e.g. `ka-sinh`,
    `kU-sinh`, `ka_repha-sinh.hist`."""
    return name.endswith("-sinh") or "-sinh." in name


def component_names(layer):
    if layer is None:
        return []
    return [c.name for c in layer.components]


def anchor_names(layer):
    if layer is None:
        return []
    return [a.name for a in layer.anchors]

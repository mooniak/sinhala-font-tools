"""Surgical writer for the .glyphspackage directory format.

glyphsLib can *read* a .glyphspackage but its GSFont.save() only writes a single
.glyphs file. A package stores every glyph as an independent openstep-plist
`glyphs/<mangled-name>.glyph` file, so we rewrite only the glyph files we change
— leaving fontinfo.plist, order.plist and every untouched glyph byte-for-byte.

Each layer entry in a v2/v3 glyph file carries `paths` and/or `components`
arrays plus its own `width`. To turn a drawn glyph into a composite we drop
`paths`, set `components`, and keep the existing `width` (drawn Sinhala base+mark
forms already advance by the base width, so the width is already correct).
Output uses indent=0, which reproduces the Glyphs-native one-entry-per-line
layout and alphabetical key order.
"""
from pathlib import Path

import openstep_plist


def is_package(path):
    p = Path(path)
    return p.is_dir() and (p / "glyphs").is_dir()


def glyph_dir(path):
    return Path(path) / "glyphs"


def build_name_to_file(package_path, only_names=None):
    """Map glyph name -> .glyph file Path. `only_names`, if given, short-circuits
    once every requested name is found (the glyph name is always the first key)."""
    wanted = set(only_names) if only_names is not None else None
    out = {}
    for gf in sorted(glyph_dir(package_path).glob("*.glyph")):
        name = _read_glyphname(gf)
        if name is None:
            continue
        out[name] = gf
        if wanted is not None and wanted.issubset(out.keys()):
            break
    return out


def _read_glyphname(glyph_file):
    with open(glyph_file, "r", encoding="utf-8") as fh:
        data = openstep_plist.load(fh, use_numbers=True)
    return data.get("glyphname")


def rewrite_as_composite(glyph_file, components):
    """Replace every layer's drawn contours with the given component references.
    Returns the number of layers changed."""
    with open(glyph_file, "r", encoding="utf-8") as fh:
        data = openstep_plist.load(fh, use_numbers=True)

    comp_entries = [{"name": c} for c in components]
    changed = 0
    for layer in data.get("layers", []):
        had = ("paths" in layer) or ("shapes" in layer) or ("components" in layer)
        layer.pop("paths", None)
        # v3 unifies contours + components under `shapes`; drop it too and use
        # the explicit `components` key (both v2 and v3 accept `components`).
        layer.pop("shapes", None)
        layer["components"] = [dict(e) for e in comp_entries]
        if had:
            changed += 1

    with open(glyph_file, "w", encoding="utf-8") as fh:
        openstep_plist.dump(data, fh, indent=0)
    return changed

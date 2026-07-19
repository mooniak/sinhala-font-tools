"""Audit and rebuild engine.

Takes a composite map (built from the reference sources) and applies it to ANY
target Glyphs source: for each mapped composite whose target glyph is currently
drawn atomically (single/merged outline) or mixed (base component + still-drawn
sign), it deletes the drawn contours and replaces them with the base + sign
component references from the map, in every master layer.

Positioning of sign components relies on the target font's own base/mark anchors
(Glyphs auto-aligns matching anchor/_anchor pairs on open); the engine sets the
layer advance width from the base glyph so metrics survive the swap.

`audit()` is read-only. `plan()` computes the edits without writing. `apply()`
performs them and saves.
"""
import shutil
from collections import Counter
from pathlib import Path

from glyphsLib import GSComponent

from . import glyphsio, packageio


def _target_class(font_glyphs_by_name, name, master_ids):
    glyph = font_glyphs_by_name.get(name)
    if glyph is None:
        return "missing"
    # classify on the first master that has a layer
    for mid in master_ids:
        layer = glyphsio.master_layer(glyph, mid)
        if layer is not None:
            return glyphsio.layer_class(layer)
    return "missing"


def audit(font_path, map_data):
    """Read-only: classify every mapped composite against the target font."""
    font = glyphsio.load_font(font_path)
    by_name = {g.name: g for g in font.glyphs}
    master_ids = [m.id for m in font.masters]
    composites = map_data["composites"]

    rows = []
    status_counts = Counter()
    for name, spec in sorted(composites.items()):
        comps = spec["components"]
        klass = _target_class(by_name, name, master_ids)
        missing_comps = [c for c in comps if c not in by_name]
        if klass == "missing":
            status = "absent"          # target glyph not in this font
        elif missing_comps:
            status = "blocked"         # can't build: component(s) missing
        elif klass == "composite":
            status = "already"         # already a composite
        else:
            status = "rebuildable"     # atomic/mixed/empty -> can rebuild
        status_counts[status] += 1
        rows.append({
            "name": name, "components": comps, "class": klass,
            "status": status, "missing_components": missing_comps, "tier": spec["tier"],
        })
    return {
        "font": Path(font_path).name,
        "masters": [m.name for m in font.masters],
        "status_counts": dict(status_counts),
        "rows": rows,
    }


def plan(font_path, map_data, include_tiers=(0, 1, 2)):
    """Which glyphs would be rebuilt, and how, without writing."""
    a = audit(font_path, map_data)
    edits = [
        r for r in a["rows"]
        if r["status"] == "rebuildable" and r["tier"] in include_tiers
    ]
    return {"font": a["font"], "masters": a["masters"], "edits": edits,
            "status_counts": a["status_counts"]}


def apply(font_path, map_data, include_tiers=(0, 1, 2), backup=False):
    """Perform the rebuild and save in place.

    Dispatches on source format: a .glyphspackage directory is edited glyph-file
    by glyph-file (glyphsLib cannot write packages); a single .glyphs file is
    mutated and saved through glyphsLib.
    """
    font_path = Path(font_path)
    backup_made = _make_backup(font_path) if backup else None

    p = plan(font_path, map_data, include_tiers=include_tiers)
    edits = p["edits"]  # already rebuildable (glyph present, components present)

    if packageio.is_package(font_path):
        changed = _apply_package(font_path, edits)
    else:
        changed = _apply_glyphs_file(font_path, edits)

    return {"font": font_path.name, "changed": changed,
            "status_counts": p["status_counts"], "backup": backup_made}


def _apply_package(font_path, edits):
    names = [e["name"] for e in edits]
    name_to_file = packageio.build_name_to_file(font_path, only_names=names)
    changed = []
    for e in edits:
        gf = name_to_file.get(e["name"])
        if gf is None:
            continue
        layers = packageio.rewrite_as_composite(gf, e["components"])
        changed.append({"name": e["name"], "components": e["components"], "layers": layers})
    return changed


def _apply_glyphs_file(font_path, edits):
    font = glyphsio.load_font(font_path)
    by_name = {g.name: g for g in font.glyphs}
    master_ids = [m.id for m in font.masters]
    changed = []
    for e in edits:
        glyph = by_name.get(e["name"])
        if glyph is None:
            continue
        edited = 0
        for layer in glyph.layers:
            _rebuild_layer(layer, e["components"])
            edited += 1
        changed.append({"name": e["name"], "components": e["components"], "layers": edited})
    if changed:
        font.save(str(font_path))
    return changed


def _rebuild_layer(layer, comps):
    """Drop drawn contours (keeping the existing advance width) and set the
    given component references."""
    try:
        layer.paths = []
    except (TypeError, AttributeError):
        for pth in list(layer.paths):
            layer.paths.remove(pth)
    try:
        layer.components = []
    except (TypeError, AttributeError):
        for c in list(layer.components):
            layer.components.remove(c)
    for comp_name in comps:
        component = GSComponent(comp_name)
        try:
            component.automaticAlignment = True  # anchor-driven mark alignment
        except AttributeError:
            pass
        layer.components.append(component)


def _make_backup(font_path):
    dst = _backup_path(font_path)
    if font_path.is_dir():
        shutil.copytree(font_path, dst)
    else:
        shutil.copy2(font_path, dst)
    return str(dst)


def _backup_path(font_path):
    n = 1
    while True:
        candidate = font_path.with_name(f"{font_path.name}.bak{n}")
        if not candidate.exists():
            return candidate
        n += 1

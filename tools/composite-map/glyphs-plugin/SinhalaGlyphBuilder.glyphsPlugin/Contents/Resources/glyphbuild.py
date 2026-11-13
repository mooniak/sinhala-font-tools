# encoding: utf-8
"""Font bridge for the Sinhala Glyph Builder (main thread only).

Turns the pure decisions of sinhala_glyph_builder/buildplan.py (composites)
and sinhala_glyph_builder/catalogue.py (what may be added) into edits of a
GSFont: seeding sign variants, building composites, creating drawn glyphs and
recording features decisions.
"""

from __future__ import division, print_function, unicode_literals

import copy
import json
import os

from GlyphsApp import Glyphs, GSGlyph, GSComponent

from sinhala_glyph_builder import buildplan, catalogue

_RES = os.path.dirname(os.path.abspath(__file__))
TITLE = "Sinhala Glyph Builder"
FEATURES_KEY = "com.mooniak.SinhalaGlyphBuilder.features"
SEED_COLOR = 1          # orange: seeded sign variant, needs design
SEED_NOTE = "Seeded from %s by Sinhala Glyph Builder — redesign as the %s variant."
PARTS_NOTE = "Started from %s by Sinhala Glyph Builder — draw it as one glyph."
ACTION_LABEL = {"create": "create", "rebuild": "fill/replace", "update": "update"}
KEY_ATTRS = ("leftMetricsKey", "rightMetricsKey", "widthMetricsKey")


def _load(name):
    with open(os.path.join(_RES, "sinhala_glyph_builder", name), encoding="utf-8") as f:
        return json.load(f)


def load_map():
    return _load("map.json")


def load_catalogue():
    return _load("catalogue.json")


# --------------------------------------------------------------------------- #
# Reading the font
# --------------------------------------------------------------------------- #

def glyph_names(font):
    return {g.name for g in font.glyphs if g.name}


# font.tempData key: the glyph names a font had when last checked
KNOWN_KEY = "com.mooniak.SinhalaGlyphBuilder.knownGlyphs"


def known_names(font):
    """The glyph names `font` had when last checked, or None on first sight.

    Kept in the font's own tempData (never saved, dies with the font), so a
    font is only ever compared with itself. Keying a dict by id(font) broke
    that: id() of a transient PyObjC proxy gets reused, so a freshly opened
    font could be diffed against another font's list, and every composite
    the other font lacked looked "new" and was rebuilt."""
    try:
        names = font.tempData[KNOWN_KEY]
    except (KeyError, TypeError, AttributeError):
        return None
    return None if names is None else set(names)


def remember_names(font, names=None):
    font.tempData[KNOWN_KEY] = sorted(glyph_names(font) if names is None
                                      else names)


def designed_names(font):
    """Glyphs with outlines on at least one master — their own, or through
    components (a composite of still-empty parts is not designed yet)."""
    ids = [m.id for m in font.masters]
    memo = {}

    def designed(glyph, seen):
        name = glyph.name
        if name in memo:
            return memo[name]
        memo[name] = False
        result = False
        for mid in ids:
            layer = glyph.layers[mid]
            if layer is None:
                continue
            if layer.paths:
                result = True
                break
            for comp in layer.components:
                base = font.glyphs[comp.componentName]
                if base is not None and name not in seen and designed(base, seen | {name}):
                    result = True
                    break
            if result:
                break
        memo[name] = result
        return result

    return {g.name for g in font.glyphs if g.name and designed(g, frozenset())}


def font_state(font):
    """exists(name) / state(name) callables for buildplan.plan()."""
    def exists(name):
        return font.glyphs[name] is not None

    def state(name):
        glyph = font.glyphs[name]
        if glyph is None:
            return ("absent",)
        comps = None
        base_aligned = False
        for m in font.masters:
            layer = glyph.layers[m.id]
            if layer is None:
                continue
            if any(not isinstance(s, GSComponent) for s in layer.shapes):
                return ("drawn",)
            if comps is None and layer.components:
                comps = [c.componentName for c in layer.components]
                base_aligned = bool(layer.components[0].automaticAlignment)
        return ("composite", comps, base_aligned) if comps else ("empty",)
    return exists, state


def recorded_features(font):
    """Names recorded as made by features (no precomposed glyph)."""
    return set(font.userData[FEATURES_KEY] or ())


def set_recorded_features(font, names):
    if names:
        font.userData[FEATURES_KEY] = sorted(names)
    elif font.userData[FEATURES_KEY] is not None:
        del font.userData[FEATURES_KEY]


# --------------------------------------------------------------------------- #
# Composites
# --------------------------------------------------------------------------- #

def build_plan(font, cmap, targets=None, overwrite=False):
    exists, state = font_state(font)
    return buildplan.plan(cmap, exists, state, targets=targets, overwrite=overwrite)


def _clear(layer):
    for shape in list(layer.shapes):
        layer.shapes.remove(shape)


def seed_variant(font, variant, source, slot):
    """Create `variant` as a copy of `source` on every master, flagged for
    redesign."""
    src = font.glyphs[source]
    glyph = GSGlyph(variant)
    font.glyphs.append(glyph)
    glyph.color = SEED_COLOR
    glyph.note = SEED_NOTE % (source, slot)
    for m in font.masters:
        s, layer = src.layers[m.id], glyph.layers[m.id]
        if s is None or layer is None:
            continue
        for shape in s.shapes:
            layer.shapes.append(copy.copy(shape))
        for anchor in s.anchors:
            layer.anchors.append(copy.copy(anchor))
        layer.width = s.width


def _key_targets_drawn(font, glyph, layer, master_id):
    """True when every plain-name metrics key on the glyph/layer points at a
    glyph with outlines on this master — syncing against an empty glyph would
    collapse the sidebearing. Formula keys are left to Glyphs."""
    for attr in KEY_ATTRS:
        for key in (getattr(glyph, attr), getattr(layer, attr)):
            name = (key or "").lstrip("=").strip()
            target = font.glyphs[name] if name else None
            if target is not None and not (target.layers[master_id] and
                                           target.layers[master_id].shapes):
                return False
    return True


def _has_keys(glyph, layer):
    return any(getattr(glyph, a) or getattr(layer, a) for a in KEY_ATTRS)


def build_glyph(font, name, components, align):
    """Make `name` exactly base + sign components on every master. Signs align
    to the base's anchors; the base itself is auto-aligned only for
    ALIGN_ALL (spacing sign). One undo step."""
    glyph = font.glyphs[name]
    if glyph is None:
        glyph = GSGlyph(name)
        font.glyphs.append(glyph)
    aligned = align == buildplan.ALIGN_ALL
    glyph.beginUndo()
    try:
        if aligned:
            # Glyphs can't apply name keys to an auto-aligned layer
            for attr in KEY_ATTRS:
                setattr(glyph, attr, None)
        for m in font.masters:
            layer = glyph.layers[m.id]
            if layer is None:
                continue
            _clear(layer)
            for i, cname in enumerate(components):
                comp = GSComponent(cname)
                comp.automaticAlignment = aligned or i > 0
                layer.shapes.append(comp)
            if aligned:
                for attr in KEY_ATTRS:
                    setattr(layer, attr, None)
            else:
                base = font.glyphs[components[0]].layers[m.id]
                if base is not None:
                    layer.width = base.width
            # alignment is lazy: apply it now, so width and sidebearings are
            # right before anything reads them
            layer.alignComponents()
            if not aligned and _has_keys(glyph, layer) and \
                    _key_targets_drawn(font, glyph, layer, m.id):
                layer.syncMetrics()
                layer.alignComponents()
    finally:
        glyph.endUndo()


def _apply_plan(font, cmap, p):
    variants = cmap.get("sign_variants", {})
    for variant, source in sorted(p["seed"].items()):
        slot = variants.get(variant, {}).get("slot") or variant.split(".", 1)[1]
        seed_variant(font, variant, source, slot)
    for name, comps, _action, align in p["build"]:
        build_glyph(font, name, comps, align)


def apply_plan(font, cmap, p):
    font.disableUpdateInterface()
    try:
        _apply_plan(font, cmap, p)
    finally:
        font.enableUpdateInterface()


def describe(row):
    name, comps, action, _align = row
    return "%-22s %-18s = %s" % (name, ACTION_LABEL[action], " + ".join(comps))


def summary(p):
    counts = {}
    for _n, _c, action, _a in p["build"]:
        counts[action] = counts.get(action, 0) + 1
    parts = ["%d to %s" % (counts[a], ACTION_LABEL[a]) for a in buildplan.ACTIONS if a in counts]
    if p["seed"]:
        parts.append("%d sign variant(s) to seed" % len(p["seed"]))
    return ", ".join(parts) or "nothing to build"


def print_plan(p, title):
    Glyphs.showMacroWindow()
    print("\n" + "=" * 60)
    print(title)
    print("  %s; %d already right, %d skipped" % (summary(p), len(p["ok"]), len(p["skip"])))
    if p["seed"]:
        print("\nSEED (copied from the plain sign, coloured orange — redesign):")
        for variant, source in sorted(p["seed"].items()):
            print("  %-22s <- %s" % (variant, source))
    if p["build"]:
        print("\nBUILD:")
        for row in p["build"]:
            print("  " + describe(row))
    if p["skip"]:
        print("\nSKIPPED:")
        for name, reason in p["skip"]:
            print("  %-22s %s" % (name, reason))


# --------------------------------------------------------------------------- #
# Adding catalogue glyphs
# --------------------------------------------------------------------------- #

def _assign_unicode(font, glyph, item):
    """A single-character grapheme (a letter, a sign) gets its code point when
    Glyphs did not assign one from the name and no other glyph has it."""
    text = item.get("text") or ""
    if glyph.unicode or item.get("seed") or len(text) != 1:
        return
    if font.glyphs[text] is None:
        glyph.unicode = "%04X" % ord(text)


def _create_drawn(font, cmap, item, from_parts):
    name = item["name"]
    parts = item.get("parts") or item.get("components") or []
    if from_parts and parts and all(font.glyphs[p] is not None for p in parts):
        align = buildplan.alignment(parts, set(cmap.get("spacing_signs", ())),
                                    set(cmap.get("prebase_signs", ())))
        build_glyph(font, name, parts, align)
        glyph = font.glyphs[name]
        for m in font.masters:
            layer = glyph.layers[m.id]
            if layer is not None and layer.components:
                layer.decomposeComponents()
        glyph.note = PARTS_NOTE % " + ".join(parts)
    else:
        font.glyphs.append(GSGlyph(name))


def add_items(font, cmap, items, valid, from_parts=True):
    """Make each glyph of `valid` ({name: mode}, in dependency order — see
    catalogue.resolve) in `font`. Returns {'draw': [...], 'composite': [...],
    'features': [...], 'seeded': [...], 'skipped': [(name, reason)]}."""
    made = {catalogue.DRAW: [], catalogue.COMPOSITE: [], catalogue.FEATURES: [],
            "seeded": [], "skipped": []}
    feats = recorded_features(font)
    spacing = cmap.get("spacing_signs", [])
    prebase = cmap.get("prebase_signs", [])
    variants = cmap.get("sign_variants", {})
    font.disableUpdateInterface()
    try:
        for name, mode in valid.items():
            item = items[name]
            if mode == catalogue.FEATURES:
                feats.add(name)
                made[mode].append(name)
                continue
            if font.glyphs[name] is not None:
                made["skipped"].append((name, "already in the font"))
                continue
            if mode == catalogue.COMPOSITE:
                spec = {"composites": {name: {"components": item["components"]}},
                        "spacing_signs": spacing, "prebase_signs": prebase,
                        "sign_variants": variants}
                exists, state = font_state(font)
                p = buildplan.plan(spec, exists, state, targets=[name])
                if not p["build"]:
                    reason = "; ".join(r for _n, r in p["skip"]) or "nothing to build"
                    made["skipped"].append((name, reason))
                    continue
                _apply_plan(font, spec, p)
                made["seeded"].extend(sorted(p["seed"]))
            elif item.get("seed"):
                slot = variants.get(name, {}).get("slot") or name.split(".", 1)[1]
                seed_variant(font, name, item["seed"], slot)
            else:
                _create_drawn(font, cmap, item, from_parts)
            feats.discard(name)
            _assign_unicode(font, font.glyphs[name], item)
            made[mode].append(name)
    finally:
        font.enableUpdateInterface()
    set_recorded_features(font, feats)
    return made

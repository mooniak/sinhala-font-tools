# GENERATED copy of tools/composite-map/composite_map/catalogue.py — edit that
# file, then run:  python -m composite_map build-plugin
"""What the glyph catalogue lets you add to a font — pure, no font access.

Shared by the Glyphs plugin (bundled copy) and anything else that wants the
same decisions. The catalogue (tools/_generated/sinhala-glyph-catalogue.json,
built by glyph-catalogue/build.js) lists every Sinhala glyph a font may
contain; each item may be made in one of its `modes`:

  draw       an outline glyph (a sign variant is seeded from its plain sign)
  composite  its `components`, by canonical names
  features   no precomposed glyph: GSUB/GPOS shape the grapheme from its parts;
             the decision is recorded in the font so the glyph counts as done

A glyph may only be added once everything it depends on is in the font or is
being added with it:

  requires    design parents from the stage model — satisfied by a glyph or
              by a features decision
  parts       what it is made of (plain names; defaults to `components`) —
              likewise, for draw and features
  components  for composite, each must be a glyph; a missing sign variant
              (usign-sinh.medium) is fine when its plain sign is there,
              because the build seeds it

The caller describes the font through two sets: `glyphs` (names in the font)
and `features` (names recorded as made by features).
"""
import re

DRAW, COMPOSITE, FEATURES = "draw", "composite", "features"
MODES = (DRAW, COMPOSITE, FEATURES)

# item states, as the dialog shows them
IN_FONT, BY_FEATURES, CHECKED, AVAILABLE, LOCKED = (
    "in-font", "features", "checked", "available", "locked")


def plain(name):
    """usign-sinh.medium -> usign-sinh; other names pass unchanged."""
    return re.sub(r"(-sinh)\.[^.]+$", r"\1", name)


def index(catalogue):
    return {it["name"]: it for it in catalogue["items"]}


def default_mode(item, prefer=None):
    """The item's recommended mode, or `prefer` when the item allows it."""
    if prefer in item["modes"]:
        return prefer
    return item["default"]


def missing(item, mode, has_glyph, has_feature):
    """Dependencies of `item` made in `mode` that are not satisfied, in a
    stable order. has_glyph / has_feature: name -> bool."""
    out = []

    def need(name, glyph_only):
        if name == item["name"] or name in out:
            return
        if has_glyph(name):
            return
        if not glyph_only and has_feature(name):
            return
        if glyph_only and plain(name) != name and has_glyph(plain(name)):
            return      # a sign variant the build will seed
        out.append(name)

    for name in item.get("requires", ()):
        need(name, False)
    if item.get("seed"):
        need(item["seed"], True)
    if mode == COMPOSITE:
        for name in item.get("components") or ():
            need(name, True)
    else:
        for name in item.get("parts") or item.get("components") or ():
            need(name, False)
    return out


def resolve(items, glyphs, features, checked):
    """The checked items that can actually be added, in an order where every
    item comes after what it depends on.

    checked: {name: mode}. Returns an ordered {name: mode}; checked items left
    out are those whose dependencies are neither in the font nor (themselves
    resolvable) checked.
    """
    valid = {}

    def has_glyph(name):
        return name in glyphs or valid.get(name) in (DRAW, COMPOSITE)

    def has_feature(name):
        return name in features or valid.get(name) == FEATURES

    pending = [n for n in checked if n in items and n not in glyphs]
    progress = True
    while pending and progress:
        progress = False
        rest = []
        for name in pending:
            if missing(items[name], checked[name], has_glyph, has_feature):
                rest.append(name)
            else:
                valid[name] = checked[name]
                progress = True
        pending = rest
    return valid


def states(items, glyphs, features, valid, modes):
    """-> {name: (state, missing)} for every item. `valid` is resolve()'s
    result, `modes` the mode each item would be made in."""
    def has_glyph(name):
        return name in glyphs or valid.get(name) in (DRAW, COMPOSITE)

    def has_feature(name):
        return name in features or valid.get(name) == FEATURES

    out = {}
    for name, item in items.items():
        if name in glyphs:
            out[name] = (IN_FONT, [])
        elif name in features:
            out[name] = (BY_FEATURES, [])
        elif name in valid:
            out[name] = (CHECKED, [])
        else:
            miss = missing(item, modes.get(name) or item["default"], has_glyph, has_feature)
            out[name] = (LOCKED, miss) if miss else (AVAILABLE, [])
    return out


def check_all(items, names, glyphs, features, checked, modes):
    """Check every item in `names` that is or becomes available, repeating
    until nothing more unlocks (so a whole stage can be picked at once).
    Returns the new checked dict."""
    checked = dict(checked)
    while True:
        valid = resolve(items, glyphs, features, checked)
        st = states(items, glyphs, features, valid, modes)
        new = [n for n in names if st[n][0] == AVAILABLE]
        if not new:
            return checked
        for n in new:
            checked[n] = modes.get(n) or items[n]["default"]

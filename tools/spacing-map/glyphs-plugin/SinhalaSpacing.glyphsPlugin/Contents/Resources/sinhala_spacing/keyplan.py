# GENERATED copy of tools/spacing-map/spacing_map/keyplan.py — edit that
# file, then run:  python -m spacing_map build-plugin
"""Metrics-key plan: which glyph should inherit which rep's sidebearing.

Pure — no glyphsLib, no GlyphsApp, no YAML — so the same code runs in the CLI
and inside the Glyphs plugin (glyphs-plugin/, which vendors a copy).

For every scheme entry present in a font, on each side, the plan says one of:

  set       no key on that side yet — write the rep's glyph name
  ok        already keyed to the rep
  conflict  keyed to something else (another glyph, a formula) — flag it,
            never overwrite: a hand-set key is a designer decision
  waiting   the entry is present but its class rep is not, so there is
            nothing to point at yet

Skipped entirely: the rep itself on its own side (it is the source), sides
listed under the scheme's `exceptions:` (bespoke-spaced), and entries the
font lacks.

Composites (sinhala-composites.yaml: sU-sinh = sa-sinh + usign-sinh …) that
the scheme doesn't key on a side inherit that side from their BASE glyph —
measured on the composite's own outline, so a sign hanging past the base's
edge gets the base's sidebearing outside it. Their class is BASE_CLASS.

Keys are written as the bare rep glyph name (`ta-sinh`), which is how Glyphs
stores a plain inheritance key; a leading `=` is accepted when comparing.
"""

SIDES = ("left", "right")
BASE_CLASS = "(base)"     # class name reported for a composite's base fallback


def targets(scheme):
    """Every (side, class, entry, kind) the scheme asks a font to carry.

    Entries are class members (single chars) and fused forms; a form is a
    member of whatever class it maps to on that side.
    """
    out = []
    for side, classes in scheme["classes"].items():
        for cname, cls in classes.items():
            for ch in cls["members"]:
                out.append((side, cname, ch, "member"))
    for fam in scheme.get("forms", {}).values():
        for form, sides in fam["glyphs"].items():
            for side, cname in sides.items():
                if cname:
                    out.append((side, cname, form, "form"))
    return out


def normalize(key):
    """A metrics key as comparable text: None for empty, `=` prefix dropped."""
    if not key:
        return None
    key = str(key).strip()
    if key.startswith("="):
        key = key[1:].strip()
    return key or None


def expected_keys(scheme, resolve, composites=None, exists=None):
    """-> (expected, waiting)

    expected: glyph_name -> {side: (rep_glyph_name, class_name, entry)}
    waiting:  [(glyph_name, side, class_name, rep_entry)] — present, rep absent

    `resolve(entry)` returns the font's glyph name for a scheme entry, or None
    when the font lacks it. `composites` ({glyph name: base glyph name}) adds
    the base fallback for sides the scheme leaves open; `exists(name)` says
    whether the font has a glyph.
    """
    exceptions = scheme.get("exceptions") or {}
    expected, waiting = {}, []
    for side, cname, entry, _kind in targets(scheme):
        rep = scheme["classes"][side][cname]["rep"]
        if entry == rep or side in (exceptions.get(entry) or {}):
            continue
        name = resolve(entry)
        if name is None:
            continue
        rep_name = resolve(rep)
        if rep_name is None:
            waiting.append((name, side, cname, rep))
            continue
        # first claim wins; the model validator forbids double membership
        expected.setdefault(name, {}).setdefault(side, (rep_name, cname, entry))
    claimed = {(w[0], w[1]) for w in waiting}
    for name, base in sorted((composites or {}).items()):
        if not exists(name):
            continue
        for side in SIDES:
            if side in expected.get(name, {}) or (name, side) in claimed:
                continue
            if exists(base):
                expected.setdefault(name, {})[side] = (base, BASE_CLASS, name)
            else:
                waiting.append((name, side, BASE_CLASS, base))
    return expected, waiting


def classify(rep_name, keys):
    """`keys`: the non-empty keys set on one side of one glyph (glyph level
    plus any per-layer overrides). -> 'set' | 'ok' | 'conflict'."""
    found = [k for k in (normalize(k) for k in keys) if k]
    if not found:
        return "set"
    return "ok" if all(k == rep_name for k in found) else "conflict"


def plan(expected, keys_of, only=None):
    """-> {'set': [...], 'ok': [...], 'conflict': [...]} of
    (glyph_name, side, rep_name, class_name, entry, found_keys).

    `keys_of(glyph_name, side)` returns the keys currently on that side.
    `only` restricts the plan to a set of glyph names (e.g. newly added ones).
    """
    out = {"set": [], "ok": [], "conflict": []}
    for name in sorted(expected):
        if only is not None and name not in only:
            continue
        for side in SIDES:
            if side not in expected[name]:
                continue
            rep_name, cname, entry = expected[name][side]
            found = [k for k in keys_of(name, side) if normalize(k)]
            status = classify(rep_name, found)
            out[status].append((name, side, rep_name, cname, entry, found))
    return out

# GENERATED copy of tools/composite-map/composite_map/buildplan.py — edit that
# file, then run:  python -m composite_map build-plugin
"""What building the composite map into a font would do — pure, no font access.

Shared by the Glyphs plugin (bundled copy) and anything else that wants the
same decisions. The caller describes the font through two callables:

  exists(name)  -> bool
  state(name)   -> ("absent",) | ("empty",)
                   | ("composite", [component names], base_aligned)
                   | ("drawn",)          # outlines, with or without components

One rule for every composite: base + sign, by the map's canonical names. When
the font lacks a sign variant the map references (usign-sinh.medium,
isign-sinh.alt3 …) it is SEEDED from its plain sign (the name up to the first
dot), so the composite is structurally right from the start and the variant is
left for redesign. Nothing ever falls back to the plain sign.

How a composite is aligned follows from its signs (see `alignment()`):
an attached sign (ු ්‍ර ි repha ්) rides on the base, which is NOT
auto-aligned, so the glyph's sidebearings come from metrics keys like any other
glyph — Glyphs would otherwise copy the base's width and let the sign hang
past the right edge. A spacing sign (ා ැ ෑ ෟ …) only advances when the whole
glyph is auto-aligned, so those composites keep automatic alignment (and
carry no keys: Glyphs can't apply name keys to an auto-aligned layer). The
same holds for a pre-base sign (ෙ ෛ) leading the components: කො is
esign-sinh + ka-sinh + aasign-sinh, every part advancing.

Exceptions are only what the map says: keep_drawn and review glyphs are never
built. A drawn glyph is only replaced when the caller passes overwrite=True
(an explicit selection), so a whole-font run never destroys drawing.
"""

ACTIONS = ("create", "rebuild", "update")
ALIGN_BASE = "base"     # base placed at the origin, signs anchored, keys space it
ALIGN_ALL = "all"       # every component auto-aligned (a spacing sign advances)


def _stem(name):
    """usign-sinh.medium -> usign."""
    plain = name.split(".", 1)[0]
    return plain[: -len("-sinh")] if plain.endswith("-sinh") else plain


def alignment(components, spacing_signs, prebase_signs=()):
    """ALIGN_ALL when any sign after the base is a spacing sign, or a pre-base
    sign leads the components; else ALIGN_BASE. Both sets hold plain sign
    names without script suffix (aasign, esign …)."""
    if len(components) > 1 and _stem(components[0]) in prebase_signs:
        return ALIGN_ALL
    for c in components[1:]:
        if _stem(c) in spacing_signs:
            return ALIGN_ALL
    return ALIGN_BASE


def plan(map_data, exists, state, targets=None, overwrite=False):
    """-> {
         'build':  [(name, components, action, align)],  action in ACTIONS
         'seed':   {variant: plain sign},          variants to create first
         'ok':     [name],                         already the right composite
         'skip':   [(name, reason)],
       }

    targets: names to consider (None = every composite in the map). Glyphs
    not in the map are reported in 'skip' only when explicitly targeted.
    """
    composites = map_data.get("composites", {})
    keep_drawn = map_data.get("keep_drawn", {})
    review = map_data.get("review", {})
    spacing_signs = set(map_data.get("spacing_signs", ()))
    prebase_signs = set(map_data.get("prebase_signs", ()))
    explicit = targets is not None
    names = list(targets) if explicit else sorted(composites)

    out = {"build": [], "seed": {}, "ok": [], "skip": []}
    for name in names:
        if name in keep_drawn:
            if explicit:
                out["skip"].append((name, "keep drawn: %s" % keep_drawn[name]))
            continue
        if name in review:
            if explicit:
                out["skip"].append((name, "in review"))
            continue
        spec = composites.get(name)
        if spec is None:
            if explicit:
                out["skip"].append((name, "not in the composite map"))
            continue
        comps = list(spec["components"])
        align = alignment(comps, spacing_signs, prebase_signs)

        st = state(name)
        kind = st[0]
        if (kind == "composite" and list(st[1]) == comps
                and st[2] == (align == ALIGN_ALL)):
            out["ok"].append(name)
            continue
        if kind == "drawn" and not overwrite:
            out["skip"].append((name, "drawn (select it to replace)"))
            continue

        missing = _missing_components(comps, exists, out["seed"])
        if missing:
            out["skip"].append((name, "missing %s" % ", ".join(missing)))
            continue

        action = {"absent": "create", "composite": "update"}.get(kind, "rebuild")
        out["build"].append((name, comps, action, align))
    return out


def plain_sign(name):
    """usign-sinh.medium -> usign-sinh; isign-sinh.alt3 -> isign-sinh."""
    return name.split(".", 1)[0] if "." in name else None


def _missing_components(comps, exists, seed):
    """Components that can't be had: absent and not seedable. Seedable ones
    are recorded in `seed` (shared across the plan, so each is seeded once)."""
    missing = []
    for c in comps:
        if exists(c) or c in seed:
            continue
        src = plain_sign(c)
        if src and exists(src):
            seed[c] = src
        else:
            missing.append(c)
    return missing

"""Build the Sinhala composite-glyph map from reference sources.

Two reference roles (per project convention):
  - inventory reference (default: Abhaya Libre) — the widest glyph set, whose
    conjuncts / al-forms / sign-forms are largely drawn atomically (GSUB-based).
    Defines WHICH forms exist.
  - anchor reference  (default: Noto Sans Sinhala) — the GPOS-optimised source
    whose base/mark anchors document HOW shape-invariant marks attach.

Crucially, Sinhala mark attachment is not uniform: only rasign, repha and the
DEFAULT-class u/uu/virama are genuine base+mark composites. ispilla (ිී) forms
are atomically designed, and u-special / du-form / llu-form / ra and the fused
virama alternates (rahena/trap/ja) are special forms. Those are recorded as
keep-drawn with the responsible form-family as the reason (see families.py /
grammar.py), so the map never claims e.g. `kU-sinh = ka + usign`.

The output is a plain dict, serialised to YAML by cli/jsexport. It never mutates
any font.
"""
import re
from collections import Counter
from pathlib import Path

from . import glyphsio
from .families import Families
from .grammar import Grammar
from .ispilla import IspillaModel
from .signvariants import SignVariants


_CANONICAL_RE = re.compile(r"^[A-Za-z_]+-sinh$")


def _harvest_existing(font, master_id, sign_stems):
    """The inventory's own composites, kept only where they are canonical:
    every name a plain `-sinh` glyph (no `bullet` display glyphs, no `.hist`
    style alternates), and reordered base-first, since Glyphs' automatic
    alignment places components in order."""
    out = {}
    for glyph in font.glyphs:
        if not _CANONICAL_RE.match(glyph.name):
            continue
        layer = glyphsio.master_layer(glyph, master_id)
        if glyphsio.layer_class(layer) != "composite":
            continue
        comps = glyphsio.component_names(layer)
        if not all(_CANONICAL_RE.match(c) for c in comps):
            continue
        is_sign = lambda c: c[:-len("-sinh")].split("_")[0] in sign_stems
        comps = [c for c in comps if not is_sign(c)] + [c for c in comps if is_sign(c)]
        out[glyph.name] = {"components": comps, "tier": 0, "source": "inventory-existing"}
    return out


def _extract_anchor_system(font):
    mid = font.masters[0].id
    mark_anchors = {}
    base_anchor_freq = Counter()
    for glyph in font.glyphs:
        if not glyphsio.is_sinhala(glyph.name):
            continue
        layer = glyphsio.master_layer(glyph, mid)
        anchors = glyphsio.anchor_names(layer)
        mark = [a for a in anchors if a.startswith("_")]
        if mark:
            mark_anchors[glyph.name] = mark[0][1:]
        else:
            for a in anchors:
                base_anchor_freq[a] += 1
    return mark_anchors, dict(base_anchor_freq)


def build_map(inventory_path, anchor_path, classification):
    inv_font = glyphsio.load_font(inventory_path)
    inv_mid = inv_font.masters[0].id
    inv_names = [g.name for g in inv_font.glyphs]
    sinh_names = [n for n in inv_names if glyphsio.is_sinhala(n)]

    anchor_font = glyphsio.load_font(anchor_path)
    families = Families()
    ispilla = IspillaModel(anchor_font)
    variants = SignVariants(anchor_font)
    grammar = Grammar(classification, inv_names, families, ispilla, variants)

    consonant_bases = {f"{c}-sinh" for c in classification["consonants"]}
    plain_letters = consonant_bases | {f"{v}-sinh" for v in classification["independent_vowels"]}
    sign_and_mark_glyphs = (
        {f"{s}-sinh" for s in classification["dependent_signs"]}
        | {f"{m}-sinh" for m in classification["other_marks"]}
    )

    composites = {}
    sign_stems = (set(classification["dependent_signs"]) | set(classification["other_marks"])
                  | {"repha", "rasign", "yasign"})
    composites.update(_harvest_existing(inv_font, inv_mid, sign_stems))  # tier 0
    comp_gen, drawn_gen = grammar.generate()                            # tier 1/2 + drawn
    for name, spec in comp_gen.items():
        composites.setdefault(name, spec)

    keep_drawn = {}   # name -> reason
    review = {}       # name -> {class, guess}

    for name, info in drawn_gen.items():
        if name not in composites:
            keep_drawn[name] = info["reason"]

    for name in sinh_names:
        if name in composites or name in keep_drawn:
            continue
        if name in plain_letters or name in sign_and_mark_glyphs:
            continue
        klass = glyphsio.glyph_class(inv_font.glyphs[name], inv_mid)
        res = grammar.classify(name)
        if res is None:
            if klass in ("atomic", "mixed", "composite"):
                keep_drawn[name] = "irreducible"
            continue
        kind = res[0]
        if kind == "composite":
            comps = res[1]
            is_ispilla = any(c.split(".")[0] in ("isign-sinh", "iisign-sinh") for c in comps)
            tier, source = (3, "noto-ispilla") if is_ispilla else (2, "grammar-classify")
            composites[name] = {"components": comps, "tier": tier, "source": source}
        elif kind == "drawn":
            keep_drawn[name] = res[1]
        elif kind == "review":
            review[name] = {
                "class": klass,
                "guess": res[1],
                "note": "sign form on a conjunct base the family model does not cover — confirm before applying",
            }

    # anchor system from the anchor reference
    mark_anchors, base_anchor_freq = _extract_anchor_system(anchor_font)
    used_components = set()
    for spec in composites.values():
        used_components.update(spec["components"])
    sign_to_anchor = {}
    for n in sorted(used_components):
        src = n if n in mark_anchors else variants.noto.get(n)
        if src in mark_anchors:
            sign_to_anchor[n] = mark_anchors[src]

    meta = {
        "inventory_reference": Path(inventory_path).name,
        "anchor_reference": Path(anchor_path).name,
        "family_model": "model/sinhala-design-dependencies.yaml",
        "counts": {
            "composites": len(composites),
            "by_tier": dict(sorted(Counter(v["tier"] for v in composites.values()).items())),
            "review": len(review),
            "keep_drawn": len(keep_drawn),
            "keep_drawn_by_reason": _reason_counts(keep_drawn),
        },
    }

    return {
        "meta": meta,
        "atoms": {
            "base_letters": sorted(consonant_bases & set(inv_names)),
            "signs": sorted(sign_and_mark_glyphs & set(inv_names)),
            "ispilla_alternates": _ispilla_alternates(composites),
            "sign_variants": variants.table(),
        },
        "anchors": {
            "base_anchor_frequency": base_anchor_freq,
            "sign_attachment": sign_to_anchor,
        },
        "composites": dict(sorted(composites.items())),
        "review": dict(sorted(review.items())),
        "keep_drawn": dict(sorted(keep_drawn.items())),
    }


def _reason_counts(keep_drawn):
    counts = Counter(r.split(":", 1)[0] for r in keep_drawn.values())
    return dict(sorted(counts.items()))


def _ispilla_alternates(composites):
    """The isign/iisign glyphs (incl. .altN alternates) the ispilla composites
    reference — documents the sign inventory a target needs to rebuild them."""
    signs = set()
    for spec in composites.values():
        if spec.get("source") == "noto-ispilla":
            signs.update(c for c in spec["components"] if "sign-sinh" in c)
    return sorted(signs)

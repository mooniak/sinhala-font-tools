"""Reads the design-stages model (sinhala-design-dependencies.yaml) and
extracts what the spacing scheme needs: the spacing_classes block, the
per-glyph `spacing` declarations, the spacing-mark inventory, and the fused
form families.

The model is the source of truth for RELATIONSHIPS (classes, reps, members).
Membership of a class is the union of its core `members` list and every
glyph whose `spacing: {left/right: ...}` field names the class — composites
like ආ declare class membership without appearing in the core lists.

Form families with `fused: true` produce single ligature glyphs (ටි ම් කු …)
that carry their own sidebearings. Their forms default to host+mark (and
host+long via the mark system's `long`), or an explicit `forms:` list
(ra-forms). Spacing defaults to the host's classes per side, overridable
family-wide (`form_spacing`) or per form (`form_overrides`).
"""
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MODEL = REPO_ROOT / "sinhala-design-stages" / "sinhala-design-dependencies.yaml"

SIDES = ("right", "left")

# Glyph-entry types whose characters carry their own sidebearings (candidates
# for class membership / the unassigned report). form-family, conjunct-system
# and process entries are design decisions, not spacing carriers.
SPACING_CARRIER_TYPES = {"base", "vowel", "sign"}


def load_model(path=DEFAULT_MODEL):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def glyph_char(key, entry):
    """The Sinhala character for a glyphs-block entry, or None for named
    entries (form families, processes, conjunct systems)."""
    if isinstance(key, str) and len(key) == 1:
        return key
    cp = (entry or {}).get("codepoint")
    if cp:
        try:
            return chr(int(str(cp), 16))
        except (ValueError, OverflowError):
            return None
    return None


def extract(model):
    glyphs = model.get("glyphs") or {}
    per_glyph = {}            # char -> {side: class-name}
    glyph_notes = {}          # char -> spacing_note (provisional flags)
    char_types = {}           # char -> entry type
    named_with_spacing = []   # non-char entries that declare spacing (skipped)
    mark_systems = model.get("mark_systems") or {}
    longs = {s.get("mark"): s.get("long")
             for s in mark_systems.values()
             if isinstance(s, dict) and s.get("mark") and s.get("long")}

    form_families = {}        # family key -> forms + spacing rules (model order)
    for key, entry in glyphs.items():
        if not isinstance(entry, dict):
            continue
        ch = glyph_char(key, entry)
        if ch is not None:
            char_types[ch] = entry.get("type")
            if entry.get("spacing_note"):
                glyph_notes[ch] = entry["spacing_note"]
        if entry.get("type") == "form-family" and entry.get("fused"):
            mark = entry.get("mark")
            forms = list(entry.get("forms") or [])
            if not forms and mark:
                hosts = list(entry.get("hosts") or []) + list(entry.get("conjunct_hosts") or [])
                for host in hosts:
                    forms.append(host + mark)
                    if longs.get(mark):
                        forms.append(host + longs[mark])
            form_families[key] = {
                "forms": forms,
                "spacing": entry.get("form_spacing") or {},
                "overrides": entry.get("form_overrides") or {},
                "note": entry.get("spacing_note"),
            }
        sp = entry.get("spacing")
        if not sp:
            continue
        if ch is None:
            named_with_spacing.append(key)
            continue
        per_glyph[ch] = {side: sp[side] for side in SIDES if side in sp}

    marks = mark_systems.get("spacing_marks") or {}
    spacing_mark_chars = [c for group, chars in marks.items()
                          if group != "nonspacing" for c in chars]
    nonspacing_chars = list(marks.get("nonspacing") or [])

    return {
        "classes": model.get("spacing_classes") or {},
        "per_glyph": per_glyph,
        "glyph_notes": glyph_notes,
        "char_types": char_types,
        "named_with_spacing": named_with_spacing,
        "spacing_mark_chars": spacing_mark_chars,
        "nonspacing_chars": nonspacing_chars,
        "form_families": form_families,
        "meta": model.get("meta") or {},
    }


def validate(x):
    """Returns (errors, warnings). Errors block the build; warnings don't."""
    errors, warnings = [], []
    side_primary = {}  # side -> {char: class} (core membership)
    for side in SIDES:
        side_classes = (x["classes"].get(side) or {})
        primary = {}  # char -> class that lists it as a core member
        side_primary[side] = primary
        for cname, cls in side_classes.items():
            rep = cls.get("rep")
            members = cls.get("members") or []
            if not rep:
                errors.append(f"{side}/{cname}: no rep")
            if not members:
                errors.append(f"{side}/{cname}: no members")
            if rep and members and rep not in members:
                errors.append(f"{side}/{cname}: rep {rep} is not among its members")
            for m in members:
                if m in primary:
                    errors.append(
                        f"{side}: {m} is a core member of both {primary[m]} and "
                        f"{cname} — the primary class must be unique per side")
                primary[m] = cname

        for ch, sp in x["per_glyph"].items():
            cname = sp.get(side)
            if cname is None:
                continue
            if cname not in side_classes:
                errors.append(f"glyph {ch}: spacing.{side} references unknown class {cname}")
            elif ch in primary and primary[ch] != cname:
                errors.append(
                    f"glyph {ch}: declares spacing.{side}={cname} but is a core "
                    f"member of {primary[ch]}")

        for m, cname in primary.items():
            sp = x["per_glyph"].get(m) or {}
            if m not in x["char_types"]:
                warnings.append(f"{side}/{cname}: member {m} has no glyphs entry in the model")
            elif sp.get(side) != cname:
                warnings.append(
                    f"{side}/{cname}: member {m} has a glyphs entry that does not "
                    f"declare spacing.{side}={cname}")

    seen_forms = {}  # form -> family
    for fam, ff in x["form_families"].items():
        for form, sides in ff["overrides"].items():
            if form not in ff["forms"]:
                warnings.append(f"{fam}: form_overrides lists {form}, not one of its forms")
            for side, cname in (sides or {}).items():
                if cname not in (x["classes"].get(side) or {}):
                    errors.append(f"{fam}: override {form}.{side} names unknown class {cname}")
        for side, cname in ff["spacing"].items():
            if cname not in (x["classes"].get(side) or {}):
                errors.append(f"{fam}: form_spacing.{side} names unknown class {cname}")
        for form in ff["forms"]:
            if form in seen_forms:
                errors.append(f"form {form} generated by both {seen_forms[form]} and {fam}")
            seen_forms[form] = fam
            host = form[0]
            for side in SIDES:
                covered = ((ff["overrides"].get(form) or {}).get(side)
                           or ff["spacing"].get(side)
                           or (x["per_glyph"].get(host) or {}).get(side)
                           or side_primary[side].get(host))
                if not covered:
                    errors.append(
                        f"{fam}: form {form} has no {side} class — host {host} is "
                        f"unclassed and no family/form override covers it")
    return errors, warnings

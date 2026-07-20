"""Builds sinhala-spacing.yaml (the spacing scheme) from the design-stages
model, preserving hand-authored data on refresh.

Division of truth:
  - relationships (classes, reps, members)  -> always from the model
  - values, notes, exceptions, extra keys   -> preserved from the existing
    scheme file across rebuilds

Seeding: the model defines spacing_unit as ට's sidebearing rhythm
("Sidebearings define the spacing unit for L-tta and R-bowl"), so classes
whose rep is ට seed with value 1.0; every other value starts null (unset)
until authored in the workbench or by hand.
"""
from .model import SIDES, SPACING_CARRIER_TYPES

MODEL_RELPATH = "sinhala-design-stages/sinhala-design-dependencies.yaml"
UNIT_DEFINING_REP = "ට"

# class-entry keys owned by the builder; anything else in an existing entry
# is user data and is carried through untouched
OWNED_KEYS = ("rep", "members", "value", "note")


def class_members(side, cname, cls, per_glyph):
    """Core members (model order) + every glyph declaring this class."""
    core = list(cls.get("members") or [])
    extra = [ch for ch, sp in per_glyph.items()
             if sp.get(side) == cname and ch not in core]
    return core + extra


def unassigned(x):
    """Spacing-carrying characters with no class on a side: letters/signs by
    entry type, plus every spacing mark (nonspacing combining marks are
    excluded — they carry no sidebearings)."""
    candidates = [ch for ch, t in x["char_types"].items()
                  if t in SPACING_CARRIER_TYPES and ch not in x["nonspacing_chars"]]
    candidates += [ch for ch in x["spacing_mark_chars"] if ch not in candidates]
    covered = {side: set() for side in SIDES}
    for side in SIDES:
        for cname, cls in (x["classes"].get(side) or {}).items():
            covered[side].update(class_members(side, cname, cls, x["per_glyph"]))
    return {side: [ch for ch in candidates if ch not in covered[side]]
            for side in SIDES}


def host_class(x, host, side):
    """The class a fused form inherits from its host on one side: the host's
    per-glyph declaration, else its core membership."""
    declared = (x["per_glyph"].get(host) or {}).get(side)
    if declared:
        return declared
    for cname, cls in (x["classes"].get(side) or {}).items():
        if host in (cls.get("members") or []):
            return cname
    return None


def build_forms(x, report):
    """Fused form-family glyphs (ටි ම් කු …), grouped by family. Each form
    maps to a left/right class: per-form override > family form_spacing >
    inherited from the host (the form's first character)."""
    out = {}
    for fam, ff in x["form_families"].items():
        glyphs = {}
        for form in ff["forms"]:
            entry = {}
            for side in SIDES:
                cname = ((ff["overrides"].get(form) or {}).get(side)
                         or ff["spacing"].get(side)
                         or host_class(x, form[0], side))
                if cname is None:
                    report["forms_unresolved"].append(f"{fam}/{form}/{side}")
                entry[side] = cname
            # yaml order: left, right to match reading direction of the glyph
            glyphs[form] = {"left": entry["left"], "right": entry["right"]}
        fam_out = {}
        if ff["note"]:
            fam_out["note"] = ff["note"]
        fam_out["glyphs"] = glyphs
        out[fam] = fam_out
    return out


def build(x, existing=None):
    """Returns (data, report). `existing` is the previously written scheme
    (parsed YAML) or None on first seed."""
    existing = existing or {}
    ex_classes = existing.get("classes") or {}
    report = {
        "added": [], "removed": [], "rep_changed": [],
        "members_added": {}, "members_removed": {},
        "values_preserved": 0, "values_seeded": [],
        "forms_unresolved": [],
    }

    classes_out = {}
    member_counts = {}
    for side in SIDES:
        model_side = x["classes"].get(side) or {}
        ex_side = ex_classes.get(side) or {}
        out_side = {}
        seen_chars = set()
        for cname, cls in model_side.items():
            members = class_members(side, cname, cls, x["per_glyph"])
            seen_chars.update(members)
            prev = ex_side.get(cname)
            if prev:
                value = prev.get("value")
                if value is not None:
                    report["values_preserved"] += 1
                note = prev.get("note") or cls.get("note")
                prev_members = prev.get("members") or []
                diff_key = f"{side}/{cname}"
                added = [m for m in members if m not in prev_members]
                removed = [m for m in prev_members if m not in members]
                if added:
                    report["members_added"][diff_key] = added
                if removed:
                    report["members_removed"][diff_key] = removed
                if prev.get("rep") != cls.get("rep"):
                    report["rep_changed"].append(
                        f"{diff_key}: {prev.get('rep')} -> {cls.get('rep')}")
            else:
                report["added"].append(f"{side}/{cname}")
                value = 1.0 if cls.get("rep") == UNIT_DEFINING_REP else None
                if value is not None:
                    report["values_seeded"].append(f"{side}/{cname}")
                note = cls.get("note")

            entry = {"rep": cls.get("rep"), "members": members, "value": value}
            if note:
                entry["note"] = note
            if prev:
                for k, v in prev.items():
                    if k not in OWNED_KEYS:
                        entry[k] = v
            out_side[cname] = entry

        report["removed"] += [f"{side}/{c}" for c in ex_side if c not in model_side]
        classes_out[side] = out_side
        member_counts[side] = len(seen_chars)

    forms_out = build_forms(x, report)
    n_forms = sum(len(f["glyphs"]) for f in forms_out.values())
    data = {
        "meta": {
            "version": 1,
            "generated_by": "tools/spacing-map (python -m spacing_map build-map)",
            "model": MODEL_RELPATH,
            "model_version": x["meta"].get("version"),
            "unit": "spacing_unit",
            "description": (
                "Sinhala spacing scheme. Each class: `rep` sets the sidebearing, "
                "`members` inherit it (applied as Glyphs metrics keys), `value` is "
                "the rep's sidebearing target as a multiple of the font's "
                "spacing_unit metric (null = not yet authored). `forms` are the "
                "fused form-family glyphs (ටි ම් කු …): each maps to the class "
                "whose rep it copies per side — per-form override > family "
                "form_spacing > inherited from its host. `flags` collect the "
                "model's provisional spacing_note markers awaiting the designer. "
                "`nonspacing` combining marks carry no sidebearings. Relationships "
                "are rebuilt from the model; values/notes/exceptions survive "
                "rebuilds."),
            "counts": {
                "classes": {side: len(classes_out[side]) for side in SIDES},
                "members": member_counts,
                "forms": n_forms,
            },
        },
        "classes": classes_out,
        "forms": forms_out,
        "forms_note": (
            "Fused forms inherit their host's classes unless the family "
            "overrides a side. FLAG (blanket): ී long tails and ්-wraps may set "
            "their own right extreme on some hosts — verify against each family "
            "rep in the workbench and add form_overrides in the model where the "
            "drawing disagrees."),
        "exceptions": existing.get("exceptions") or {},
        "unassigned": unassigned(x),
        "nonspacing": list(x["nonspacing_chars"]),
        "flags": dict(x["glyph_notes"]),
    }
    return data, report

"""Read-only audit of a font against the spacing scheme.

Three questions, answered per master:

  coverage — which scheme entries exist in this font at all (resolved by
             unicode for letters, by name convention for fused forms)?
  drift    — does each class member's measured sidebearing match its rep's?
             This is the design gate "every new glyph sits correctly in its
             spacing class", measured rather than eyeballed.
  keys     — does each member carry a leftMetricsKey/rightMetricsKey pointing
             at its rep, i.e. is the inheritance actually wired up in the
             source (what `apply` will write)?

It also reports the font's implied spacing unit — the sidebearings of ට, the
glyph the model says defines the unit — and each class's measured sidebearing
as a multiple of it. That turns a well-spaced existing font into candidate
`value:` numbers for the scheme.
"""
from . import fontio, keyplan, names

UNIT_GLYPH = "ට"     # the model's unit-defining glyph (mapbuild.UNIT_DEFINING_REP)
SIDE_SB = {"left": "lsb", "right": "rsb"}


def _resolve_all(scheme, resolver):
    """entry -> (glyph_name, how), plus a coverage summary."""
    entries = sorted({e for _, _, e, _ in keyplan.targets(scheme)})
    resolved = {e: resolver.resolve(e) for e in entries}
    absent = {e: how for e, (_, how) in resolved.items() if how in ("missing", "unknown")}
    return resolved, {
        "entries": len(entries),
        "resolved": len(entries) - len(absent),
        "absent": absent,
    }


def audit(font_path, scheme, tolerance=8, master_ids=None, overrides=None):
    font = fontio.load_font(font_path)
    by_name, by_unicode = fontio.glyph_index(font)
    resolver = names.Resolver(by_name.keys(), by_unicode, overrides)
    resolved, coverage = _resolve_all(scheme, resolver)

    by_class = {}
    for side, cname, entry, kind in keyplan.targets(scheme):
        by_class.setdefault((side, cname), []).append((entry, kind))

    all_masters = fontio.masters(font)
    wanted = [m for m in all_masters if master_ids is None or m[0] in master_ids
              or m[1] in master_ids]

    result = {
        "font": str(font_path),
        "masters": [name for _, name in all_masters],
        "coverage": coverage,
        "tolerance": tolerance,
        "per_master": [],
    }

    for mid, mname in wanted:
        def sb(entry):
            name, how = resolved.get(entry, (None, "unknown"))
            if how in ("missing", "unknown") or name not in by_name:
                return None, name
            return fontio.sidebearings(fontio.layer_of(by_name[name], mid)), name

        unit_sb, _ = sb(UNIT_GLYPH)
        unit = {side: (unit_sb or {}).get(SIDE_SB[side]) for side in SIDE_SB}

        classes_out, key_counts = [], {"ok": 0, "missing": 0, "other": 0}
        for side, classes in scheme["classes"].items():
            for cname, cls in classes.items():
                rep = cls["rep"]
                rep_sb, rep_name = sb(rep)
                rep_v = (rep_sb or {}).get(SIDE_SB[side])
                members = by_class.get((side, cname), [])
                rows = []
                for entry, kind in members:
                    m_sb, m_name = sb(entry)
                    if m_sb is None:
                        rows.append({"entry": entry, "kind": kind, "glyph": m_name,
                                     "sb": None, "delta": None, "status": "absent",
                                     "key": None, "key_status": "absent"})
                        continue
                    value = m_sb[SIDE_SB[side]]
                    delta = None if rep_v is None else round(value - rep_v, 1)
                    is_rep = entry == rep
                    status = ("rep" if is_rep else
                              "no-rep" if delta is None else
                              "ok" if abs(delta) <= tolerance else "drift")

                    glyph = by_name[m_name]
                    key, scope = fontio.metrics_keys(
                        glyph, fontio.layer_of(glyph, mid))[side]
                    if is_rep:
                        key_status = "rep"
                    elif key is None:
                        key_status = "missing"
                    elif rep_name and keyplan.normalize(key) == rep_name:
                        key_status = "ok"
                    else:
                        key_status = "other"
                    if key_status in key_counts:
                        key_counts[key_status] += 1

                    rows.append({"entry": entry, "kind": kind, "glyph": m_name,
                                 "sb": value, "delta": delta, "status": status,
                                 "key": key, "key_scope": scope,
                                 "key_status": key_status})

                unit_v = unit[side]
                classes_out.append({
                    "side": side, "class": cname, "rep": rep, "rep_glyph": rep_name,
                    "rep_sb": rep_v,
                    "implied_value": (None if not unit_v or rep_v is None
                                      else round(rep_v / unit_v, 3)),
                    "scheme_value": cls.get("value"),
                    "rows": rows,
                    "counts": _count(rows),
                })

        result["per_master"].append({
            "id": mid, "name": mname, "unit": unit,
            "unit_glyph": resolved.get(UNIT_GLYPH, (None,))[0],
            "classes": classes_out,
            "key_counts": key_counts,
            "counts": _count([r for c in classes_out for r in c["rows"]]),
        })
    return result


def _count(rows):
    out = {}
    for r in rows:
        out[r["status"]] = out.get(r["status"], 0) + 1
    return out


def harvest_values(master_result):
    """Measured class sidebearings as unit multiples — candidate `value:`
    numbers for the scheme, keyed side -> class."""
    out = {}
    for c in master_result["classes"]:
        if c["implied_value"] is not None:
            out.setdefault(c["side"], {})[c["class"]] = c["implied_value"]
    return out

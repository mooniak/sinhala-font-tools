"""spacing-map — build and apply the Sinhala spacing scheme.

The scheme (sinhala-spacing.yaml, repo root) maps every glyph's left/right
sidebearing to a spacing class: the class `rep` sets the sidebearing, members
inherit it, and `value` records the class target as a multiple of the font's
spacing_unit metric. Relationships come from the design-stages model;
values/notes/exceptions are authored in the scheme file and survive rebuilds.

Subcommands:
  build-map   seed/refresh sinhala-spacing.yaml from the design-stages model
  audit       measure a font against the scheme (read-only): coverage, class
              drift, metrics keys, and the font's implied spacing unit
  export-js   vendor the scheme as tools/_generated/sinhala-spacing.js for
              the spacing workbench (tools/spacing-workbench)
  build-plugin
              refresh the scheme + shared code bundled in the Glyphs plugin
              (glyphs-plugin/SinhalaSpacing.glyphsPlugin)

Planned (see README.md): apply.
"""
import argparse
import sys
from pathlib import Path

import yaml

from . import audit as audit_mod
from . import jsexport, mapbuild, model, pluginbuild

DEFAULT_MAP_YAML = model.REPO_ROOT / "sinhala-spacing.yaml"
DEFAULT_JS = model.REPO_ROOT / "tools" / "_generated" / "sinhala-spacing.js"


def _print_report(report, x, limit):
    if report["values_seeded"]:
        print(f"  seeded value 1.0 (unit-defining rep {mapbuild.UNIT_DEFINING_REP}): "
              + ", ".join(report["values_seeded"]))
    if report["values_preserved"]:
        print(f"  preserved {report['values_preserved']} authored value(s)")
    for label in ("added", "removed", "rep_changed"):
        if report[label]:
            print(f"  classes {label}: " + ", ".join(report[label]))
    for label in ("members_added", "members_removed"):
        for key, chars in report[label].items():
            print(f"  {label.replace('_', ' ')} in {key}: {' '.join(chars)}")
    if report["forms_unresolved"]:
        print(f"  forms with no class (family/side): " + ", ".join(report["forms_unresolved"]))
    if x["named_with_spacing"]:
        print(f"  skipped {len(x['named_with_spacing'])} named (non-character) entries "
              f"declaring spacing: " + ", ".join(x["named_with_spacing"][:limit])
              + (" ..." if len(x["named_with_spacing"]) > limit else ""))


def cmd_build_map(args):
    x = model.extract(model.load_model(args.model))
    errors, warnings = model.validate(x)
    for w in warnings[: args.limit]:
        print(f"warning: {w}")
    if len(warnings) > args.limit:
        print(f"... and {len(warnings) - args.limit} more warnings")
    if errors:
        for e in errors:
            print(f"error: {e}", file=sys.stderr)
        print(f"{len(errors)} error(s) — fix the model; nothing written.", file=sys.stderr)
        sys.exit(1)

    out = Path(args.output)
    existing = None
    if out.exists():
        with open(out, encoding="utf-8") as f:
            existing = yaml.safe_load(f)

    data, report = mapbuild.build(x, existing)
    verb = "refreshed" if existing else "seeded"
    counts = data["meta"]["counts"]

    if args.check:
        print(f"check OK — would have {verb} {out.name} (not written)")
    else:
        out.write_text(
            yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=100),
            encoding="utf-8")
        print(f"{verb} {out}")
    print(f"  classes: {counts['classes']}  members: {counts['members']}")
    print(f"  forms: {counts['forms']} fused glyphs in {len(data['forms'])} families; "
          f"nonspacing marks: {len(data['nonspacing'])}; flags: {len(data['flags'])}")
    print(f"  unassigned: right {len(data['unassigned']['right'])}, "
          f"left {len(data['unassigned']['left'])}")
    _print_report(report, x, args.limit)


def _fmt_sb(v):
    return "  —  " if v is None else f"{v:>5g}"


def cmd_audit(args):
    with open(args.map, encoding="utf-8") as f:
        scheme = yaml.safe_load(f)
    overrides = {}
    if args.names:
        with open(args.names, encoding="utf-8") as f:
            overrides = yaml.safe_load(f) or {}
    result = audit_mod.audit(args.font, scheme, tolerance=args.tolerance,
                             master_ids=args.master, overrides=overrides)

    cov = result["coverage"]
    print(f"font: {Path(result['font']).name}   masters: {', '.join(result['masters'])}")
    print(f"coverage: {cov['resolved']}/{cov['entries']} scheme entries present")
    if cov["absent"]:
        shown = list(cov["absent"])[: args.limit]
        print(f"  absent ({len(cov['absent'])}): " + " ".join(shown)
              + (" ..." if len(cov["absent"]) > args.limit else ""))

    for m in result["per_master"]:
        u = m["unit"]
        print(f"\n── master {m['name']} " + "─" * 40)
        print(f"implied spacing unit (from {audit_mod.UNIT_GLYPH} = {m['unit_glyph']}): "
              f"left {u['left']}, right {u['right']}")
        c = m["counts"]
        print(f"sidebearings vs class rep (±{result['tolerance']}): "
              f"{c.get('ok', 0)} ok, {c.get('drift', 0)} drift, "
              f"{c.get('absent', 0)} absent, {c.get('rep', 0)} reps")
        k = m["key_counts"]
        print(f"metrics keys: {k['ok']} point at the rep, {k['other']} elsewhere, "
              f"{k['missing']} missing")

        for cl in sorted(m["classes"], key=lambda c: (c["side"], c["class"])):
            n_drift = cl["counts"].get("drift", 0)
            if not args.verbose and not n_drift:
                continue
            iv, sv = cl["implied_value"], cl["scheme_value"]
            print(f"\n  {cl['side']}/{cl['class']}  rep {cl['rep']} "
                  f"({cl['rep_glyph']}) sb={_fmt_sb(cl['rep_sb'])}"
                  f"  measured {iv if iv is not None else '—'}× unit"
                  f"  scheme value {sv if sv is not None else '—'}"
                  + (f"   {n_drift} drift" if n_drift else ""))
            for r in cl["rows"]:
                if not args.verbose and r["status"] != "drift":
                    continue
                delta = "" if r["delta"] is None else f"{r['delta']:+g}"
                print(f"    {r['entry']:<8s} {str(r['glyph'] or ''):<14s} "
                      f"{_fmt_sb(r['sb'])} {delta:>6s}  {r['status']:<7s} "
                      f"key:{r['key_status']}")

    if args.emit_values:
        first = result["per_master"][0]
        out = {
            "meta": {
                "font": Path(result["font"]).name,
                "master": first["name"],
                "spacing_unit": first["unit"],
                "note": ("Measured from the font, not authored: each number is the "
                         "class rep's sidebearing divided by the implied unit. "
                         "Review before copying into sinhala-spacing.yaml."),
            },
            "values": audit_mod.harvest_values(first),
        }
        Path(args.emit_values).write_text(
            yaml.safe_dump(out, allow_unicode=True, sort_keys=False, width=100),
            encoding="utf-8")
        print(f"\nwrote measured values to {args.emit_values} (master {first['name']})")


def cmd_export_js(args):
    with open(args.map, encoding="utf-8") as f:
        scheme = yaml.safe_load(f)
    out = Path(args.output)
    js = jsexport.to_js(scheme)
    if args.check:
        current = out.read_text(encoding="utf-8") if out.exists() else None
        if current == js:
            print(f"{out.name} is up to date")
            return
        print(f"{out.name} is stale — run export-js", file=sys.stderr)
        sys.exit(1)
    out.write_text(js, encoding="utf-8")
    print(f"wrote {out}")


def cmd_build_plugin(args):
    with open(args.map, encoding="utf-8") as f:
        scheme = yaml.safe_load(f)
    if args.check:
        bad = pluginbuild.stale(scheme)
        if not bad:
            print(f"{pluginbuild.PLUGIN.name} is up to date")
            return
        for p in bad:
            print(f"stale: {p.relative_to(pluginbuild.PLUGIN)}", file=sys.stderr)
        print("run build-plugin, then restart Glyphs", file=sys.stderr)
        sys.exit(1)
    written = pluginbuild.write(scheme)
    for p in written:
        print(f"wrote {p.relative_to(pluginbuild.PLUGIN)}")
    print(f"{pluginbuild.PLUGIN.name}: "
          + (f"{len(written)} file(s) updated — restart Glyphs to load them"
             if written else "already up to date"))


def build_parser():
    p = argparse.ArgumentParser(prog="spacing-map", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="command", required=True)

    bm = sub.add_parser("build-map",
                        help="seed/refresh the spacing scheme from the design-stages model")
    bm.add_argument("--model", default=str(model.DEFAULT_MODEL),
                    help=f"design-stages model YAML [default: {model.DEFAULT_MODEL.name}]")
    bm.add_argument("-o", "--output", default=str(DEFAULT_MAP_YAML))
    bm.add_argument("--check", action="store_true",
                    help="validate and report only; do not write")
    bm.add_argument("--limit", type=int, default=20,
                    help="max warnings/list items to print [default 20]")
    bm.set_defaults(func=cmd_build_map)

    au = sub.add_parser("audit", help="measure a font against the scheme (read-only)")
    au.add_argument("--font", required=True, help="target .glyphs(package) to measure")
    au.add_argument("--map", default=str(DEFAULT_MAP_YAML))
    au.add_argument("--tolerance", type=int, default=8,
                    help="font units a member may differ from its rep before it "
                         "counts as drift [default 8]")
    au.add_argument("--master", action="append",
                    help="master name or id to audit (repeatable) [default: all]")
    au.add_argument("--names", help="YAML mapping of scheme entries to glyph names, "
                                    "for fonts using another naming convention")
    au.add_argument("--emit-values", metavar="FILE",
                    help="write the measured per-class unit multiples to a values YAML")
    au.add_argument("-v", "--verbose", action="store_true",
                    help="list every class and member, not just drift")
    au.add_argument("--limit", type=int, default=20)
    au.set_defaults(func=cmd_audit)

    ej = sub.add_parser("export-js",
                        help="vendor the scheme as a JS module for the spacing workbench")
    ej.add_argument("--map", default=str(DEFAULT_MAP_YAML))
    ej.add_argument("-o", "--output", default=str(DEFAULT_JS))
    ej.add_argument("--check", action="store_true",
                    help="exit non-zero if the JS file is out of date; do not write")
    ej.set_defaults(func=cmd_export_js)

    bp = sub.add_parser("build-plugin",
                        help="refresh the scheme and shared code bundled in the Glyphs plugin")
    bp.add_argument("--map", default=str(DEFAULT_MAP_YAML))
    bp.add_argument("--check", action="store_true",
                    help="exit non-zero if the bundled files are out of date; do not write")
    bp.set_defaults(func=cmd_build_plugin)

    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except (FileNotFoundError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)

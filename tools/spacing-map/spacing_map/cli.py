"""spacing-map — build and apply the Sinhala spacing scheme.

The scheme (sinhala-spacing.yaml, repo root) maps every glyph's left/right
sidebearing to a spacing class: the class `rep` sets the sidebearing, members
inherit it, and `value` records the class target as a multiple of the font's
spacing_unit metric. Relationships come from the design-stages model;
values/notes/exceptions are authored in the scheme file and survive rebuilds.

Subcommands:
  build-map   seed/refresh sinhala-spacing.yaml from the design-stages model

Planned (see README.md): audit, apply, export-js.
"""
import argparse
import sys
from pathlib import Path

import yaml

from . import mapbuild, model

DEFAULT_MAP_YAML = model.REPO_ROOT / "sinhala-spacing.yaml"


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

    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except (FileNotFoundError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)

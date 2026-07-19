"""composite-map — build and apply a Sinhala composite-glyph map.

Subcommands:
  build-map   derive the map from the inventory + anchor reference fonts -> YAML
  export-js   YAML -> vendored tools/_generated/sinhala-composites.js
  audit       classify a target font's glyphs against the map (read-only)
  rebuild     replace atomically-drawn/mixed glyphs with composite references
              (dry-run by default; --apply to write)
"""
import argparse
import sys
from pathlib import Path

import yaml

from . import jsexport, mapbuild, rebuild
from .lanka_data import REPO_ROOT, load_classification

# Workspace-relative defaults for the two documentation references. Override
# with --inventory / --anchor to build a map from any other pair of sources.
MOONIAK = REPO_ROOT.parent
DEFAULT_INVENTORY = MOONIAK / "font-repos/abhaya-libre-font/sources/AbhayaLibre.glyphspackage"
DEFAULT_ANCHOR = MOONIAK / "font-repos/noto-sans-sinhala/sources/NotoSansSinhala.glyphspackage"
DEFAULT_MAP_YAML = REPO_ROOT / "sinhala-composites.yaml"
DEFAULT_JS_OUT = REPO_ROOT / "tools/_generated/sinhala-composites.js"


def _parse_tiers(s):
    return tuple(int(x) for x in s.split(",") if x.strip() != "")


def _load_map(path):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def cmd_build_map(args):
    classification = load_classification()
    data = mapbuild.build_map(args.inventory, args.anchor, classification)
    text = yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=100)
    Path(args.output).write_text(text, encoding="utf-8")
    c = data["meta"]["counts"]
    print(f"wrote {args.output}")
    print(f"  composites: {c['composites']}  by tier: {c['by_tier']}")
    print(f"  review: {c['review']}   keep_drawn: {c['keep_drawn']}")
    print(f"  inventory: {data['meta']['inventory_reference']}  "
          f"anchor: {data['meta']['anchor_reference']}")


def cmd_export_js(args):
    data = _load_map(args.map)
    Path(args.output).write_text(jsexport.to_js(data), encoding="utf-8")
    print(f"wrote {args.output}  ({len(data.get('composites', {}))} composites)")


def cmd_audit(args):
    data = _load_map(args.map)
    result = rebuild.audit(args.font, data)
    print(f"font: {result['font']}  masters: {result['masters']}")
    print(f"status: {result['status_counts']}")
    if args.verbose:
        for r in result["rows"]:
            if r["status"] in ("rebuildable", "blocked"):
                extra = f"  missing={r['missing_components']}" if r["missing_components"] else ""
                print(f"  [{r['status']:11s}] {r['name']:24s} {r['class']:9s} "
                      f"<- {' + '.join(r['components'])}{extra}")


def cmd_rebuild(args):
    data = _load_map(args.map)
    tiers = _parse_tiers(args.tiers)
    if not args.apply:
        p = rebuild.plan(args.font, data, include_tiers=tiers)
        print(f"font: {p['font']}  masters: {p['masters']}")
        print(f"status: {p['status_counts']}")
        print(f"DRY-RUN: would rebuild {len(p['edits'])} glyph(s) (tiers {tiers}). "
              f"Re-run with --apply to write.")
        for e in p["edits"][: args.limit]:
            print(f"  {e['name']:24s} {e['class']:9s} -> {' + '.join(e['components'])}")
        if len(p["edits"]) > args.limit:
            print(f"  ... and {len(p['edits']) - args.limit} more")
        return
    result = rebuild.apply(args.font, data, include_tiers=tiers, backup=args.backup)
    print(f"font: {result['font']}")
    if result["backup"]:
        print(f"backup: {result['backup']}")
    print(f"status: {result['status_counts']}")
    print(f"rebuilt {len(result['changed'])} glyph(s) as composites (tiers {tiers}).")
    for c in result["changed"][: args.limit]:
        print(f"  {c['name']:24s} -> {' + '.join(c['components'])}  ({c['layers']} layers)")
    if len(result["changed"]) > args.limit:
        print(f"  ... and {len(result['changed']) - args.limit} more")


def build_parser():
    p = argparse.ArgumentParser(prog="composite-map", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="command", required=True)

    bm = sub.add_parser("build-map", help="derive the map from reference fonts")
    bm.add_argument("--inventory", default=str(DEFAULT_INVENTORY),
                    help=f"inventory reference .glyphs(package) [default: {DEFAULT_INVENTORY.name}]")
    bm.add_argument("--anchor", default=str(DEFAULT_ANCHOR),
                    help=f"anchor reference .glyphs(package) [default: {DEFAULT_ANCHOR.name}]")
    bm.add_argument("-o", "--output", default=str(DEFAULT_MAP_YAML))
    bm.set_defaults(func=cmd_build_map)

    ej = sub.add_parser("export-js", help="YAML map -> vendored JS module")
    ej.add_argument("--map", default=str(DEFAULT_MAP_YAML))
    ej.add_argument("-o", "--output", default=str(DEFAULT_JS_OUT))
    ej.set_defaults(func=cmd_export_js)

    au = sub.add_parser("audit", help="classify a target font against the map")
    au.add_argument("--map", default=str(DEFAULT_MAP_YAML))
    au.add_argument("--font", required=True, help="target .glyphs(package) to inspect")
    au.add_argument("-v", "--verbose", action="store_true")
    au.set_defaults(func=cmd_audit)

    rb = sub.add_parser("rebuild", help="rebuild drawn glyphs as composites")
    rb.add_argument("--map", default=str(DEFAULT_MAP_YAML))
    rb.add_argument("--font", required=True, help="target .glyphs(package) to modify")
    rb.add_argument("--apply", action="store_true", help="write changes (else dry-run)")
    rb.add_argument("--tiers", default="0,1,2",
                    help="comma-separated tiers to apply [default 0,1,2; add 3 for "
                         "ispilla ිී forms, which need the alternate i-signs present]")
    rb.add_argument("--backup", action="store_true", help="copy the source before writing")
    rb.add_argument("--limit", type=int, default=40)
    rb.set_defaults(func=cmd_rebuild)

    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except (FileNotFoundError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

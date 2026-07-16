#!/usr/bin/env python3
"""mnik glyphsets — validate glyph dependencies & generate OpenType features
for LankaGlyphset Sinhala/Tamil fonts.

Examples
--------
    # Dependency report: satisfiable rules, blockers, orphans:
    mnik glyphsets validate --script sinhala --font MySource.glyphspackage

    # Emit features.fea gated on the glyphs present in the font:
    mnik glyphsets generate --script sinhala --font MyFont.ttf -o features.fea

    # Add the ZWJ/ZWNJ control glyphs, then write features into the source
    # (hand-written features/prefixes are preserved):
    mnik glyphsets generate --script sinhala --font MySource.glyphspackage \\
        --fix-zwj --glyphs-out MySource.glyphspackage

    # Merge hand-authored shape-group / stylistic-set lookups:
    mnik glyphsets generate --script sinhala --font MyFont.ttf --inject inject/

    # Fix glyph-info (Mark/Spacing) + Mooniak metadata on one source, then validate:
    mnik glyphsets fix-source --font MySource.glyphspackage

    # Same, batch across every sibling *-font repo:
    mnik glyphsets fix-source --all ../.. --dry-run
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .api import build_fea, validate_font
from .inventory import FontInventory
from .injection import collect_paths


def _load_inventory(font_path: Path) -> tuple[FontInventory, bool]:
    """Load the glyph inventory from a binary or a Glyphs source."""
    from .glyphsource import is_glyphs_source
    source_is_glyphs = is_glyphs_source(font_path)
    if source_is_glyphs:
        from .glyphsource import inventory_from_glyphs
        inventory = inventory_from_glyphs(font_path)
    else:
        inventory = FontInventory.from_font(font_path)
    return inventory, source_is_glyphs


def _print_blockers(report, limit: int = 3) -> None:
    """Short actionable blocker summary after generate's count line."""
    for b in report.blockers[:limit]:
        feats = ", ".join(f"{t}:{c}" for t, c in
                          sorted(b.features.items(), key=lambda kv: -kv[1]))
        print(f"# blocker: {b.glyph} blocks {b.blocked_rules} rules ({feats})",
              file=sys.stderr)
        if b.hint:
            print(f"#   hint: {b.hint}", file=sys.stderr)
    remaining = len(report.blockers) - limit
    if remaining > 0:
        print(f"# ... {remaining} more blockers — run `mnik glyphsets validate` for the "
              f"full dependency report", file=sys.stderr)


def _cmd_generate(args) -> int:
    if not args.font.exists():
        print(f"error: font not found: {args.font}", file=sys.stderr)
        return 1
    if args.fix_zwj:
        from .glyphsource import is_glyphs_source
        if not is_glyphs_source(args.font):
            print("error: --fix-zwj needs a .glyphs/.glyphspackage source "
                  "(binaries are report-only)", file=sys.stderr)
            return 2
        from .zwjfix import add_control_glyphs
        added = add_control_glyphs(args.font)
        if added:
            print(f"# fix-zwj: added {', '.join(added)} to {args.font}",
                  file=sys.stderr)
        else:
            print("# fix-zwj: control glyphs already present", file=sys.stderr)
    inventory, source_is_glyphs = _load_inventory(args.font)
    inject_paths = collect_paths(args.inject, args.inject_file)

    try:
        result = build_fea(
            script=args.script,
            inventory=inventory,
            level=args.level,
            inject_paths=inject_paths or None,
            prefer_feacomposer=args.feacomposer,
            validate=not args.no_validate,
            use_yaml=not args.no_yaml,
        )
    except Exception as exc:  # feaLib syntax error, missing YAML, etc.
        print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    if args.output:
        args.output.write_text(result.fea, encoding="utf-8")
        print(f"wrote {args.output}", file=sys.stderr)
    else:
        sys.stdout.write(result.fea)

    r = result.report
    print(f"# gated: {r.kept_rules} rules kept, {r.dropped_rules} dropped, "
          f"{r.dropped_lookups} empty lookups, {r.dropped_features} empty features",
          file=sys.stderr)
    if not args.quiet:
        _print_blockers(r)

    if args.compile:
        if source_is_glyphs:
            print("error: --compile needs a compiled .ttf/.otf; use --glyphs-out for "
                  "a Glyphs source", file=sys.stderr)
            return 2
        from .compile import strip_and_build
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".fea", delete=False,
                                         encoding="utf-8") as tf:
            tf.write(result.fea)
            fea_tmp = tf.name
        removed = strip_and_build(args.font, fea_tmp, args.compile)
        print(f"# compiled {args.compile} (stripped: {', '.join(removed) or 'none'})",
              file=sys.stderr)

    if args.glyphs_out:
        if not source_is_glyphs:
            print("error: --glyphs-out needs a .glyphs/.glyphspackage source as --font",
                  file=sys.stderr)
            return 2
        from .glyphsource import write_features_to_glyphs

        def _ask(tag: str) -> str:
            # Interactive collision resolution; non-TTY keeps the user's code.
            if not sys.stdin.isatty():
                print(f"# collision: hand-written '{tag}' kept (non-interactive); "
                      f"use --replace-tags {tag} to overwrite", file=sys.stderr)
                return "keep"
            answer = input(f"feature '{tag}' is hand-written in the source — "
                           f"replace with generated? [y/N] ").strip().lower()
            return "replace" if answer in ("y", "yes") else "keep"

        summary = write_features_to_glyphs(
            result.doc, result.profile.language_systems, args.font, args.glyphs_out,
            raw_snippets=result.raw_snippets,
            replace_tags=set(args.replace_tags.split(",")) if args.replace_tags else None,
            keep_tags=set(args.keep_tags.split(",")) if args.keep_tags else None,
            resolve_collision=_ask)
        print(f"# wrote {args.glyphs_out} "
              f"(replaced {summary['stripped_features']} own features; preserved "
              f"{summary['preserved_features']} user features/"
              f"{summary['preserved_prefixes']} prefixes; wrote {summary['written_features']} "
              f"features/{summary['written_classes']} classes)", file=sys.stderr)
        for tag, action in summary["collisions"].items():
            print(f"# collision {tag}: {action}", file=sys.stderr)
    return 0


def _fix_one_source(path: Path, dry_run: bool) -> int:
    """Fix glyph-info + Mooniak metadata on one Glyphs source; validate; print a
    summary line. Returns 0 if the targeted glyphs are clean after the fix."""
    from . import glyphinfo
    from .glyphinfofix import TARGET_GLYPHS, fix_font_extras, fix_glyph_info
    from .glyphspackage import load_source, save_source
    from .metadatafix import fix_font_metadata

    font = load_source(path)
    glyph_changes = fix_glyph_info(font)
    extra_changes = fix_font_extras(font)
    meta_changes = fix_font_metadata(font)

    present_names = {g.name for g in font.glyphs if g.name}
    glyph_info_map = {g.name: {"category": g.category, "subCategory": g.subCategory}
                      for g in font.glyphs if g.name}
    report = glyphinfo.check_glyph_info(present_names, glyph_info_map)
    other_findings = [f for f in report["findings"] if f["glyph"] not in TARGET_GLYPHS]
    still_wrong_targets = [f for f in report["findings"] if f["glyph"] in TARGET_GLYPHS]

    if (glyph_changes or extra_changes or meta_changes) and not dry_run:
        save_source(font, path)

    tag = "[dry-run] " if dry_run else ""
    glyph_part = f"glyph-info {len(glyph_changes)} fixed"
    if glyph_changes:
        glyph_part += f" ({', '.join(glyph_changes)})"
    extra_part = f"extras {len(extra_changes)} fixed"
    if extra_changes:
        extra_part += f" ({', '.join(extra_changes)})"
    meta_part = f"metadata {len(meta_changes)} fixed"
    if meta_changes:
        meta_part += f" ({', '.join(meta_changes)})"
    print(f"{tag}{path.name}: {glyph_part}; {extra_part}; {meta_part}")
    for f in other_findings:
        print(f"  # note: {f['glyph']} also Category/Subcategory-wrong "
              f"({f['reason']}) — outside fix-source's target list", file=sys.stderr)

    if still_wrong_targets:
        for f in still_wrong_targets:
            print(f"  # ERROR: {f['glyph']} still wrong after fix: {f['reason']}",
                  file=sys.stderr)
        return 1
    return 0


# Sources found sitting in a *-font repo's sources/ that are not actually that
# font's own design (template/reference leftovers) — skip so Mooniak vendorID/
# designerURL never gets stamped onto a third-party typeface.
NOT_MOONIAK_SOURCES = {"RadioCanadaDisplay.glyphs", "RadioCanadaDisplay-Italic.glyphs"}


def _cmd_fix_source(args) -> int:
    from .glyphsource import is_glyphs_source

    if args.all:
        root = args.all
        paths = sorted(root.glob("*-font/sources/*.glyphspackage")) + \
            sorted(root.glob("*-font/sources/*.glyphs"))
        skipped = [p for p in paths if p.name in NOT_MOONIAK_SOURCES]
        paths = [p for p in paths if p.name not in NOT_MOONIAK_SOURCES]
        for p in skipped:
            print(f"# skip (not a Mooniak source): {p}", file=sys.stderr)
        if not paths:
            print(f"error: no .glyphspackage/.glyphs sources found under {root}",
                  file=sys.stderr)
            return 1
        errors = 0
        for p in paths:
            try:
                if _fix_one_source(p, args.dry_run) != 0:
                    errors += 1
            except Exception as exc:  # keep the batch going past one bad source
                print(f"error: {p}: {type(exc).__name__}: {exc}", file=sys.stderr)
                errors += 1
        print(f"# {len(paths)} sources scanned, {errors} with issues", file=sys.stderr)
        return 1 if errors else 0

    if not args.font:
        print("error: --font or --all is required", file=sys.stderr)
        return 2
    if not args.font.exists():
        print(f"error: font not found: {args.font}", file=sys.stderr)
        return 1
    if not is_glyphs_source(args.font):
        print("error: fix-source needs a .glyphs/.glyphspackage source", file=sys.stderr)
        return 2
    return _fix_one_source(args.font, args.dry_run)


def _cmd_validate(args) -> int:
    if not args.font.exists():
        print(f"error: font not found: {args.font}", file=sys.stderr)
        return 1
    inventory, _ = _load_inventory(args.font)
    inject_paths = collect_paths(args.inject, args.inject_file)

    try:
        report = validate_font(
            script=args.script,
            inventory=inventory,
            level=args.level,
            inject_paths=inject_paths or None,
            use_yaml=not args.no_yaml,
        )
    except Exception as exc:
        print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    if args.json:
        args.json.write_text(report.to_json(), encoding="utf-8")
        print(f"wrote {args.json}", file=sys.stderr)
    sys.stdout.write(report.to_text(verbose=args.verbose))

    if args.fail_on_blockers and report.blockers:
        return 3
    if args.fail_on_glyph_info and report.glyph_info_findings:
        return 4
    return 0


def _add_common_args(p) -> None:
    p.add_argument("--script", required=True, help="sinhala | tamil")
    p.add_argument("--font", type=Path, required=True,
                   help="target font: .ttf/.otf OR a .glyphs/.glyphspackage source")
    p.add_argument("--level", type=int, default=3,
                   help="Sinhala glyphset tier 0-3 (default 3; ignored for Tamil)")
    p.add_argument("--inject", type=Path, metavar="DIR",
                   help="directory of *.yaml/*.fea custom rules to merge")
    p.add_argument("--inject-file", type=Path, action="append", metavar="FILE",
                   help="individual inject file (repeatable)")
    p.add_argument("--no-yaml", action="store_true",
                   help="run standalone: derive everything from the built-in codepoint "
                        "tables + the font's glyphs, using no glyphset YAML")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="mnik glyphsets", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)

    val = sub.add_parser("validate",
                         help="dependency report: satisfiable rules, blockers, orphans")
    _add_common_args(val)
    val.add_argument("--json", type=Path, metavar="OUT.json",
                     help="also write the machine-readable report here")
    val.add_argument("--verbose", action="store_true",
                     help="full blocker/orphan lists with sample rules")
    val.add_argument("--fail-on-blockers", action="store_true",
                     help="exit 3 if any blocker exists (for CI)")
    val.add_argument("--fail-on-glyph-info", action="store_true",
                     help="exit 4 if any spacing-mark sign has wrong/unset "
                          "Category/Subcategory (needs a Glyphs source)")
    val.set_defaults(func=_cmd_validate)

    gen = sub.add_parser("generate", help="generate features.fea for a font")
    gen.add_argument("--script", required=True, help="sinhala | tamil")
    gen.add_argument("--font", type=Path, required=True,
                     help="target font: .ttf/.otf OR a .glyphs/.glyphspackage source")
    gen.add_argument("--level", type=int, default=3,
                     help="Sinhala glyphset tier 0-3 (default 3; ignored for Tamil)")
    gen.add_argument("-o", "--output", type=Path, help="write features.fea here")
    gen.add_argument("--inject", type=Path, metavar="DIR",
                     help="directory of *.yaml/*.fea custom rules to merge")
    gen.add_argument("--inject-file", type=Path, action="append", metavar="FILE",
                     help="individual inject file (repeatable)")
    gen.add_argument("--compile", type=Path, metavar="OUT.ttf",
                     help="strip GSUB/GPOS/GDEF and compile features into this font")
    gen.add_argument("--glyphs-out", type=Path, metavar="OUT.glyphs",
                     help="strip & write features back into a Glyphs source "
                          "(requires --font to be a .glyphs/.glyphspackage)")
    gen.add_argument("--feacomposer", action="store_true",
                     help="author rules via tptq-feacomposer (default: built-in text backend)")
    gen.add_argument("--no-validate", action="store_true",
                     help="skip the feaLib syntax check")
    gen.add_argument("--no-yaml", action="store_true",
                     help="run standalone: derive everything from the built-in codepoint "
                          "tables + the font's glyphs, using no glyphset YAML")
    gen.add_argument("--quiet", action="store_true",
                     help="suppress the blocker summary")
    gen.add_argument("--fix-zwj", action="store_true",
                     help="add the bundled zerowidthjoiner/zerowidthnonjoiner "
                          "glyphs to the Glyphs source (in place) if missing")
    gen.add_argument("--replace-tags", metavar="a,b",
                     help="on --glyphs-out collision, replace these hand-written "
                          "feature tags with generated code")
    gen.add_argument("--keep-tags", metavar="a,b",
                     help="on --glyphs-out collision, always keep these "
                          "hand-written feature tags")
    gen.set_defaults(func=_cmd_generate)

    fix = sub.add_parser("fix-source",
                         help="fix glyph-info (Mark/Spacing) + Mooniak metadata "
                              "on a Glyphs source, then validate")
    fix.add_argument("--font", type=Path, help="target .glyphs/.glyphspackage source")
    fix.add_argument("--all", type=Path, nargs="?", const=Path("../.."), default=None,
                     metavar="ROOT",
                     help="batch-fix every *-font/sources/*.glyphspackage (or .glyphs) "
                          "under ROOT (default when the flag is given bare: ../..)")
    fix.add_argument("--dry-run", action="store_true",
                     help="report what would change; don't write")
    fix.set_defaults(func=_cmd_fix_source)

    args = ap.parse_args(argv)
    return args.func(args)


def main_umbrella(argv: list[str] | None = None) -> int:
    """`mnik` umbrella command: `mnik glyphsets <validate|generate> ...`.

    Room for future mooniak tools under one entry point."""
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in ("glyphsets", "lankaglyphsets"):
        return main(argv[1:])
    prog_help = ("usage: mnik <tool> ...\n\n"
                 "tools:\n"
                 "  glyphsets    LankaGlyphset validator + OpenType feature generator\n")
    if argv and argv[0] not in ("-h", "--help"):
        print(f"mnik: unknown tool {argv[0]!r}\n", file=sys.stderr)
        print(prog_help, file=sys.stderr)
        return 2
    print(prog_help)
    return 0


def main_deprecated(argv: list[str] | None = None) -> int:
    """Legacy `lankafea` console script."""
    print("warning: 'lankafea' is deprecated; use 'mnik glyphsets ...'",
          file=sys.stderr)
    return main(argv)


if __name__ == "__main__":
    raise SystemExit(main())

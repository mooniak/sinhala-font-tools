"""Rename a Tamil Glyphs source (.glyphspackage or .glyphs) to the standard's glyph and anchor names.

    python -m lankafea.migrate SOURCE.glyphspackage | SOURCE.glyphs [--aliases FILE]
                               [--adopt-legacy-names] [--apply]

Without --apply nothing is written: the report lists every rename, how many places each
touches, and any problem (a clash with a glyph that already exists, an anchor that cannot be
mapped). With --apply the package is rewritten in place (use git to undo).

What it does
  * glyph renames: ``standard name: this font's name`` pairs from --aliases and/or
    --adopt-legacy-names (only Tamil names, those in the ``taml`` namespace). The glyph file,
    its ``glyphname``, every component ``ref``, metric key, class, feature and order entry that
    names it are rewritten together, by whole name (``isign-taml.alt1`` never matches
    ``isign-taml.alt12``).
  * anchor renames: ``Anchor-N`` / ``tm_halant`` / ``MatraI.altN`` style names become the sign
    name (``virama``, ``isign``, ``iisign``, ``usign``, ``uusign``) on both the base and the
    sign glyph, per the standard's "Anchor naming". Which legacy anchor is which sign is read
    from the sign glyphs themselves (the glyph that carries ``_Anchor-2`` is the sign), so no
    per-font table is needed. A legacy anchor shared by ``usign`` and ``uusign`` is split into
    two on each base.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

from .aliases import compute_aliases, load_alias_file
from .glyphsource import inventory_from_glyphs

# The sign glyphs whose `_anchor` tells us which legacy anchor belongs to which sign.
SIGN_ANCHOR = {
    "virama-taml": ("virama",),
    "anusvaraya-taml": ("virama",),     # shares the pulli anchor
    "isign-taml": ("isign",),
    "iisign-taml": ("iisign",),
    "usign-taml": ("usign",),
    "uusign-taml": ("uusign",),
}
# A sign alternate (isign-taml.ka, usign-taml.pa, iisign-taml.stylalt1 ...) reuses its sign.
ALT_RE = re.compile(r"^(isign|iisign|usign|uusign)-taml\.")

NAME_CHARS = r"[A-Za-z0-9_.\-]"


def glyph_file(name: str) -> str:
    """Glyphs' file name for a glyph: each capital gets an underscore (kSsa -> kS_sa)."""
    return "".join(c + "_" if c.isupper() else c for c in name) + ".glyph"


def _token_regex(names) -> re.Pattern:
    alt = "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True))
    # a name may also follow the escaped newline (\012) a .glyphs file uses inside code strings
    return re.compile(rf"(?:(?<!{NAME_CHARS})|(?<=\\012))({alt})(?!{NAME_CHARS})")


def plan_glyph_renames(inv, aliases: dict[str, str]) -> tuple[dict[str, str], list[str]]:
    """font name -> standard name, plus the problems found."""
    renames: dict[str, str] = {}
    problems: list[str] = []
    for std, actual in aliases.items():
        if std == actual or "-taml" not in std:
            continue
        if actual not in inv.glyphs:
            continue
        if std in inv.glyphs:
            problems.append(f"clash: {actual} -> {std}, but {std} already exists")
            continue
        if actual in renames and renames[actual] != std:
            problems.append(f"{actual} maps to both {renames[actual]} and {std}")
            continue
        renames[actual] = std
    targets = list(renames.values())
    for t in set(targets):
        if targets.count(t) > 1:
            problems.append(f"two glyphs would both be named {t}")
    return renames, problems


# --- anchors ------------------------------------------------------------------------------

# A package/v3 anchor is `pos = (x,y);`, a v2 .glyphs one `position = "{x, y}";`; either may be
# absent (a mark anchor at 0,0). The position line is carried over verbatim.
ANCHOR_BLOCK = re.compile(r'\{\nname = "(?P<name>[^"\n]+)";(?P<pos>\n(?:pos|position) = [^\n]*;)?\n\}')


def _anchors(text: str):
    return [(m.group("name"), m.group("pos")) for m in ANCHOR_BLOCK.finditer(text)]


def is_tamil(name: str) -> bool:
    return name.endswith("-taml") or "-taml." in name


def plan_anchor_renames(glyph_texts: dict[str, str], names_after: dict[str, str]):
    """Work out legacy anchor -> sign name(s) from the sign glyphs.

    Returns (mapping, problems); mapping is legacy anchor name -> list of standard names
    (two for an anchor shared by usign and uusign)."""
    mapping: dict[str, list[str]] = {}
    problems: list[str] = []
    for gname, text in glyph_texts.items():
        std = names_after.get(gname, gname)
        if not is_tamil(std):
            continue
        sign = SIGN_ANCHOR.get(std)
        if sign is None:
            m = ALT_RE.match(std)
            sign = (m.group(1),) if m else None
        if sign is None:
            continue
        for aname, _ in _anchors(text):
            if not aname.startswith("_"):
                continue
            legacy = aname[1:]
            if legacy in sign:
                continue                      # already standard
            cur = mapping.setdefault(legacy, [])
            for s in sign:
                if s not in cur:
                    cur.append(s)
    # Order so usign comes before uusign; both names go on the base.
    for k in mapping:
        mapping[k].sort(key=lambda s: ["virama", "isign", "iisign", "usign", "uusign"].index(s))
    return mapping, problems


def rewrite_anchors(text: str, mapping: dict[str, list[str]], is_sign: bool,
                    conflicts: list[str], gname: str) -> str:
    """Rename anchors in one glyph file. A sign glyph's ``_legacy`` becomes ``_<sign>`` (one
    name, the first); a base's ``legacy`` becomes every name for it."""
    def repl(m: re.Match) -> str:
        name, pos = m.group("name"), m.group("pos")
        posline = pos or ""
        under = name.startswith("_")
        key = name[1:] if under else name
        if key not in mapping:
            return m.group(0)
        news = mapping[key]
        if under:
            return f'{{\nname = "_{news[0]}";{posline}\n}}'
        return ",\n".join(f'{{\nname = "{n}";{posline}\n}}' for n in news)

    return ANCHOR_BLOCK.sub(repl, text)


# --- driver -------------------------------------------------------------------------------

# A glyph's layers (and so its anchors) follow its `glyphname` line, whatever keys (category,
# color ...) precede it, so a glyph's text is "from this glyphname to the next one".
GLYPH_START = re.compile(r'^glyphname = "?([^";\n]+)"?;', re.M)


def _migrate_file(path: Path, aliases_file, adopt_legacy, apply) -> int:
    """A single .glyphs file: the same renames, done on glyph entries inside one text."""
    inv = inventory_from_glyphs(str(path))
    extra = load_alias_file(aliases_file) if aliases_file else None
    aliases = compute_aliases(inv, extra=extra, legacy_tamil=adopt_legacy)
    renames, problems = plan_glyph_renames(inv, aliases)

    text = path.read_text(encoding="utf8")
    starts = [(m.start(), m.group(1)) for m in GLYPH_START.finditer(text)]
    head = text[:starts[0][0]] if starts else text
    segs: dict[str, str] = {}
    for i, (st, name) in enumerate(starts):
        en = starts[i + 1][0] if i + 1 < len(starts) else len(text)
        segs[name] = text[st:en]
    amap, aproblems = plan_anchor_renames(segs, renames)
    problems += aproblems

    print(path.name)
    print(f"  glyph renames: {len(renames)}")
    for old, new in sorted(renames.items(), key=lambda kv: kv[1]):
        print(f"    {old:28s} -> {new}")
    print(f"  anchor renames: {len(amap)}")
    for old, news in sorted(amap.items()):
        print(f"    {old:12s} -> {' + '.join(news)}")
    if problems:
        print("  PROBLEMS:")
        for p in problems:
            print(f"    {p}")
    if not apply:
        print("  (dry run: nothing written; pass --apply)")
        return 1 if problems else 0
    if problems:
        print("  not applying while there are problems", file=sys.stderr)
        return 1

    for name in segs:
        std = renames.get(name, name)
        if not is_tamil(std):
            continue
        is_sign = std in SIGN_ANCHOR or bool(ALT_RE.match(std))
        segs[name] = rewrite_anchors(segs[name], amap, is_sign, [], name)
    out = head + "".join(segs.values())
    n_sub = 0
    if renames:
        out, n_sub = _token_regex(renames).subn(lambda m: renames[m.group(1)], out)
    path.write_text(out, encoding="utf8")
    print(f"  applied: {n_sub} name replacements, {len(renames)} glyphs renamed")
    return 0


def migrate(package: Path, aliases_file: str | None, adopt_legacy: bool, apply: bool) -> int:
    package = Path(package)
    if package.is_file() and package.suffix == ".glyphs":
        return _migrate_file(package, aliases_file, adopt_legacy, apply)
    glyph_dir = package / "glyphs"
    if not glyph_dir.is_dir():
        print(f"{package}: not a .glyphspackage (no glyphs/ directory)", file=sys.stderr)
        return 2

    inv = inventory_from_glyphs(str(package))
    extra = load_alias_file(aliases_file) if aliases_file else None
    aliases = compute_aliases(inv, extra=extra, legacy_tamil=adopt_legacy)
    renames, problems = plan_glyph_renames(inv, aliases)

    # every glyph name must map to a file we can find, or the rename could miss one
    files = {p.name for p in glyph_dir.glob("*.glyph")}
    for old in renames:
        if glyph_file(old) not in files:
            problems.append(f"no file {glyph_file(old)} for glyph {old}")

    texts = {p.name: p.read_text(encoding="utf8") for p in glyph_dir.glob("*.glyph")}
    by_name: dict[str, str] = {}
    for fname, t in texts.items():
        m = re.search(r'^glyphname = "?([^";\n]+)"?;', t, re.M)
        if m:
            by_name[m.group(1)] = fname

    amap, aproblems = plan_anchor_renames({n: texts[f] for n, f in by_name.items()}, renames)
    problems += aproblems

    print(f"{package.name}")
    print(f"  glyph renames: {len(renames)}")
    for old, new in sorted(renames.items(), key=lambda kv: kv[1]):
        print(f"    {old:28s} -> {new}")
    print(f"  anchor renames: {len(amap)}")
    for old, news in sorted(amap.items()):
        print(f"    {old:12s} -> {' + '.join(news)}")
    if problems:
        print("  PROBLEMS:")
        for p in problems:
            print(f"    {p}")
    if not apply:
        print("  (dry run: nothing written; pass --apply)")
        return 1 if problems else 0
    if problems:
        print("  not applying while there are problems", file=sys.stderr)
        return 1

    # 1. anchors, on the glyph texts, using post-rename names to decide sign vs base
    new_of = lambda n: renames.get(n, n)
    for gname, fname in by_name.items():
        std = new_of(gname)
        if not is_tamil(std):
            continue
        is_sign = std in SIGN_ANCHOR or bool(ALT_RE.match(std))
        texts[fname] = rewrite_anchors(texts[fname], amap, is_sign, [], gname)

    # 2. glyph names everywhere (glyph files, order.plist, fontinfo.plist, kerning ...)
    rx = _token_regex(renames) if renames else None
    n_sub = 0

    def sub(text: str) -> str:
        nonlocal n_sub
        if rx is None:
            return text
        out, n = rx.subn(lambda m: renames[m.group(1)], text)
        n_sub += n
        return out

    for fname in list(texts):
        t = sub(texts[fname])
        texts[fname] = t
    for p in package.iterdir():
        if p.is_file() and p.suffix == ".plist":
            t = p.read_text(encoding="utf8")
            new = sub(t)
            if new != t:
                p.write_text(new, encoding="utf8")

    # 3. write the glyph texts; only a glyph that was renamed moves to a new file, every other
    #    keeps whatever file name Glyphs gave it (a leading "." is stored as "_", for one).
    for gname, fname in by_name.items():
        old = glyph_dir / fname
        old.write_text(texts[fname], encoding="utf8")
        if gname in renames:
            target = glyph_dir / glyph_file(renames[gname])
            if target.exists():
                print(f"  refusing to overwrite {target.name}", file=sys.stderr)
                return 1
            old.rename(target)
    print(f"  applied: {n_sub} name replacements, {len(renames)} glyphs renamed")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m lankafea.migrate", description=__doc__.split("\n\n")[0])
    ap.add_argument("package")
    ap.add_argument("--aliases")
    ap.add_argument("--adopt-legacy-names", action="store_true")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    return migrate(Path(a.package), a.aliases, a.adopt_legacy_names, a.apply)


if __name__ == "__main__":
    sys.exit(main())

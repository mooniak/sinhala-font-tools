"""Native .glyphspackage read/write.

glyphsLib parses flat ``.glyphs`` text reliably but has no package *writer*
(``GSFont.save`` always emits a flat file). This module owns the package
layout — ``fontinfo.plist`` + ``order.plist`` + ``glyphs/<escaped>.glyph``
(+ optional ``UIState.plist``) — and delegates the openstep-plist content of
each part to glyphsLib's parser/writer, so content fidelity tracks glyphsLib
while layout stays under our control.

Filename escaping (verified against Glyphs.app's own packages, e.g. aggnni):
every uppercase letter is followed by an underscore — glyph ``tTha_repha-sinh``
lives in ``tT_ha_repha-sinh.glyph``. Glyphs' reserved dot-prefixed glyph names
(``.notdef``, ``.null``, ...) are escaped to a leading underscore instead
(``.notdef`` -> ``_notdef``) — a leading dot would make the file hidden,
invisible to naive directory scans/backups, and to Glyphs.app's own package
reader.

This is deliberately an explicit whitelist, not a generic "leading underscore
means an escaped dot" rule: Glyphs also has a real, unrelated convention of
underscore-prefixed *component* glyphs (e.g. ``_caron``, confirmed via its own
``glyphname = _caron;`` — no dot involved) that must round-trip unchanged. A
generic transform would corrupt those. Extend ``RESERVED_DOT_NAMES`` when a new
reserved name turns up (found by a name silently vanishing after a
read/write round-trip, same symptom that surfaced ``.null`` here).
"""

from __future__ import annotations

from pathlib import Path

RESERVED_DOT_NAMES = {".notdef": "_notdef", ".null": "_null"}
_STEM_TO_DOT_NAME = {v: k for k, v in RESERVED_DOT_NAMES.items()}


def escape_glyph_filename(name: str) -> str:
    if name in RESERVED_DOT_NAMES:
        return RESERVED_DOT_NAMES[name]
    out = []
    for ch in name:
        out.append(ch)
        if ch.isupper():
            out.append("_")
    return "".join(out)


def unescape_glyph_filename(stem: str) -> str:
    if stem in _STEM_TO_DOT_NAME:
        return _STEM_TO_DOT_NAME[stem]
    out = []
    i = 0
    while i < len(stem):
        ch = stem[i]
        out.append(ch)
        if ch.isupper() and i + 1 < len(stem) and stem[i + 1] == "_":
            i += 2
            continue
        i += 1
    return "".join(out)


def is_glyphspackage(path: Path | str) -> bool:
    return Path(path).suffix.lower() == ".glyphspackage"


def _read_order(pkg: Path) -> list[str]:
    """order.plist is a bare openstep array of glyph names."""
    import openstep_plist
    text = (pkg / "order.plist").read_text(encoding="utf-8")
    return list(openstep_plist.loads(text))


def read_glyphspackage(path: Path | str):
    """Assemble the package parts into flat text and parse -> GSFont.

    Glyphs are ordered by order.plist; glyph files not listed there are
    appended (Glyphs.app tolerates strays, so do we).
    """
    from glyphsLib.parser import loads

    pkg = Path(path)
    fontinfo = (pkg / "fontinfo.plist").read_text(encoding="utf-8")
    order = _read_order(pkg) if (pkg / "order.plist").exists() else []

    glyphs_dir = pkg / "glyphs"
    texts: dict[str, str] = {}
    for f in sorted(glyphs_dir.glob("*.glyph")):
        texts[unescape_glyph_filename(f.stem)] = f.read_text(encoding="utf-8")

    ordered = [n for n in order if n in texts]
    ordered += [n for n in sorted(texts) if n not in set(order)]

    glyph_block = "glyphs = (\n" + ",\n".join(texts[n].rstrip() for n in ordered) + "\n);\n"

    body = fontinfo.rstrip()
    if not body.endswith("}"):
        raise ValueError(f"{pkg}/fontinfo.plist: unexpected format")
    flat = body[:-1] + glyph_block + "}\n"
    return loads(flat)


def _strip_glyphs_block(flat: str) -> str:
    """Remove the top-level ``glyphs = (...);`` section from flat font text."""
    marker = "\nglyphs = ("
    start = flat.find(marker)
    if start < 0:
        return flat
    i = flat.index("(", start)
    depth = 0
    in_str = False
    while i < len(flat):
        ch = flat[i]
        if in_str:
            if ch == "\\":
                i += 2
                continue
            if ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                end = i + 1
                if end < len(flat) and flat[end] == ";":
                    end += 1
                if end < len(flat) and flat[end] == "\n":
                    end += 1
                return flat[:start + 1] + flat[end:]
        i += 1
    raise ValueError("unbalanced glyphs block")


def _dumps(obj, format_version: int) -> str:
    """Serialize with an explicit format version (writer.dumps defaults to v2,
    which must not be mixed into a v3 package)."""
    import io

    from glyphsLib.writer import Writer

    buf = io.StringIO()
    Writer(buf, format_version=format_version).write(obj)
    return buf.getvalue()


def write_glyphspackage(font, path: Path | str) -> None:
    """Write a GSFont as a .glyphspackage directory.

    Preserves an existing ``UIState.plist``; rewrites glyph files only when
    their content changed (keeps git diffs and mtimes minimal); removes glyph
    files for glyphs no longer in the font.
    """
    pkg = Path(path)
    fmt = getattr(font, "format_version", 3) or 3
    glyphs_dir = pkg / "glyphs"
    glyphs_dir.mkdir(parents=True, exist_ok=True)

    names: list[str] = []
    wanted_files: set[str] = set()
    for glyph in font.glyphs:
        name = glyph.name
        names.append(name)
        fname = escape_glyph_filename(name) + ".glyph"
        wanted_files.add(fname)
        text = _dumps(glyph, fmt)
        if not text.endswith("\n"):
            text += "\n"
        target = glyphs_dir / fname
        if not target.exists() or target.read_text(encoding="utf-8") != text:
            target.write_text(text, encoding="utf-8")
    # Drop stale glyph files.
    for f in glyphs_dir.glob("*.glyph"):
        if f.name not in wanted_files:
            f.unlink()

    order_text = "(\n" + ",\n".join(f'"{n}"' for n in names) + "\n)\n"
    (pkg / "order.plist").write_text(order_text, encoding="utf-8")

    fontinfo = _strip_glyphs_block(_dumps(font, fmt))
    (pkg / "fontinfo.plist").write_text(fontinfo, encoding="utf-8")
    # UIState.plist, if present from Glyphs.app, is left untouched.


def load_source(path: Path | str):
    """Load a Glyphs source of either layout as a GSFont."""
    from glyphsLib import GSFont

    p = Path(path)
    if is_glyphspackage(p):
        return read_glyphspackage(p)
    return GSFont(str(p))


def save_source(font, path: Path | str) -> None:
    """Save a GSFont as flat or package, chosen by the target extension."""
    p = Path(path)
    if is_glyphspackage(p):
        write_glyphspackage(font, p)
    else:
        font.save(str(p))

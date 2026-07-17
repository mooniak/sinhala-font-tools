"""--fix-zwj: add the bundled ZWJ/ZWNJ control glyphs to a Glyphs source.

The glyphs ship as authored ``.glyph`` files under ``data/glyphs/`` (drawn
control-character outlines, width 0, correct unicodes). They are inserted with
their layers remapped onto the target font's masters:

* ``.glyphspackage`` — the remapped file is written into ``glyphs/`` and the
  name appended to ``order.plist`` (no full package rewrite needed);
* flat ``.glyphs`` — the remapped text is parsed via glyphsLib and the glyph
  object appended, then the font is saved in place.

Shapers hide default-ignorables (U+200D/U+200C) at render time, so the visible
outlines only ever show in glyph overviews — they are safe to export.
"""

from __future__ import annotations

import re
from importlib import resources
from pathlib import Path

CONTROL_GLYPHS = ("zerowidthjoiner", "zerowidthnonjoiner")

_LAYERID_RE = re.compile(r'layerId = "[^"]+";')


def _bundled_glyph_text(name: str) -> str:
    ref = resources.files("lankafea").joinpath(f"data/glyphs/{name}.glyph")
    return ref.read_text(encoding="utf-8")


def _split_layer_blocks(text: str) -> tuple[str, list[str], str]:
    """Split a .glyph file into (head, [layer blocks], tail).

    Layer blocks are the top-level ``{...}`` chunks inside ``layers = (...)``.
    """
    start = text.index("layers = (")
    open_paren = text.index("(", start)
    depth = 0
    i = open_paren
    blocks: list[str] = []
    block_start = None
    while i < len(text):
        ch = text[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                close_paren = i
                break
        elif ch == "{":
            if depth == 1 and block_start is None:
                block_start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 1 and block_start is not None:
                blocks.append(text[block_start:i + 1])
                block_start = None
        i += 1
    else:
        raise ValueError("unbalanced layers block in .glyph file")
    return text[:open_paren + 1], blocks, text[close_paren:]


def _remap_layers(text: str, master_ids: list[str]) -> str:
    """Assign the glyph's layers to the target font's masters, in order.

    Extra bundled layers are dropped; if the font has more masters than the
    bundle has layers, the last layer is duplicated.
    """
    head, blocks, tail = _split_layer_blocks(text)
    if not blocks:
        raise ValueError("no layers in bundled .glyph file")
    out_blocks = []
    for idx, mid in enumerate(master_ids):
        src = blocks[min(idx, len(blocks) - 1)]
        out_blocks.append(_LAYERID_RE.sub(f'layerId = "{mid}";', src, count=1))
    return head + "\n" + ",\n".join(out_blocks) + "\n" + tail


def add_control_glyphs(source_path: Path | str,
                       names: tuple[str, ...] = CONTROL_GLYPHS) -> list[str]:
    """Add missing control glyphs to a Glyphs source in place.

    Returns the list of glyph names actually added (skips ones already
    present by name or by codepoint).
    """
    from glyphsLib import GSFont

    source_path = Path(source_path)
    font = GSFont(str(source_path))
    master_ids = [m.id for m in font.masters]
    if not master_ids:
        raise ValueError(f"{source_path}: no masters found")

    present_names = {g.name for g in font.glyphs}
    present_unicodes: set[str] = set()
    for g in font.glyphs:
        for u in (g.unicodes or ([g.unicode] if g.unicode else [])):
            present_unicodes.add(str(u).upper())

    unicode_of = {"zerowidthjoiner": "200D", "zerowidthnonjoiner": "200C"}
    to_add = [n for n in names
              if n not in present_names and unicode_of[n] not in present_unicodes]
    if not to_add:
        return []

    if source_path.suffix.lower() == ".glyphspackage":
        _add_to_package(source_path, to_add, master_ids)
    else:
        _add_to_flat(font, source_path, to_add, master_ids)
    return to_add


def _add_to_package(pkg: Path, names: list[str], master_ids: list[str]) -> None:
    glyphs_dir = pkg / "glyphs"
    order_plist = pkg / "order.plist"
    for name in names:
        text = _remap_layers(_bundled_glyph_text(name), master_ids)
        # Package filenames escape capitals with a trailing underscore; these
        # names are all-lowercase so they need no escaping.
        (glyphs_dir / f"{name}.glyph").write_text(text, encoding="utf-8")
    order = order_plist.read_text(encoding="utf-8")
    entries = "".join(f'"{n}",\n' for n in names)
    closing = order.rstrip()
    if not closing.endswith(")"):
        raise ValueError(f"{order_plist}: unexpected format")
    body = closing[:-1].rstrip()
    if not body.endswith("(") and not body.endswith(","):
        body += ","
    order_plist.write_text(body + "\n" + entries + ")\n", encoding="utf-8")


def _add_to_flat(font, path: Path, names: list[str], master_ids: list[str]) -> None:
    from glyphsLib.classes import GSGlyph
    from glyphsLib.parser import Parser

    for name in names:
        text = _remap_layers(_bundled_glyph_text(name), master_ids)
        # Bundled files are stored in v3 syntax; parsed objects are
        # format-agnostic, so font.save writes them in the font's own version.
        glyph = Parser(current_type=GSGlyph, format_version=3).parse(text)
        font.glyphs.append(glyph)
    font.save(str(path))

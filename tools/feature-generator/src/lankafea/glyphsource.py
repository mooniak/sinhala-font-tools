"""Glyphs.app source support (.glyphs and .glyphspackage).

Two integration points, both mirroring the compiled-font flow:

* :func:`inventory_from_glyphs` — read the glyph inventory from a source, so the
  same presence-gating applies (the gate keys on glyph NAMES, so a source is a
  drop-in for a compiled font here).
* :func:`write_features_to_glyphs` — strip the source's existing features / classes
  / feature-prefixes and write the generated ones back, saving to a NEW path
  (the ``--glyphs-out`` analogue of ``--compile``). GSFeature.code holds the body
  only; Glyphs supplies the ``feature tag { ... }`` wrapper.

Requires glyphsLib (optional dependency: ``pip install -e ".[glyphs]"``).
"""

from __future__ import annotations

from pathlib import Path

from .feacomposer_adapter import TextBackend
from .inventory import FontInventory
from .model import FeatureDoc
from .ownership import (
    INJECTED_PREFIX, LANGUAGESYSTEMS_PREFIX, MANIFEST_PREFIX, MARKER, SCRIPT_TAGS,
    collides, header, is_generated, is_multi_script, manifest_code,
    merge_languagesystems, owned_by, owned_class_names,
)

GLYPHS_SUFFIXES = {".glyphs", ".glyphspackage"}

# Ownership marker (see ownership.py): only features/prefixes whose code begins with
# MARKER are lankafea's to strip and rewrite — and, in a source that holds more than
# one script, only those of the script being generated. Everything else is user
# content and survives byte-identical. Classes cannot carry comments, so generated
# class names are tracked in the manifest prefix instead.


def is_glyphs_source(path: Path | str) -> bool:
    return Path(path).suffix.lower() in GLYPHS_SUFFIXES


def _load(path: Path | str):
    from .glyphspackage import load_source
    return load_source(path)


def inventory_from_glyphs(path: Path | str) -> FontInventory:
    font = _load(path)
    names: set[str] = set()
    cmap_names: dict[int, str] = {}
    anchors: dict[str, set[str]] = {}
    glyph_info: dict[str, dict] = {}
    non_exporting: set[str] = set()
    first_master = font.masters[0].id if font.masters else None
    for g in font.glyphs:
        if not g.name:
            continue
        # Glyphs' per-glyph "Export" switch (`export = 0;` in the file). Such a
        # glyph won't exist in the compiled font, so it must not gate rules in,
        # claim a codepoint, or be offered as an alternate.
        if not g.export:
            non_exporting.add(g.name)
            continue
        names.add(g.name)
        # Category/Subcategory as stored in the source (None when the designer
        # left it unset — which the glyph-info validator flags). glyphsLib does
        # not auto-derive these, so this reflects the source verbatim.
        glyph_info[g.name] = {"category": g.category, "subCategory": g.subCategory}
        for u in (g.unicodes or ([g.unicode] if g.unicode else [])):
            try:
                cmap_names.setdefault(int(str(u), 16), g.name)
            except ValueError:
                pass
        if first_master:
            layer = next((l for l in g.layers if l.layerId == first_master), None)
            if layer is not None and layer.anchors:
                anchors[g.name] = {a.name for a in layer.anchors if a.name}
    # Harvest the source's own glyph classes (shape groups etc.) so generated
    # contextual rules can reference them (Noto model).
    # Members that don't export are dropped, or the class would reference
    # glyphs the compiled font lacks.
    # Classes lankafea wrote itself (listed in the manifest) are not the designer's:
    # harvesting them would freeze last run's membership as if it were a decision.
    owned = _owned_class_names(font)
    source_classes = {c.name: [m for m in (c.code or "").split()
                               if m not in non_exporting]
                      for c in font.classes if c.name and c.name not in owned}
    return FontInventory(names, set(cmap_names.keys()), cmap_names, anchors,
                         source_classes, glyph_info, non_exporting)


def _manifest_code(font) -> str | None:
    for prefix in font.featurePrefixes:
        if prefix.name == MANIFEST_PREFIX:
            return prefix.code
    return None


def _owned_class_names(font, script: str | None = None) -> set[str]:
    """Class names recorded in the manifest prefix (ours to replace). With a script,
    only that script's: another script's generated classes are not ours to touch."""
    class_code = {c.name: (c.code or "") for c in font.classes if c.name}
    return owned_class_names(_manifest_code(font), script, class_code)


def write_features_to_glyphs(
    doc: FeatureDoc,
    language_systems: dict[str, list[str]],
    src_path: Path | str,
    out_path: Path | str,
    raw_snippets: list[str] | None = None,
    replace_tags: set[str] | None = None,
    keep_tags: set[str] | None = None,
    resolve_collision=None,
    script: str | None = None,
    scope_scripts: bool | None = None,
) -> dict:
    """Replace lankafea-owned layout code in a Glyphs source; PRESERVE the rest.

    Only features/prefixes carrying the ownership MARKER (plus manifest-listed
    classes) are stripped. A hand-written feature whose tag we also generate is
    a collision: resolution order is ``replace_tags`` > ``keep_tags`` >
    ``resolve_collision(tag) -> "keep"|"replace"`` callback > keep (default —
    never destroy designer work silently).

    ``script`` ("sinhala" / "tamil") makes the write safe for a source that holds
    both scripts, so they can be generated one after the other:

    * only that script's generated code and classes are replaced;
    * a hand-written feature collides only if it can affect that script (it is not
      scoped by ``script taml;`` to another one), so ``--replace-tags akhn`` takes
      out the Tamil ``akhn`` and leaves the Sinhala one;
    * the shared ``Languagesystems`` prefix and the class manifest are merged, not
      rewritten;
    * with ``scope_scripts`` (default: on when the source has glyphs in both
      scripts) generated code is wrapped in ``script taml; … script tml2; …``, so
      Sinhala rules are not registered for Tamil and the other way round.

    Without ``script`` every generated block is ours, as before.

    Returns a summary dict incl. per-tag collision outcomes.
    """
    from glyphsLib.classes import GSFeature, GSClass, GSFeaturePrefix

    from .glyphspackage import save_source

    replace_tags = replace_tags or set()
    keep_tags = keep_tags or set()
    font = _load(src_path)

    scoped = False
    tags: list[str] | None = None
    if script is not None:
        scoped = (is_multi_script(g.name for g in font.glyphs if g.name)
                  if scope_scripts is None else scope_scripts)
        if scoped:
            tags = sorted(SCRIPT_TAGS[script])        # taml before tml2

    manifest_old = _manifest_code(font)
    class_code = {c.name: (c.code or "") for c in font.classes if c.name}
    owned_classes = owned_class_names(manifest_old, script, class_code)

    mine_f = [f for f in font.features if owned_by(f.code, script)]
    # Prefixes: our injected snippets and any other generated block; the manifest is
    # rebuilt below. The Languagesystems prefix is shared, so with a script it is
    # merged rather than stripped.
    mine_p = []
    for p in font.featurePrefixes:
        if p.name == MANIFEST_PREFIX:
            mine_p.append(p)
        elif p.name == LANGUAGESYSTEMS_PREFIX:
            if script is None and is_generated(p.code):
                mine_p.append(p)
        elif p.name.startswith(INJECTED_PREFIX) and owned_by(p.code, script):
            mine_p.append(p)
        elif is_generated(p.code) and owned_by(p.code, script):
            mine_p.append(p)
    summary = {
        "stripped_features": len(mine_f),
        "stripped_classes": len([c for c in font.classes if c.name in owned_classes]),
        "stripped_prefixes": len(mine_p),
        "preserved_features": len(font.features) - len(mine_f),
        "preserved_prefixes": len(font.featurePrefixes) - len(mine_p),
        "collisions": {},
    }

    font.features = [f for f in font.features if f not in mine_f]
    font.featurePrefixes = [p for p in font.featurePrefixes if p not in mine_p]
    font.classes = [c for c in font.classes if c.name not in owned_classes]

    user_class_names = {c.name for c in font.classes}
    text = TextBackend()

    # Language systems prefix. A user's own is never touched. Ours is created, and in
    # script mode extended with this script's lines.
    existing_ls = next((p for p in font.featurePrefixes
                        if p.name == LANGUAGESYSTEMS_PREFIX), None)
    if existing_ls is None:
        lines = [f"languagesystem {s} {lang};"
                 for s, langs in language_systems.items() for lang in langs]
        font.featurePrefixes.append(
            GSFeaturePrefix(LANGUAGESYSTEMS_PREFIX, MARKER + "\n" + "\n".join(lines)))
    elif script is not None and is_generated(existing_ls.code):
        existing_ls.code = merge_languagesystems(existing_ls.code, language_systems)

    # Classes (skip names the user owns; record ours in the manifest).
    written_classes: list[str] = []
    for cls in doc.classes:
        if not cls.members:
            continue
        if cls.name in user_class_names:
            summary["collisions"][f"@{cls.name}"] = "keep"
            continue
        font.classes.append(GSClass(cls.name, " ".join(cls.members)))
        written_classes.append(cls.name)

    # Features, with per-tag collision resolution. A hand-written feature of the same
    # tag collides only if it can affect this script.
    written = 0
    for feature in doc.features:
        body = text.emit_feature_body(feature, tags)
        if not body:
            continue
        clashing = [f for f in font.features
                    if f.name == feature.tag and collides(f.code, script)]
        if clashing:
            if feature.tag in replace_tags:
                action = "replace"
            elif feature.tag in keep_tags:
                action = "keep"
            elif resolve_collision is not None:
                action = resolve_collision(feature.tag)
            else:
                action = "keep"
            summary["collisions"][feature.tag] = action
            if action != "replace":
                continue
            font.features = [f for f in font.features if f not in clashing]
        font.features.append(GSFeature(feature.tag, header(script, scoped) + "\n" + body))
        written += 1

    # Raw injected snippets -> marked prefix so they survive round-trips.
    if raw_snippets:
        name = f"{INJECTED_PREFIX}-{script}" if scoped else INJECTED_PREFIX
        font.featurePrefixes.append(GSFeaturePrefix(
            name, header(script, scoped) + "\n" + "\n\n".join(raw_snippets)))

    # Manifest records which classes are ours to strip next run (per script).
    font.featurePrefixes.append(GSFeaturePrefix(
        MANIFEST_PREFIX,
        manifest_code(manifest_old, script, scoped, written_classes, class_code)))

    summary["in_place"] = _save(font, src_path, out_path)
    summary["written_features"] = written
    summary["written_classes"] = len(written_classes)
    return summary


# --------------------------------------------------------------------------- #
# Writing back in place: only the layout code changes
#
# A glyphsLib round trip is not byte-faithful: it re-quotes glyph names, rounds
# component scales, rewrites master metrics and order.plist. Writing the features
# back into the SAME source must not touch any of that, so the font is serialised
# to a scratch copy and only its three top-level layout blocks (classes,
# featurePrefixes, features) are spliced into the existing file, byte for byte.
# --------------------------------------------------------------------------- #

LAYOUT_KEYS = ("classes", "featurePrefixes", "features")


def _layout_blocks(text: str) -> dict:
    import re
    out = {}
    for key in LAYOUT_KEYS:
        m = re.search(r"^%s = \(\n.*?^\);\n" % key, text, re.S | re.M)
        if m:
            out[key] = m
    return out


def splice_layout(new_text: str, old_text: str) -> str | None:
    """``old_text`` with its layout blocks replaced by ``new_text``'s; ``None`` when a
    block ``new_text`` has is missing from ``old_text`` (nowhere safe to put it)."""
    new, old = _layout_blocks(new_text), _layout_blocks(old_text)
    if set(new) - set(old):
        return None
    out = old_text
    for key in sorted(old, key=lambda k: old[k].start(), reverse=True):
        m = old[key]
        out = out[:m.start()] + (new[key].group(0) if key in new else "") + out[m.end():]
    return out


def _layout_file(path: Path) -> Path:
    from .glyphspackage import is_glyphspackage
    return path / "fontinfo.plist" if is_glyphspackage(path) else path


def _save(font, src_path, out_path) -> bool:
    """Save; in place when writing back into the source itself. Returns True when only
    the layout blocks of the existing file were replaced."""
    import tempfile
    from .glyphspackage import save_source

    src, out = Path(src_path).resolve(), Path(out_path).resolve()
    if src != out:
        save_source(font, out_path)
        return False
    with tempfile.TemporaryDirectory() as tmp:
        scratch = Path(tmp) / src.name
        save_source(font, scratch)
        new_text = _layout_file(scratch).read_text(encoding="utf-8")
    target = _layout_file(src)
    spliced = splice_layout(new_text, target.read_text(encoding="utf-8"))
    if spliced is None:                    # e.g. the source had no classes block yet
        save_source(font, out_path)
        return False
    target.write_text(spliced, encoding="utf-8")
    return True

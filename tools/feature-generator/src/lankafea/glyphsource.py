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

GLYPHS_SUFFIXES = {".glyphs", ".glyphspackage"}

# Ownership marker: only features/prefixes whose code begins with this line are
# lankafea's to strip and rewrite. Everything else is user content and survives
# byte-identical. Classes cannot carry comments, so generated class names are
# tracked in the manifest prefix instead.
MARKER = "# lankafea:generated v1 — do not edit; regenerate with lankafea"
MANIFEST_PREFIX = "lankafea-manifest"


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
    first_master = font.masters[0].id if font.masters else None
    for g in font.glyphs:
        if not g.name:
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
    source_classes = {c.name: (c.code or "").split()
                      for c in font.classes if c.name}
    return FontInventory(names, set(cmap_names.keys()), cmap_names, anchors,
                         source_classes, glyph_info)


def _owned_class_names(font) -> set[str]:
    """Class names recorded in the manifest prefix (ours to replace)."""
    for prefix in font.featurePrefixes:
        if prefix.name == MANIFEST_PREFIX:
            for line in (prefix.code or "").splitlines():
                if line.startswith("# classes:"):
                    return set(line[len("# classes:"):].split())
    return set()


def write_features_to_glyphs(
    doc: FeatureDoc,
    language_systems: dict[str, list[str]],
    src_path: Path | str,
    out_path: Path | str,
    raw_snippets: list[str] | None = None,
    replace_tags: set[str] | None = None,
    keep_tags: set[str] | None = None,
    resolve_collision=None,
) -> dict:
    """Replace lankafea-owned layout code in a Glyphs source; PRESERVE the rest.

    Only features/prefixes carrying the ownership MARKER (plus manifest-listed
    classes) are stripped. A hand-written feature whose tag we also generate is
    a collision: resolution order is ``replace_tags`` > ``keep_tags`` >
    ``resolve_collision(tag) -> "keep"|"replace"`` callback > keep (default —
    never destroy designer work silently).

    Returns a summary dict incl. per-tag collision outcomes.
    """
    from glyphsLib.classes import GSFeature, GSClass, GSFeaturePrefix

    from .glyphspackage import save_source

    replace_tags = replace_tags or set()
    keep_tags = keep_tags or set()
    font = _load(src_path)

    owned_classes = _owned_class_names(font)
    is_ours_f = [f for f in font.features
                 if (f.code or "").lstrip().startswith("# lankafea:generated")]
    is_ours_p = [p for p in font.featurePrefixes
                 if (p.code or "").lstrip().startswith("# lankafea:generated")
                 or p.name == MANIFEST_PREFIX
                 or p.name == "lankafea-injected"]
    summary = {
        "stripped_features": len(is_ours_f),
        "stripped_classes": len([c for c in font.classes if c.name in owned_classes]),
        "stripped_prefixes": len(is_ours_p),
        "preserved_features": len(font.features) - len(is_ours_f),
        "preserved_prefixes": len(font.featurePrefixes) - len(is_ours_p),
        "collisions": {},
    }

    font.features = [f for f in font.features if f not in is_ours_f]
    font.featurePrefixes = [p for p in font.featurePrefixes if p not in is_ours_p]
    font.classes = [c for c in font.classes if c.name not in owned_classes]

    user_tags = {f.name for f in font.features}
    user_class_names = {c.name for c in font.classes}
    text = TextBackend()

    # Language systems prefix: only when the user has none of their own.
    if not any(p.name == "Languagesystems" for p in font.featurePrefixes):
        ls_lines = [f"languagesystem {s} {lang};"
                    for s, langs in language_systems.items() for lang in langs]
        font.featurePrefixes.append(
            GSFeaturePrefix("Languagesystems", MARKER + "\n" + "\n".join(ls_lines)))

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

    # Features, with per-tag collision resolution.
    written = 0
    for feature in doc.features:
        body = text.emit_feature_body(feature)
        if not body:
            continue
        if feature.tag in user_tags:
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
            font.features = [f for f in font.features if f.name != feature.tag]
        font.features.append(GSFeature(feature.tag, MARKER + "\n" + body))
        written += 1

    # Raw injected snippets -> marked prefix so they survive round-trips.
    if raw_snippets:
        font.featurePrefixes.append(GSFeaturePrefix(
            "lankafea-injected", MARKER + "\n" + "\n\n".join(raw_snippets)))

    # Manifest records which classes are ours to strip next run.
    manifest = MARKER + "\n# classes: " + " ".join(written_classes)
    font.featurePrefixes.append(GSFeaturePrefix(MANIFEST_PREFIX, manifest))

    save_source(font, out_path)
    summary["written_features"] = written
    summary["written_classes"] = len(written_classes)
    return summary

"""Load LankaGlyphset YAML into typed specs.

Port of ``src/core/parser.ts``: honours ``namespace`` + ``Exclude namespace from``,
skips ``#``-commented keys, and loads Sinhala cumulatively across tiers. Nested
sub-categories (the ``ssNN`` groups in sinhala-3-pro.yaml) are flattened, retaining
the parent stylistic-set name.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .scripts import ScriptProfile


@dataclass
class GlyphSpec:
    """One glyph declared in a glyphset YAML."""

    name: str                    # bare name, e.g. "ka" or "daa._c"
    full_name: str               # namespaced, e.g. "ka-sinh"
    category: str
    unicode: int | None = None
    decompose: list[str] | None = None
    signs: list[str] | None = None
    conjunct: list[str] | None = None
    touch: list[str] | None = None
    style_set: str | None = None  # e.g. "ss01 Da Forms" when nested


@dataclass
class ScriptSpecs:
    profile: ScriptProfile
    glyphs: list[GlyphSpec] = field(default_factory=list)
    by_name: dict[str, GlyphSpec] = field(default_factory=dict)   # keyed by bare name

    def consonants(self) -> list[GlyphSpec]:
        cps = self.profile.tables.consonants
        return [g for g in self.glyphs
                if g.category == "Letters" and g.unicode in cps]

    def in_category(self, category: str) -> list[GlyphSpec]:
        return [g for g in self.glyphs if g.category == category]

    def style_sets(self) -> dict[str, list[GlyphSpec]]:
        out: dict[str, list[GlyphSpec]] = {}
        for g in self.glyphs:
            if g.style_set:
                out.setdefault(g.style_set, []).append(g)
        return out


def _parse_unicode(value) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.lower().startswith("0x"):
        return int(value, 16)
    return None


def _walk_category(category: str, node, use_ns: bool, namespace: str,
                   style_set: str | None) -> list[GlyphSpec]:
    """Recurse one category dict, flattening nested ssNN sub-groups."""
    out: list[GlyphSpec] = []
    if not node:
        return out
    for key, meta in node.items():
        if key.startswith("#"):
            continue
        # A nested group (value is a dict WITHOUT glyph-metadata keys) is a
        # stylistic sub-category such as "ss01 Da Forms".
        if isinstance(meta, dict) and not _looks_like_metadata(meta):
            out += _walk_category(category, meta, use_ns, namespace, style_set=key)
            continue
        meta = meta if isinstance(meta, dict) else None
        full = f"{key}-{namespace}" if use_ns else key
        out.append(GlyphSpec(
            name=key,
            full_name=full,
            category=category,
            unicode=_parse_unicode(meta.get("unicode") if meta else None),
            decompose=meta.get("decompose") if meta else None,
            signs=meta.get("signs") if meta else None,
            conjunct=meta.get("conjunct") if meta else None,
            touch=meta.get("touch") if meta else None,
            style_set=style_set,
        ))
    return out


_METADATA_KEYS = {"unicode", "decompose", "signs", "conjunct", "touch"}


def _looks_like_metadata(d: dict) -> bool:
    return any(k in _METADATA_KEYS for k in d.keys())


def synth_specs(profile: ScriptProfile) -> ScriptSpecs:
    """Build minimal specs from the built-in codepoint tables — NO YAML.

    Consonants come from ``profile.tables`` so ``specs.consonants()`` works; there is
    no conjunct/touch metadata and no glyph categories, so the generators fall back
    to cartesian candidate generation and rely entirely on presence-gating. This is
    what lets the library run standalone with no data files.
    """
    specs = ScriptSpecs(profile=profile)
    t = profile.tables
    for cp, stem in t.consonants.items():
        name = stem + "a"
        g = GlyphSpec(name=name, full_name=f"{name}-{profile.namespace}",
                      category="Letters", unicode=cp)
        specs.glyphs.append(g)
        specs.by_name[name] = g
    return specs


def load_specs(profile: ScriptProfile) -> ScriptSpecs:
    specs = ScriptSpecs(profile=profile)
    for path in profile.yaml_paths():
        definition = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        namespace = definition.get("namespace", profile.namespace)
        exclude = set(definition.get("Exclude namespace from", []) or [])
        for category, node in (definition.get("categories") or {}).items():
            use_ns = category not in exclude
            for g in _walk_category(category, node, use_ns, namespace, style_set=None):
                specs.glyphs.append(g)
                specs.by_name[g.name] = g
    return specs

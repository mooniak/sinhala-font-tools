"""Font-specific glyph-name aliasing.

The generators write the STANDARD's names. A font may call a glyph something else:
U+200D under ``zwj`` or ``uni200D``, or, before a Tamil font is migrated to the
standard, ``nna2-u-taml`` for ``nnnU-taml`` and ``isign.alt5-taml`` for a shape-group
alternate. Rather than threading overrides through every generator, the generated
document is rewritten in one pass before gating: each standard name is replaced
with the font's own name for that glyph.

Three sources, merged (a table the user gives wins over the rest):

* the font's own ZWJ glyph, found through the cmap (always);
* ``--adopt-legacy-names``: the Tamil renames that are deterministic (``nna2`` →
  ``nnna``, the dot-suffix on the other side of the namespace);
* ``--aliases FILE``: a ``standard name: font name`` table. This is the only way to
  say which numbered ``isign.altN`` is which shape group, because that differs from
  font to font and cannot be derived.
"""

from __future__ import annotations

import json
from pathlib import Path

from .inventory import FontInventory
from .model import FeatureDoc
from .names import NO_NAMESPACE

# The old standard (and the fonts built on it) called ன ``nna2``; the standard now
# calls it ``nnna`` (D2). nnna form -> its legacy stem.
_NNNA_FORMS = {
    "nnna": "nna2", "nnnI": "nna2-i", "nnnIi": "nna2-ii", "nnnU": "nna2-u",
    "nnnUu": "nna2-uu", "nnnAa": "nna2-aa", "nnnAi": "nna2-ai",
}

# Standard Tamil names that fonts spelled differently before the standard fixed the
# dot-suffix after the namespace. Each entry lists the legacy spellings, tried in order.
_TAMIL_VARIANTS = {
    "ra.alt": ["ra.alt"],
    "nnAa": ["nnAa.alt"], "rrAa": ["rrAa.alt"], "nnnAa": ["nnnAa.alt", "nna2-aa.alt"],
    "usign.pa": ["usign.alt1"],
    "iisign.la": ["iisign.alt1"],
    "aisign.la": ["aisign.alt"],
}


def legacy_tamil_aliases(inventory: FontInventory, namespace: str = "taml") -> dict[str, str]:
    """standard name -> the font's pre-standard name, for the renames that are
    deterministic. A standard name the font already has is never aliased."""
    ns = f"-{namespace}"
    glyphs = inventory.glyphs
    out: dict[str, str] = {}

    def add(standard: str, candidates: list[str]) -> None:
        if standard in glyphs:
            return
        for cand in candidates:
            if cand in glyphs:
                out[standard] = cand
                return

    for std_stem, legacy_stem in _NNNA_FORMS.items():
        add(f"{std_stem}{ns}", [f"{legacy_stem}{ns}"])
    for std_stem, legacies in _TAMIL_VARIANTS.items():
        base, _, variant = std_stem.partition(".")
        standard = f"{base}{ns}.{variant}" if variant else f"{base}{ns}"
        spellings: list[str] = []
        for legacy in legacies:
            lbase, _, lvariant = legacy.partition(".")
            spellings += [f"{lbase}.{lvariant}{ns}",       # suffix before the namespace
                          f"{lbase}{ns}.{lvariant}"]       # suffix after it
        add(standard, spellings)
    return out


def load_alias_file(path: Path | str) -> dict[str, str]:
    """A ``standard name: font name`` table, as YAML or JSON."""
    text = Path(path).read_text(encoding="utf-8")
    if str(path).lower().endswith(".json"):
        data = json.loads(text)
    else:
        import yaml
        data = yaml.safe_load(text)
    data = data or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a mapping of standard name -> font name")
    return {str(k): str(v) for k, v in data.items()}


def compute_aliases(inventory: FontInventory,
                    extra: dict[str, str] | None = None,
                    legacy_tamil: bool = False,
                    namespace: str = "taml") -> dict[str, str]:
    """standard name -> the font's actual glyph name for it."""
    aliases: dict[str, str] = {}
    for cp, canonical in NO_NAMESPACE.items():
        if canonical in inventory.glyphs:
            continue                       # font already uses the standard name
        actual = inventory.name_for(cp)
        if actual:
            aliases[canonical] = actual
    if legacy_tamil:
        aliases.update(legacy_tamil_aliases(inventory, namespace))
    if extra:
        aliases.update(extra)              # an explicit table wins
    return aliases


def apply_aliases(doc: FeatureDoc, aliases: dict[str, str]) -> int:
    """Rewrite rule/class tokens in place; returns the number of replacements."""
    if not aliases:
        return 0

    def swap(token: str) -> str:
        marked = token.endswith("'")
        t = token[:-1] if marked else token
        new = aliases.get(t, t)
        return new + "'" if marked else new

    n = 0
    for cls in doc.classes:
        for i, m in enumerate(cls.members):
            new = swap(m)
            if new != m:
                cls.members[i] = new
                n += 1
    for feature in doc.features:
        for lookup in feature.lookups:
            if lookup.mark_filter_set:
                lookup.mark_filter_set = [swap(g) for g in lookup.mark_filter_set]
            for rule in lookup.rules:
                for i, t in enumerate(rule.inputs):
                    new = swap(t)
                    if new != t:
                        rule.inputs[i] = new
                        n += 1
                if isinstance(rule.output, str):
                    new = swap(rule.output)
                    if new != rule.output:
                        rule.output = new
                        n += 1
                elif isinstance(rule.output, list):
                    for i, t in enumerate(rule.output):
                        new = swap(t)
                        if new != t:
                            rule.output[i] = new
                            n += 1
    return n

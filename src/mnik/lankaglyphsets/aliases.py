"""Font-specific glyph-name aliasing.

The standard names ZWJ ``zerowidthjoiner``, but a font may encode U+200D under
another name (``zwj``, ``uni200D`` …). Rather than threading overrides through
every generator, the generated document is rewritten in one pass before gating:
each canonical name whose codepoint the font encodes under a different name is
replaced with the font's actual name.
"""

from __future__ import annotations

from .inventory import FontInventory
from .model import FeatureDoc
from .names import NO_NAMESPACE


def compute_aliases(inventory: FontInventory) -> dict[str, str]:
    """canonical name -> the font's actual glyph name for that codepoint."""
    aliases: dict[str, str] = {}
    for cp, canonical in NO_NAMESPACE.items():
        if canonical in inventory.glyphs:
            continue                       # font already uses the standard name
        actual = inventory.name_for(cp)
        if actual:
            aliases[canonical] = actual
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

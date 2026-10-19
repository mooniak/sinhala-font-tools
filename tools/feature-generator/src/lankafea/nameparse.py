"""Decode LankaGlyphset glyph names — the inverse of names.py.

Used by the validator to explain orphans: given ``ka_repha-sinh`` it answers
"repha ligature on base ka", so the report can say what kind of rule would
consume the glyph even when no candidate rule references it yet.

Parsing is heuristic (names are not fully reversible), so results are advisory
descriptions, never inputs to rule generation — names.py stays the only namer.
"""

from __future__ import annotations

from dataclasses import dataclass

from .scripts import ScriptTables


@dataclass
class ParsedName:
    kind: str                 # "repha-lig" | "carrier-lig" | "rakar" | "yansa"
                              # | "vowel-lig" | "pure" | "conjunct" | "alt" | "base"
    description: str


def _strip_ns(name: str, namespace: str) -> str | None:
    suffix = f"-{namespace}"
    return name[: -len(suffix)] if name.endswith(suffix) else None


def _vowel_suffixes(tables: ScriptTables) -> dict[str, str]:
    """ligature suffix -> sign name (e.g. 'I' -> 'isign', 'U' -> 'usign')."""
    out: dict[str, str] = {}
    for cp, suffix in tables.vsign_lig.items():
        alone = tables.sign_alone.get(cp)
        if alone:
            out[suffix] = alone
    for cp, (low, capv) in tables.vsign_below.items():
        alone = tables.sign_alone.get(cp)
        if alone:
            out[capv] = alone
            out[low] = alone
    return out


def parse(glyph_name: str, tables: ScriptTables, namespace: str) -> ParsedName | None:
    stem = _strip_ns(glyph_name, namespace)
    if stem is None:
        return None

    # Variant suffixes (.alt1, .low, ._c ...) — describe against the base.
    if "." in stem:
        base, _, variant = stem.partition(".")
        inner = parse(f"{base}-{namespace}", tables, namespace)
        desc = f"variant .{variant} of {base}"
        if inner:
            desc += f" ({inner.description})"
        return ParsedName("alt", desc)

    if stem.endswith("_repha"):
        core = stem[: -len("_repha")]
        return ParsedName("repha-lig",
                          f"repha ligature on '{core}' — formed in abvs from "
                          f"'{core} + repha' after the shaper repositions the reph")

    if stem.startswith("yasign_"):
        rest = stem[len("yasign_"):]
        return ParsedName("carrier-lig",
                          f"yansaya carrying '{rest}' — formed after vatu makes "
                          f"yasign, by ligating the following sign(s)")

    if stem.endswith("_virama"):
        core = stem[: -len("_virama")]
        return ParsedName("carrier-lig", f"'{core}' with trailing virama")

    consonant_stems = set(tables.consonants.values())

    if stem.endswith("Ra") and stem[:-2] and not stem[:-2][-1].isupper():
        return ParsedName("rakar", f"rakaransaya form of '{stem[:-2]}a' — "
                                   f"formed in blws from base + rasign")
    if stem.endswith("ya") and stem[:-2] in consonant_stems:
        return ParsedName("yansa", f"yansaya conjunct of '{stem[:-2]}a'")

    vsuffixes = _vowel_suffixes(tables)
    for suffix in sorted(vsuffixes, key=len, reverse=True):
        if stem.endswith(suffix) and stem[: -len(suffix)]:
            head = stem[: -len(suffix)]
            if head in consonant_stems or any(c.isupper() for c in head):
                return ParsedName(
                    "vowel-lig",
                    f"'{head}' + {vsuffixes[suffix]} vowel ligature")

    if stem in consonant_stems:
        return ParsedName("pure", f"pure (al-lakuna) form of '{stem}a' — "
                                  f"formed in akhn from '{stem}a + virama'")
    if stem.endswith("a") and stem[:-1] in consonant_stems:
        return ParsedName("base", f"base consonant '{stem}'")
    if any(c.isupper() for c in stem):
        return ParsedName("conjunct", f"conjunct cluster '{stem}'")
    return None

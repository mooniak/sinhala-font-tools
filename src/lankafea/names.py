"""Glyph-name construction — the ONLY module allowed to build LankaGlyphset names.

Ported from ``src/generators/index.ts`` (forward naming) and the cluster builder
in ``tools/glyphname-unicode-converter/lankaglyphset-map.js`` (``_clusterName``).
All naming rules live here so a change to the standard touches one file.
"""

from __future__ import annotations

from .scripts import ScriptTables

ZWJ = 0x200D

# Glyphs that never carry the "-<ns>" namespace suffix (shared across scripts).
NO_NAMESPACE = {ZWJ: "zerowidthjoiner"}


def drop_a(stem: str) -> str:
    """Drop a single trailing inherent 'a' (ka -> k)."""
    return stem[:-1] if stem.endswith("a") else stem


def cap(stem: str) -> str:
    return stem[:1].upper() + stem[1:] if stem else stem


def base_a(tables: ScriptTables, cp: int) -> str:
    """Consonant codepoint -> base name with inherent vowel (0x0D9A -> 'ka')."""
    return tables.consonants[cp] + "a"


def is_consonant(tables: ScriptTables, cp: int) -> bool:
    return cp in tables.consonants


def with_ns(stem: str, namespace: str) -> str:
    """Apply the namespace suffix (ka -> ka-sinh)."""
    return f"{stem}-{namespace}"


def glyph_for_codepoint(tables: ScriptTables, cp: int, namespace: str) -> str | None:
    """Nominal glyph name a single codepoint maps to after cmap.

    This is the LHS unit of a GSUB rule: a consonant maps to its base glyph
    (with inherent 'a'), a vowel sign to its ``*sign`` glyph, virama/ZWJ to their
    own glyphs. Returns ``None`` for a codepoint with no known glyph role.
    """
    if cp == ZWJ:
        return NO_NAMESPACE[cp]
    if cp in tables.consonants:
        return with_ns(base_a(tables, cp), namespace)
    if cp in tables.independent_vowels:
        return with_ns(tables.independent_vowels[cp], namespace)
    if cp in tables.sign_alone:
        return with_ns(tables.sign_alone[cp], namespace)
    return None


def componentize(tables: ScriptTables, cps: list[int], namespace: str) -> list[str] | None:
    """Map a Unicode cluster sequence to its nominal glyph-name sequence.

    Returns ``None`` if any codepoint has no glyph role (the rule is then unbuildable).
    """
    out: list[str] = []
    for cp in cps:
        name = glyph_for_codepoint(tables, cp, namespace)
        if name is None:
            return None
        out.append(name)
    return out


def cluster_stem(
    tables: ScriptTables,
    cons_list: list[int],
    specials: list[str],
    vowel: int | None = None,
    repaya: bool = False,
    trailing_virama: bool = False,
) -> str:
    """Forward port of lankaglyphset-map.js ``_clusterName`` core assembly.

    ``cons_list`` is the stacked consonant codepoints; ``specials`` (len == n-1)
    marks each stacked consonant after the first as ``"R"`` (rakaransaya),
    ``"y"`` (yansaya) or ``"conj"``. Returns the bare stem (no namespace).
    """
    core = base_a(tables, cons_list[0])
    for k in range(1, len(cons_list)):
        kind = specials[k - 1]
        if kind == "R":
            core = drop_a(core) + "Ra"
        elif kind == "y":
            core = drop_a(core) + "ya"
        else:
            core = drop_a(core) + cap(base_a(tables, cons_list[k]))

    da_shape = _is_da_shape(tables, cons_list)
    ra_base = len(cons_list) == 1 and cons_list[0] == tables.ra
    below_da = False

    if vowel is not None and vowel in tables.vsign_lig:
        stem = drop_a(core) + tables.vsign_lig[vowel]
    elif vowel is not None and vowel in tables.vsign_below:
        low, capv = tables.vsign_below[vowel]
        if da_shape:
            stem = drop_a(core) + low
            below_da = True
        else:  # ra ligature or spacing-vowel ligature
            stem = drop_a(core) + capv
    else:
        stem = drop_a(core) if trailing_virama else core

    if vowel is not None and trailing_virama:
        stem += "_virama"
    if below_da:
        stem += "._c"
    if repaya:
        stem += "_repha"
    return stem


def _is_da_shape(tables: ScriptTables, cons_list: list[int]) -> bool:
    if cons_list[0] in tables.da_shape_first:
        return True
    # nDa conjunct: n + da (Sinhala)
    if len(cons_list) >= 2 and cons_list[0] == 0x0DB1 and cons_list[1] == 0x0DAF:
        return True
    return False

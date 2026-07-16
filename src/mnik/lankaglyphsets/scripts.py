"""Per-script codepoint tables and the ScriptProfile that isolates all
Sinhala/Tamil divergence.

The Sinhala tables mirror ``tools/glyphname-unicode-converter/lankaglyphset-map.js``
and ``tools/font-coverage/font_coverage.py`` (the repo's existing sources of truth);
the Tamil tables follow ``glyphsets/tamil.yaml``. Keeping them here — rather than
re-deriving from the YAML — means the naming logic in :mod:`lankafea.names` has one
authoritative codepoint→role mapping to consult.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

_HERE = Path(__file__).resolve()
# YAMLs bundled inside the package, so the library is self-contained when installed
# out of this repository.
_BUNDLED_GLYPHSETS = _HERE.parent / "data" / "glyphsets"
# Fallback: the repo's canonical glyphsets/ (when running from a source checkout).
_REPO_GLYPHSETS = _HERE.parents[5] / "glyphsets"


def glyphsets_dir() -> Path:
    """Resolve the glyphsets directory.

    Priority: ``MNIK_GLYPHSETS_DIR`` (or legacy ``LANKAFEA_GLYPHSETS_DIR``) env override -> bundled package data ->
    the repo's ``glyphsets/`` (source-checkout fallback). Bundling means an
    installed wheel needs no repository files.
    """
    env = os.environ.get("MNIK_GLYPHSETS_DIR") or os.environ.get("LANKAFEA_GLYPHSETS_DIR")
    if env:
        return Path(env)
    if _BUNDLED_GLYPHSETS.is_dir():
        return _BUNDLED_GLYPHSETS
    return _REPO_GLYPHSETS

# Shared control characters.
AL = 0x0DCA          # placeholder; per-script virama overrides below
ZWJ = 0x200D


@dataclass(frozen=True)
class ScriptTables:
    """Codepoint → role tables for one script."""

    virama: int
    ra: int
    ya: int | None
    consonants: dict[int, str]           # cp -> virama-form stem (name without inherent 'a')
    independent_vowels: dict[int, str]   # cp -> name
    vsign_lig: dict[int, str]            # above/below signs that ligate for every C -> capital suffix
    vsign_below: dict[int, tuple[str, str]]  # spacing/below signs -> (lowercase, Capital)
    sign_alone: dict[int, str]           # cp -> standalone sign glyph name
    da_shape_first: frozenset[int] = frozenset()  # leading consonants taking ._c below-base form


# --------------------------------------------------------------------------- #
# Sinhala
# --------------------------------------------------------------------------- #

SINHALA = ScriptTables(
    virama=0x0DCA,
    ra=0x0DBB,
    ya=0x0DBA,
    consonants={
        0x0D9A: "k", 0x0D9B: "kh", 0x0D9C: "g", 0x0D9D: "gh", 0x0D9E: "ng",
        0x0D9F: "nng", 0x0DA0: "c", 0x0DA1: "ch", 0x0DA2: "j", 0x0DA3: "jh",
        0x0DA4: "ny", 0x0DA5: "jny", 0x0DA6: "nyj",
        0x0DA7: "tt", 0x0DA8: "tth", 0x0DA9: "dd", 0x0DAA: "ddh", 0x0DAB: "nn",
        0x0DAC: "nndd",
        0x0DAD: "t", 0x0DAE: "th", 0x0DAF: "d", 0x0DB0: "dh", 0x0DB1: "n",
        0x0DB3: "nd",
        0x0DB4: "p", 0x0DB5: "ph", 0x0DB6: "b", 0x0DB7: "bh", 0x0DB8: "m",
        0x0DB9: "mb",
        0x0DBA: "y", 0x0DBB: "r", 0x0DBD: "l", 0x0DC0: "v",
        0x0DC1: "sh", 0x0DC2: "ss", 0x0DC3: "s", 0x0DC4: "h", 0x0DC5: "ll",
        0x0DC6: "f",
    },
    independent_vowels={
        0x0D85: "a", 0x0D86: "aa", 0x0D87: "ae", 0x0D88: "aae",
        0x0D89: "i", 0x0D8A: "ii", 0x0D8B: "u", 0x0D8C: "uu",
        0x0D8D: "vocalicr", 0x0D8E: "vocalicrr", 0x0D8F: "vocalicl", 0x0D90: "vocalicll",
        0x0D91: "e", 0x0D92: "ee", 0x0D93: "ai", 0x0D94: "o", 0x0D95: "oo", 0x0D96: "au",
    },
    vsign_lig={0x0DD2: "I", 0x0DD3: "Ii", 0x0DD4: "U", 0x0DD6: "Uu"},
    vsign_below={
        0x0DCF: ("aa", "Aa"), 0x0DD0: ("ae", "Ae"), 0x0DD1: ("aae", "Aae"),
        0x0DD8: ("vocalicr", "Vocalicr"), 0x0DF2: ("vocalicrr", "Vocalicrr"),
        0x0DDF: ("vocalicl", "Vocalicl"), 0x0DF3: ("vocalicll", "Vocalicll"),
        0x0DD9: ("e", "E"), 0x0DDA: ("ee", "Ee"), 0x0DDB: ("ai", "Ai"),
        0x0DDC: ("o", "O"), 0x0DDD: ("oo", "Oo"), 0x0DDE: ("au", "Au"),
    },
    sign_alone={
        0x0DCF: "aasign", 0x0DD0: "aesign", 0x0DD1: "aaesign",
        0x0DD2: "isign", 0x0DD3: "iisign", 0x0DD4: "usign", 0x0DD6: "uusign",
        0x0DD8: "vocalicrsign", 0x0DF2: "vocalicrrsign",
        0x0DDF: "vocaliclsign", 0x0DF3: "vocalicllsign",
        0x0DD9: "esign", 0x0DDA: "eesign", 0x0DDB: "aisign",
        0x0DDC: "osign", 0x0DDD: "oosign", 0x0DDE: "ausign",
        0x0DCA: "virama", 0x0D82: "anusvaraya", 0x0D83: "visargaya", 0x0DF4: "kunddaliya",
    },
    # da, nya, jnya, nda take the below-base ._c form with a spacing vowel.
    da_shape_first=frozenset({0x0DAF, 0x0DA4, 0x0DA5, 0x0DB3}),
)


# --------------------------------------------------------------------------- #
# Tamil  (U+0B80–U+0BFF; see glyphsets/tamil.yaml)
# --------------------------------------------------------------------------- #

TAMIL = ScriptTables(
    virama=0x0BCD,
    ra=0x0BB0,
    ya=0x0BAF,
    consonants={
        0x0B95: "k", 0x0B99: "ng", 0x0B9A: "c", 0x0B9C: "j", 0x0B9E: "ny",
        0x0B9F: "tt", 0x0BA3: "nn", 0x0BA4: "t", 0x0BA8: "n", 0x0BA9: "nna2",
        0x0BAA: "p", 0x0BAE: "m", 0x0BAF: "y", 0x0BB0: "r", 0x0BB1: "rr",
        0x0BB2: "l", 0x0BB3: "ll", 0x0BB4: "zh", 0x0BB5: "v",
        0x0BB6: "sh", 0x0BB7: "ss", 0x0BB8: "s", 0x0BB9: "h",
    },
    independent_vowels={
        0x0B85: "a", 0x0B86: "aa", 0x0B87: "i", 0x0B88: "ii", 0x0B89: "u", 0x0B8A: "uu",
        0x0B8E: "e", 0x0B8F: "ee", 0x0B90: "ai", 0x0B92: "o", 0x0B93: "oo", 0x0B94: "au",
    },
    vsign_lig={0x0BBF: "I", 0x0BC0: "Ii", 0x0BC1: "U", 0x0BC2: "Uu"},
    vsign_below={
        0x0BBE: ("aa", "Aa"), 0x0BC6: ("e", "E"), 0x0BC7: ("ee", "Ee"), 0x0BC8: ("ai", "Ai"),
        0x0BCA: ("o", "O"), 0x0BCB: ("oo", "Oo"), 0x0BCC: ("au", "Au"),
    },
    sign_alone={
        0x0BBE: "aasign", 0x0BBF: "isign", 0x0BC0: "iisign", 0x0BC1: "usign", 0x0BC2: "uusign",
        0x0BC6: "esign", 0x0BC7: "eesign", 0x0BC8: "aisign",
        0x0BCA: "osign", 0x0BCB: "oosign", 0x0BCC: "ausign", 0x0BD7: "aulengthmark",
        0x0BCD: "virama", 0x0B82: "anusvaraya", 0x0B83: "visargaya",
    },
    da_shape_first=frozenset(),
)


@dataclass(frozen=True)
class ScriptProfile:
    """Everything the pipeline needs to know about one script."""

    key: str                       # "sinhala" | "tamil"
    namespace: str                 # "sinh" | "taml"
    tables: ScriptTables
    yaml_files: tuple[str, ...]    # ordered; Sinhala is cumulative, Tamil single
    language_systems: dict[str, list[str]]
    # Which OT feature each above/below/post vowel-sign ligature is routed to.
    # Keyed by the standalone sign name.
    sign_feature: dict[str, str] = field(default_factory=dict)
    touch_strategy: str = "gpos"   # "gpos" | "ligature"
    has_reference: bool = False
    # Shaping specifics (Sinhala forms reph/rakar/yansa & joins conjuncts with ZWJ;
    # Tamil does none of that and joins conjuncts with a bare virama).
    conjunct_zwj: bool = True
    form_reph: bool = True
    form_rakar: bool = True
    form_yansa: bool = True
    form_touch: bool = True

    def yaml_paths(self) -> list[Path]:
        base = glyphsets_dir()
        return [base / name for name in self.yaml_files]


# Vowel-sign → feature routing shared shape (matches the Noto reference for Sinhala:
# i/ii above -> abvs, u/uu below -> blws, spacing -> psts).
_SIGN_FEATURE = {
    "isign": "abvs", "iisign": "abvs",
    "usign": "blws", "uusign": "blws",
    "aasign": "psts", "aesign": "psts", "aaesign": "psts",
    "vocalicrsign": "blws", "vocalicrrsign": "blws",
    "esign": "pres", "eesign": "pres", "aisign": "pres",
    "osign": "psts", "oosign": "psts", "ausign": "psts",
}

SINHALA_LEVELS = (
    "sinhala-0-kernel.yaml",
    "sinhala-1-core.yaml",
    "sinhala-2-plus.yaml",
    "sinhala-3-pro.yaml",
)


def sinhala_profile(level: int = 3) -> ScriptProfile:
    level = max(0, min(3, level))
    return ScriptProfile(
        key="sinhala",
        namespace="sinh",
        tables=SINHALA,
        yaml_files=SINHALA_LEVELS[: level + 1],
        language_systems={"sinh": ["dflt"]},
        sign_feature=dict(_SIGN_FEATURE),
        touch_strategy="gpos",
        has_reference=True,
    )


def tamil_profile() -> ScriptProfile:
    return ScriptProfile(
        key="tamil",
        namespace="taml",
        tables=TAMIL,
        yaml_files=("tamil.yaml",),
        # Cover both the legacy and OpenType-2 Tamil script tags.
        language_systems={"taml": ["dflt"], "tml2": ["dflt"]},
        sign_feature=dict(_SIGN_FEATURE),
        touch_strategy="ligature",
        has_reference=False,
        conjunct_zwj=False,
        form_reph=False,
        form_rakar=False,
        form_yansa=False,
        form_touch=False,
    )


def get_profile(script: str, level: int = 3) -> ScriptProfile:
    s = script.strip().lower()
    if s in ("sinhala", "sinh", "si"):
        return sinhala_profile(level)
    if s in ("tamil", "taml", "ta"):
        return tamil_profile()
    raise ValueError(f"unknown script: {script!r} (expected 'sinhala' or 'tamil')")

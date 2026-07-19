"""Loads the canonical Sinhala letter inventory vendored at
tools/_generated/lanka-glyph-data.js (source of truth: lanka-glyphsets) and
classifies it into the categories the composite grammar needs.

The generated file only maps latin-name -> Sinhala character; it carries no
letter-category tags, so the classification sets below encode that by hand.
If lanka-glyphsets ever adds/removes a letter, the CONSONANTS assertion below
will fail loudly rather than silently miscategorizing the new entry.
"""
import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
LANKA_GLYPH_DATA_JS = REPO_ROOT / "tools" / "_generated" / "lanka-glyph-data.js"

INDEPENDENT_VOWELS = {
    "a", "aa", "ae", "aae", "i", "ii", "u", "uu", "e", "ee", "ai", "o", "oo", "au",
    "vocalicr", "vocalicrr", "vocalicl", "vocalicll",
}
DEPENDENT_SIGNS = {
    "aasign", "aesign", "aaesign", "isign", "iisign", "usign", "uusign",
    "vocalicrsign", "esign", "eesign", "osign", "oosign", "aisign", "ausign",
    "vocalicrrsign", "vocalicllsign", "vocaliclsign",
}
OTHER_MARKS = {"virama", "anusvaraya", "visargaya"}
IGNORED = {"zerowidthjoiner"}

EXPECTED_CONSONANT_COUNT = 40


def load_letters():
    text = LANKA_GLYPH_DATA_JS.read_text(encoding="utf-8")
    match = re.search(r"var DATA = (\{.*?\});\n  if \(typeof module", text, re.S)
    if not match:
        raise ValueError(f"could not locate DATA object in {LANKA_GLYPH_DATA_JS}")
    data = json.loads(match.group(1))
    return data["letters"]


def load_classification():
    letters = load_letters()
    names = set(letters)
    consonants = sorted(names - INDEPENDENT_VOWELS - DEPENDENT_SIGNS - OTHER_MARKS - IGNORED)
    if len(consonants) != EXPECTED_CONSONANT_COUNT:
        raise ValueError(
            f"expected {EXPECTED_CONSONANT_COUNT} consonants after classification, got "
            f"{len(consonants)}: {consonants}\nlanka-glyph-data.js may have changed — "
            "update the classification sets in composite_map/lanka_data.py"
        )
    stems = [c[:-1] for c in consonants]
    if len(set(stems)) != len(stems):
        dupes = {s for s in stems if stems.count(s) > 1}
        raise ValueError(f"al-form stem collision among consonants: {dupes}")
    return {
        "letters": letters,
        "consonants": consonants,
        "independent_vowels": sorted(INDEPENDENT_VOWELS),
        "dependent_signs": sorted(DEPENDENT_SIGNS),
        "other_marks": sorted(OTHER_MARKS),
    }

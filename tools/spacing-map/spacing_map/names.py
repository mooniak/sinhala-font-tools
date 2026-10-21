"""Resolves scheme entries (Sinhala characters and fused-form sequences) to
glyph names in a target font.

Single characters resolve by UNICODE straight from the font — naming-agnostic
and exact. Fused forms (ටි, කු, ක්, ද්‍රි …) carry no codepoint, so they must be
resolved by NAME, and names are a per-vendor convention. The convention encoded
here is the lanka-glyphsets one (as used by AbhayaLibre and by
tools/composite-map's `grammar.py`):

    base glyph      ka-sinh      stem + inherent 'a'
    al-form         k-sinh       stem alone
    with a sign     kI-sinh      stem + sign suffix (I Ii U Uu Ae Aae)
    rakar cluster   kRa-sinh     stem + 'R' + inherent 'a'
    rakar + sign    kRI-sinh     stem + 'R' + sign suffix
    conjunct        nDa-sinh     stems joined, later ones capitalised

Stems are derived from the FONT's own name for each letter's codepoint where
possible (so a font naming ඦ `nyja-sinh` yields ඦි -> `nyjI-sinh`), falling back
to the vendored lanka-glyphsets data. An unresolved form usually means the font
simply lacks that fused glyph — Noto Sans Sinhala shares this naming convention
but fuses far fewer combinations, positioning ි with contextual `isign-sinh.altN`
alternates instead. Either way the failure is REPORTED, never silently skipped;
`--names <yaml>` maps forms to glyph names by hand for other conventions.
"""
import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
LANKA_GLYPH_DATA_JS = REPO_ROOT / "tools" / "_generated" / "lanka-glyph-data.js"

SUFFIX = "-sinh"
ZWJ = "‍"
VIRAMA = "්"
RAKAR = "ර"   # ර — as a post-virama cluster member this is the rakar sign

# sign char -> name-stem suffix / ligature-component name
SIGN_SUFFIX = {"ි": "I", "ී": "Ii", "ු": "U", "ූ": "Uu",
               "ැ": "Ae", "ෑ": "Aae"}
SIGN_NAME = {"ි": "isign", "ී": "iisign", "ු": "usign",
             "ූ": "uusign", "ැ": "aesign", "ෑ": "aaesign"}


def load_letters():
    text = LANKA_GLYPH_DATA_JS.read_text(encoding="utf-8")
    m = re.search(r"var DATA = (\{.*?\});\n  if \(typeof module", text, re.S)
    if not m:
        raise ValueError(f"could not locate DATA object in {LANKA_GLYPH_DATA_JS}")
    return json.loads(m.group(1))["letters"]


def lgs_char_to_name():
    """Sinhala char -> lanka-glyphsets base name (ක -> 'ka')."""
    out = {}
    for name, ch in load_letters().items():
        out.setdefault(ch, name)
    return out


def strip_suffix(name):
    return name[: -len(SUFFIX)] if name.endswith(SUFFIX) else name


def stem_of(base_name):
    """Base name -> stem: the inherent 'a' dropped ('ka' -> 'k', 'nyja' -> 'nyj')."""
    return base_name[:-1] if base_name.endswith("a") else base_name


def _cap(s):
    return s[:1].upper() + s[1:]


def split_form(form):
    """A fused form -> (cluster chars, sign char or None).

    'ටි'  -> (['ට'], 'ි')            'ක්' -> (['ක'], None)   al-form
    'ද්‍රි' -> (['ද', 'ර'], 'ි')   'න්‍ද්‍රී' -> (['න','ද','ර'], 'ී')
    """
    chars = [c for c in form if c != ZWJ]
    sign = chars.pop() if chars and chars[-1] in SIGN_SUFFIX else None
    cluster = [c for c in chars if c != VIRAMA]
    return cluster, sign


def name_candidates(form, stems):
    """Glyph-name candidates for a fused form, best first. Empty when any
    cluster member has no known stem."""
    cluster, sign = split_form(form)
    if not cluster or any(c not in stems for c in cluster):
        return []

    rakar = len(cluster) > 1 and cluster[-1] == RAKAR
    letters = cluster[:-1] if rakar else cluster
    core = stems[letters[0]] + "".join(_cap(stems[c]) for c in letters[1:])
    if rakar:
        core += "R"

    if sign:
        tail = SIGN_SUFFIX[sign]
    elif rakar:
        tail = "a"          # ද්‍ර standing alone keeps the inherent vowel: dRa-sinh
    else:
        tail = ""           # al-form: k-sinh
    cands = [f"{core}{tail}{SUFFIX}"]

    # ligature-style fallback: ka_rasign_isign-sinh
    parts = [stems[c] + "a" for c in letters]
    if rakar:
        parts.append("rasign")
    parts.append(SIGN_NAME[sign] if sign else "virama")
    cands.append("_".join(parts) + SUFFIX)
    return cands


class Resolver:
    """Maps scheme entries (chars and fused forms) to names in `font_names`."""

    HOWS = ("override", "unicode", "name", "missing", "unknown")

    def __init__(self, font_names, unicode_to_name, overrides=None, lgs_names=None):
        """`lgs_names` (char -> base name) replaces reading the vendored
        lanka-glyphsets file — the Glyphs plugin passes its bundled copy."""
        self.names = set(font_names)
        self.by_unicode = dict(unicode_to_name)
        self.overrides = dict(overrides or {})
        self.stems = self._build_stems(lgs_names)

    def _build_stems(self, lgs_names=None):
        """char -> stem, font's own naming preferred over vendored LGS data."""
        if lgs_names is None:
            lgs_names = lgs_char_to_name()
        stems = {ch: stem_of(n) for ch, n in lgs_names.items()}
        for cp, gname in self.by_unicode.items():
            stems[chr(cp)] = stem_of(strip_suffix(gname))
        return stems

    def resolve(self, entry):
        """-> (glyph_name, how): 'override' | 'unicode' | 'name' (derived, found)
        | 'missing' (derived, font lacks it) | 'unknown' (nothing derivable)."""
        if entry in self.overrides:
            name = self.overrides[entry]
            return name, ("override" if name in self.names else "missing")
        if len(entry) == 1:
            name = self.by_unicode.get(ord(entry))
            if name:
                return name, "unicode"
            stem = self.stems.get(entry)
            if stem is None:
                return None, "unknown"
            cand = f"{stem}a{SUFFIX}"
            return cand, ("name" if cand in self.names else "missing")
        cands = name_candidates(entry, self.stems)
        for cand in cands:
            if cand in self.names:
                return cand, "name"
        return (cands[0] if cands else None), ("missing" if cands else "unknown")

"""Acceptance for the Tamil model: does it shape like the hand-written features?

For a real font (Ralex, Yaldevi, Abhaya Libre) this

  1. reads the font's Glyphs source for its glyph inventory,
  2. generates Tamil features for that inventory, through an alias table that says which
     of the font's glyphs is which of the standard's names (the font is not migrated yet),
  3. compiles them into a synthetic font with the same glyph names and cmap, and
  4. shapes the full consonant x sign grid plus the Tamil test texts with BOTH that font
     and the real, hand-written build, comparing glyph names (the built font drops hyphens
     and names encoded glyphs uniXXXX; both are mapped back to the source's names).

Every difference must either match or be explained (see EXPLAINED in the test).
Run it directly for a report:   python tests/acceptance_tamil.py [ralex|yaldevi|abhaya]
"""

from __future__ import annotations

import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))

from lankafea.aliases import load_alias_file
from lankafea.api import build_fea
from lankafea.glyphsource import inventory_from_glyphs
from lankafea.inventory import FontInventory
from lankafea.scripts import get_profile
from lankafea.verify import shape_names
from lankafea.yamlloader import load_specs

# <workspace>/font-repos and <workspace>/sinhala-font-tools/test-texts
WORKSPACE = HERE.parents[3]
FONT_REPOS = WORKSPACE / "font-repos"
TEXTS = WORKSPACE / "sinhala-font-tools" / "test-texts"
ALIASES = HERE / "fixtures" / "tamil-aliases"
TEXT_FILES = ["tamil-alphabet", "tamil-kern-pairs", "tamil-numerals",
              "tamil-pangram", "tamil-prose"]


@dataclass
class FontCase:
    key: str
    source: Path
    built: Path
    aliases: Path
    # The stylistic sets the hand-written font carries its traditional forms in.
    traditional: tuple[str, ...]


CASES = {
    "ralex": FontCase(
        "ralex", FONT_REPOS / "ralex-font/sources/Ralex.glyphspackage",
        FONT_REPOS / "ralex-font/fonts/ttf/Ralex-Regular.ttf",
        ALIASES / "ralex.yaml", ("ss02", "ss04")),
    "yaldevi": FontCase(
        "yaldevi", FONT_REPOS / "yaldevi-font/sources/Yaldevi.glyphspackage",
        FONT_REPOS / "yaldevi-font/fonts/ttf/Yaldevi-Regular.ttf",
        ALIASES / "yaldevi.yaml", ("ss01", "ss02", "ss03", "ss04")),
    "abhaya": FontCase(
        "abhaya", FONT_REPOS / "abhaya-libre-font/sources/AbhayaLibre.glyphspackage",
        FONT_REPOS / "abhaya-libre-font/fonts/variable/AbhayaLibre[wght].ttf",
        ALIASES / "abhaya.yaml", ("ss09",)),
}


def source_is_migrated(case: FontCase) -> bool:
    """True once the font's source has been renamed to the standard (isign-taml.ka exists)."""
    return "isign-taml.ka" in inventory_from_glyphs(case.source).glyphs


def available(case: FontCase) -> bool:
    return case.source.exists() and case.built.exists() and case.aliases.exists()


# ---- corpus ------------------------------------------------------------------- #

# The 13 columns of the grid: the inherent vowel, the pulli, and the 11 vowel signs.
GRID_COLUMNS = [(name, chr(cp) if cp else "") for name, cp in (
    (None, 0), ("virama", 0x0BCD), ("aasign", 0x0BBE), ("isign", 0x0BBF),
    ("iisign", 0x0BC0), ("usign", 0x0BC1), ("uusign", 0x0BC2), ("esign", 0x0BC6),
    ("eesign", 0x0BC7), ("aisign", 0x0BC8), ("osign", 0x0BCA), ("oosign", 0x0BCB),
    ("ausign", 0x0BCC))]


def grid_strings() -> list[tuple[str, str]]:
    """The 24 x 13 consonant x sign grid, plus both spellings of ஸ்ரீ."""
    specs = load_specs(get_profile("tamil", 2))
    rows = [(c.name, chr(c.unicode)) for c in specs.consonants()]
    rows.append(("kSsa", chr(0x0B95) + chr(0x0BCD) + chr(0x0BB7)))
    out = []
    for name, base in rows:
        for sign, char in GRID_COLUMNS:
            out.append((f"{name}+{sign or 'inherent'}", base + char))
    out.append(("shree (sha)", "".join(chr(c) for c in (0x0BB6, 0x0BCD, 0x0BB0, 0x0BC0))))
    out.append(("shree (sa)", "".join(chr(c) for c in (0x0BB8, 0x0BCD, 0x0BB0, 0x0BC0))))
    return out


def text_tokens() -> list[tuple[str, str]]:
    """Every distinct whitespace-separated Tamil token in the test texts."""
    seen: dict[str, str] = {}
    for stem in TEXT_FILES:
        path = TEXTS / f"{stem}.md"
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        if text.startswith("---"):                    # skip the YAML front matter
            text = text.split("---", 2)[2]
        for tok in re.split(r"[\s,;:.!?()\[\]\"'“”‘’/\\|]+", text):
            if tok and any("஀" <= ch <= "௿" for ch in tok):
                seen.setdefault(tok, stem)
    return [(stem, tok) for tok, stem in seen.items()]


# ---- the synthetic font ------------------------------------------------------- #

def synthetic_font(inv: FontInventory, fea: str, out: Path) -> Path:
    """Empty-outline font with the source's glyphs and cmap, plus the generated GSUB."""
    from fontTools.feaLib.builder import addOpenTypeFeatures
    from fontTools.fontBuilder import FontBuilder
    from fontTools.ttLib.tables._g_l_y_f import Glyph

    order = [".notdef"] + sorted(n for n in inv.glyphs if n != ".notdef")
    cmap = {cp: n for cp, n in inv.cmap_names.items() if n in set(order)}
    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap(cmap)
    fb.setupGlyf({n: Glyph() for n in order})
    fb.setupHorizontalMetrics({n: (600, 0) for n in order})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({"familyName": "LankaAcceptance", "styleName": "Regular"})
    fb.setupOS2()
    fb.setupPost()
    fea_path = out.with_suffix(".fea")
    fea_path.write_text(fea, encoding="utf-8")
    addOpenTypeFeatures(fb.font, str(fea_path))
    fb.font.save(str(out))
    return out


def canonicaliser(inv: FontInventory):
    """Map a built font's glyph names back to the source's: the build drops hyphens and
    names encoded glyphs uniXXXX."""
    stripped: dict[str, str] = {}
    for n in sorted(inv.glyphs):
        stripped.setdefault(n.replace("-", ""), n)

    def canon(name: str) -> str:
        m = re.fullmatch(r"uni([0-9A-Fa-f]{4,6})", name)
        if m:
            return inv.cmap_names.get(int(m.group(1), 16), name)
        return stripped.get(name, name)
    return canon


# ---- comparison --------------------------------------------------------------- #

@dataclass
class Difference:
    corpus: str
    label: str
    text: str
    hand: list[str]
    generated: list[str]


def _nested_lookups(obj, found: set[int]) -> None:
    """Collect the lookups a contextual rule calls (SubstLookupRecord), at any depth."""
    if isinstance(obj, (list, tuple)):
        for item in obj:
            _nested_lookups(item, found)
    elif hasattr(obj, "__dict__"):
        if obj.__class__.__name__ == "SubstLookupRecord":
            found.add(obj.LookupListIndex)
        else:
            for value in vars(obj).values():
                _nested_lookups(value, found)


def gsub_outputs(font_path: Path) -> set[str]:
    """Every glyph the font's GSUB can output FOR TAMIL: through the lookups its
    taml / tml2 script records reach (directly, or called by a contextual rule).
    A lookup that exists but is registered under another script — Yaldevi's old akhn —
    does not count: it can never run on Tamil text."""
    from fontTools.ttLib import TTFont
    tt = TTFont(str(font_path))
    gsub = tt["GSUB"].table
    lookups = gsub.LookupList.Lookup

    todo: set[int] = set()
    for sr in gsub.ScriptList.ScriptRecord:
        if sr.ScriptTag not in ("taml", "tml2"):
            continue
        langs = [sr.Script.DefaultLangSys] if sr.Script.DefaultLangSys else []
        langs += [l.LangSys for l in sr.Script.LangSysRecord]
        for ls in langs:
            for fi in ls.FeatureIndex:
                todo.update(gsub.FeatureList.FeatureRecord[fi].Feature.LookupListIndex)
    reached: set[int] = set()
    while todo:
        i = todo.pop()
        if i in reached:
            continue
        reached.add(i)
        called: set[int] = set()
        for sub in lookups[i].SubTable:
            _nested_lookups(sub.ExtSubTable if lookups[i].LookupType == 7 else sub, called)
        todo.update(called - reached)

    out: set[str] = set()
    for i in reached:
        lookup = lookups[i]
        for sub in lookup.SubTable:
            if lookup.LookupType == 7:
                sub = sub.ExtSubTable
            kind = sub.__class__.__name__
            if kind == "LigatureSubst":
                for ligs in sub.ligatures.values():
                    out.update(lig.LigGlyph for lig in ligs)
            elif kind == "SingleSubst":
                out.update(sub.mapping.values())
            elif kind == "MultipleSubst":
                for seq in sub.mapping.values():
                    out.update(seq)
            elif kind == "AlternateSubst":
                for alts in sub.alternates.values():
                    out.update(alts)
    tt.close()
    return out


def hand_tamil_features(font_path: Path) -> set[str]:
    """The feature tags the built font registers for the Tamil scripts."""
    from fontTools.ttLib import TTFont
    tt = TTFont(str(font_path))
    gsub = tt["GSUB"].table
    tags: set[str] = set()
    for sr in gsub.ScriptList.ScriptRecord:
        if sr.ScriptTag in ("taml", "tml2"):
            langs = [sr.Script.DefaultLangSys] if sr.Script.DefaultLangSys else []
            langs += [l.LangSys for l in sr.Script.LangSysRecord]
            for ls in langs:
                tags.update(gsub.FeatureList.FeatureRecord[i].FeatureTag
                            for i in ls.FeatureIndex)
    tt.close()
    return tags


@dataclass
class Result:
    case: FontCase
    total: int = 0
    same: int = 0
    differences: list[Difference] = field(default_factory=list)
    traditional_total: int = 0
    traditional_same: int = 0
    traditional_differences: list[Difference] = field(default_factory=list)
    kept_rules: int = 0
    blockers: int = 0
    unmet_forms: list[str] = field(default_factory=list)
    # Glyphs the hand-written GSUB can never output. A difference that involves only
    # them is "an existing glyph made reachable", not a regression.
    hand_unreachable: set[str] = field(default_factory=set)
    # False when the built font registers none of the sets its traditional forms
    # belong in (a stale build), so there is nothing to compare ss09 against.
    traditional_comparable: bool = True

    def explained(self, d: Difference) -> bool:
        """The generated shaping differs from the hand-written only by glyphs the
        hand-written GSUB cannot output at all: a glyph the font has, drawn for exactly
        this, that its own features never reach (or, in a stale build, never could).
        That is a fix rather than a regression, though whether the glyph is wanted is
        the designer's call."""
        only_generated = set(d.generated) - set(d.hand)
        return bool(only_generated) and only_generated <= self.hand_unreachable

    def unexplained(self, traditional: bool = False) -> list[Difference]:
        diffs = self.traditional_differences if traditional else self.differences
        return [d for d in diffs if not self.explained(d)]

    def reached(self, traditional: bool = False) -> Counter:
        """The glyphs the generated features reach that the hand-written never do."""
        diffs = self.traditional_differences if traditional else self.differences
        c: Counter = Counter()
        for d in diffs:
            if self.explained(d):
                c.update(set(d.generated) - set(d.hand))
        return c

    def pairs(self, traditional: bool = False) -> Counter:
        """(hand, generated) sequences, counted: the shape of each distinct difference."""
        diffs = self.traditional_differences if traditional else self.differences
        return Counter((tuple(d.hand), tuple(d.generated)) for d in diffs)


def run(key: str, workdir: Path) -> Result:
    case = CASES[key]
    inv = inventory_from_glyphs(case.source)
    aliases = load_alias_file(case.aliases)
    built = build_fea("tamil", inv, level=2, aliases=aliases,
                      adopt_legacy_names=True, validate=True)
    gen_font = synthetic_font(inv, built.fea, workdir / f"{key}-generated.ttf")
    canon = canonicaliser(inv)

    result = Result(case)
    reachable = {canon(n) for n in gsub_outputs(case.built)}
    result.hand_unreachable = {n for n in inv.glyphs if n not in reachable}
    result.traditional_comparable = bool(set(case.traditional) & hand_tamil_features(case.built))
    result.kept_rules = built.report.kept_rules
    result.blockers = len(built.report.blockers)
    result.unmet_forms = [f["form"] for f in built.report.forms_unmet]

    corpus = [("grid", label, text) for label, text in grid_strings()]
    corpus += [(stem, tok, tok) for stem, tok in text_tokens()]

    def shape_pair(text, hand_features, gen_features):
        hand = [canon(n) for n in shape_names(case.built, text, hand_features)]
        gen = shape_names(gen_font, text, gen_features)
        return hand, gen

    for corpus_name, label, text in corpus:
        hand, gen = shape_pair(text, None, None)
        result.total += 1
        if hand == gen:
            result.same += 1
        else:
            result.differences.append(Difference(corpus_name, label, text, hand, gen))
        # The traditional orthography: the generated ss09 against the font's own sets
        # (only when the built font really registers them).
        if not result.traditional_comparable:
            continue
        hand_t, gen_t = shape_pair(
            text, {tag: True for tag in case.traditional}, {"ss09": True})
        result.traditional_total += 1
        if hand_t == gen_t:
            result.traditional_same += 1
        else:
            result.traditional_differences.append(
                Difference(corpus_name, label, text, hand_t, gen_t))
    return result


def report(result: Result, limit: int = 12) -> str:
    c = result.case
    lines = [f"== {c.key} ==",
             f"generated: {result.kept_rules} rules kept, {result.blockers} blockers, "
             f"{len(result.unmet_forms)} unmet forms",
             f"default features: {result.same}/{result.total} identical, "
             f"{len(result.differences)} differ "
             f"({len(result.differences) - len(result.unexplained())} explained, "
             f"{len(result.unexplained())} not)"]
    if result.traditional_comparable:
        lines.append(f"traditional ({'+'.join(c.traditional)} vs ss09): "
                     f"{result.traditional_same}/{result.traditional_total} identical, "
                     f"{len(result.traditional_differences)} differ "
                     f"({len(result.unexplained(True))} unexplained)")
    else:
        lines.append(f"traditional: not compared — the built font registers none of "
                     f"{'+'.join(c.traditional)} (a stale build)")
    reached = result.reached() + result.reached(True)
    if reached:
        lines.append("glyphs the generated features reach that the hand-written never "
                     "do: " + ", ".join(sorted(reached)))
    if result.unmet_forms:
        lines.append("forms the standard requires that the font lacks: "
                     + ", ".join(result.unmet_forms))
    for title, traditional in (("default", False), ("traditional", True)):
        pairs = result.pairs(traditional)
        if not pairs:
            continue
        lines.append(f"\n-- distinct {title} differences ({len(pairs)}):")
        diffs = result.traditional_differences if traditional else result.differences
        example = {}
        for d in diffs:
            example.setdefault((tuple(d.hand), tuple(d.generated)), d)
        for (hand, gen), n in pairs.most_common(limit):
            d = example[(hand, gen)]
            lines.append(f"  x{n:<3} {d.label!r} ({d.corpus})")
            lines.append(f"       hand:      {' '.join(hand)}")
            lines.append(f"       generated: {' '.join(gen)}")
    return "\n".join(lines)


if __name__ == "__main__":
    import tempfile
    keys = sys.argv[1:] or list(CASES)
    with tempfile.TemporaryDirectory() as tmp:
        for k in keys:
            if not available(CASES[k]):
                print(f"== {k}: skipped (source, build or alias table missing)")
                continue
            print(report(run(k, Path(tmp))), "\n")

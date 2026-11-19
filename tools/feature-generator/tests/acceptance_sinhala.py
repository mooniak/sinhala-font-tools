"""Acceptance for the Sinhala model: does it shape like a font's hand-written features?

For a real font (Abhaya Libre first) this

  1. reads the Glyphs source for its glyph inventory and its hand-written features (or a
     frozen copy of them, see BASELINES below),
  2. generates Sinhala features for that inventory,
  3. compiles BOTH into the same synthetic font (the source's glyph names and cmap, empty
     outlines, every advance 600), so the two runs differ only in their features, and
  4. shapes a corpus with each and compares glyph names, then positions (GPOS `dist`).

The corpus is built from the standard: every consonant against every sign; yansaya,
rakar and repaya on every consonant, with signs; every conjunct and touching pair the
standard lists, with signs and under a repaya; the ZWJ spellings of the four prenasalised
letters; numerals; and every Sinhala token in sinhala-font-tools/test-texts. It is shaped
with the default features and again with each stylistic feature the hand-written
features register (ssNN, dlig).

Every difference is sorted into a category. "reach" means the generated features output
a glyph the hand-written ones never can (a glyph the font has that its own features never
form). "feature" means the hand-written features change the text under a stylistic feature
the generated ones don't have yet. The rest are matched against the known items in the
plan (lanka-glyphsets/docs/abhaya-feature-plan.md, sections 1.2 and 4), and whatever
matches nothing is "unexplained".

BASELINES: once the refactor removes a font's hand-written features from its source, the
baseline has to come from somewhere else. `--freeze` writes the hand-written features to
tests/fixtures/sinhala-baselines/<font>.fea, and a frozen file, when present, is used
instead of the source. Re-freeze after renaming glyphs in the source (the frozen file
uses the names it was frozen with).

Run it directly for a report:
    python tests/acceptance_sinhala.py [abhaya] [--freeze] [--json FILE] [--all]
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))

from lankafea.api import build_fea
from lankafea.glyphsource import inventory_from_glyphs
from lankafea.inventory import FontInventory
from lankafea.scripts import get_profile
from lankafea.yamlloader import load_specs

# <workspace>/font-repos and <workspace>/sinhala-font-tools/test-texts. The test texts are
# read from the main sinhala-font-tools checkout, or from this one if it has them.
WORKSPACE = HERE.parents[3]
FONT_REPOS = WORKSPACE / "font-repos"
TEXTS = next((p for p in (HERE.parents[2] / "test-texts",
                          WORKSPACE / "sinhala-font-tools" / "test-texts") if p.is_dir()),
             HERE.parents[2] / "test-texts")
BASELINES = HERE / "fixtures" / "sinhala-baselines"
TEXT_FILES = ["sinhala-alphabet", "sinhala-pangram", "prose", "conjuncts", "rakar",
              "signs-combinations", "shape-groups", "marks", "ot-features",
              "pali-and-sanskrit-words", "classical-texts", "numerals", "display-strings",
              "kern-pairs"]


@dataclass
class FontCase:
    key: str
    source: Path

    def config(self):
        """The font's own lankafea settings (sources/lankafea.yaml), as `lankafea generate` reads
        them: inject files, feature routing, dist, numerals, feature names."""
        from lankafea.fontconfig import find_config, load_font_config
        return load_font_config(find_config(self.source), "sinhala")


CASES = {
    "abhaya": FontCase(
        "abhaya", FONT_REPOS / "abhaya-libre-font/sources/AbhayaLibre.glyphspackage"),
}


def available(case: FontCase) -> bool:
    return case.source.exists()


# ---- corpus ------------------------------------------------------------------- #

ZWJ = "‍"
VIRAMA, RA, YA = "්", "ර", "ය"
REPAYA = RA + VIRAMA + ZWJ
YANSAYA = VIRAMA + ZWJ + YA
RAKAR = VIRAMA + ZWJ + RA

SIGNS = [(name, chr(cp)) for name, cp in (
    ("virama", 0x0DCA), ("aasign", 0x0DCF), ("aesign", 0x0DD0), ("aaesign", 0x0DD1),
    ("isign", 0x0DD2), ("iisign", 0x0DD3), ("usign", 0x0DD4), ("uusign", 0x0DD6),
    ("vocalicrsign", 0x0DD8), ("esign", 0x0DD9), ("eesign", 0x0DDA), ("aisign", 0x0DDB),
    ("osign", 0x0DDC), ("oosign", 0x0DDD), ("ausign", 0x0DDE), ("vocaliclsign", 0x0DDF),
    ("vocalicrrsign", 0x0DF2), ("vocalicllsign", 0x0DF3), ("anusvara", 0x0D82),
    ("visarga", 0x0D83), ("candrabindu", 0x0D81))]
# The signs that interact with a cluster (ligatures, below-base forms, split vowels).
CLUSTER_SIGNS = ["virama", "aasign", "aesign", "aaesign", "isign", "iisign", "usign",
                 "uusign", "vocalicrsign", "esign", "eesign", "osign", "oosign"]
SIGN_CHAR = dict(SIGNS)

# Prenasalised letters and the ZWJ conjunct spelling some fonts map to them.
PRENASALISED = [("mba", "ම", "බ"), ("nnga", "ඞ", "ග"),
                ("nndda", "ණ", "ඩ"), ("nyja", "ඤ", "ජ")]


def _with_signs(label: str, base: str, signs: list[str]) -> list[tuple[str, str]]:
    out = [(f"{label}+inherent", base)]
    out += [(f"{label}+{s}", base + SIGN_CHAR[s]) for s in signs]
    return out


def corpus_strings() -> list[tuple[str, str, str]]:
    """(section, label, text) for the standard-derived part of the corpus."""
    specs = load_specs(get_profile("sinhala", 3))
    cons = [(c.name, chr(c.unicode)) for c in specs.consonants()]
    char = dict(cons)
    out: list[tuple[str, str, str]] = []

    # 1. every consonant x every sign
    for name, ch in cons:
        for label, text in _with_signs(name, ch, [s for s, _ in SIGNS]):
            out.append(("grid", label, text))

    # 2. yansaya, rakar, repaya (and repaya + yansaya) on every consonant, with signs
    for name, ch in cons:
        for kind, text in (("yansaya", ch + YANSAYA), ("rakar", ch + RAKAR),
                           ("repaya", REPAYA + ch), ("repaya+yansaya", REPAYA + ch + YANSAYA)):
            for label, t in _with_signs(f"{name} {kind}", text, CLUSTER_SIGNS):
                out.append((kind, label, t))

    # 3. conjuncts and touching pairs the standard lists, with signs, and under a repaya
    for c in specs.consonants():
        first = chr(c.unicode)
        for kind, partners, joiner in (("conjunct", c.conjunct, VIRAMA + ZWJ),
                                       ("touching", c.touch, ZWJ + VIRAMA)):
            for p in partners or []:
                if p not in char:
                    continue
                cluster = first + joiner + char[p]
                for label, t in _with_signs(f"{c.name} {kind} {p}", cluster, CLUSTER_SIGNS):
                    out.append((kind, label, t))
                    out.append((f"{kind}+repaya", "repaya " + label, REPAYA + t))

    # 4. ZWJ spellings of the prenasalised letters
    for name, a, b in PRENASALISED:
        for label, t in _with_signs(f"{name} as ZWJ conjunct", a + VIRAMA + ZWJ + b,
                                    CLUSTER_SIGNS):
            out.append(("prenasalised", label, t))

    # 5. numerals: ASCII digits (for the numeral sets) and Lith digits
    ascii_nums = [str(d) for d in range(10)] + [str(d * 10) for d in range(1, 10)]
    ascii_nums += ["100", "1000", "1234567890"]
    for n in ascii_nums:
        out.append(("numerals", f"ascii {n}", n))
    lith = [chr(0x0DE6 + d) for d in range(10)]
    for d in range(10):
        out.append(("numerals", f"lith {d}", lith[d]))
        out.append(("numerals", f"lith {d}0", lith[d] + lith[0]))
    return out


SINHALA_RE = re.compile(r"[඀-෿\U000111e0-\U000111ff]")


def text_tokens() -> list[tuple[str, str]]:
    """(file, token) for every distinct Sinhala token in the test texts."""
    seen: dict[str, str] = {}
    for stem in TEXT_FILES:
        path = TEXTS / f"{stem}.md"
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        if text.startswith("---"):                    # skip the YAML front matter
            text = text.split("---", 2)[2]
        for tok in re.split(r"[\s,;:.!?()\[\]\"'“”‘’/\\|=*#`<>]+", text):
            if tok and SINHALA_RE.search(tok):
                seen.setdefault(tok, stem)
    return [(stem, tok) for tok, stem in seen.items()]


# ---- the two feature sets ----------------------------------------------------- #

def hand_written_fea(source: Path) -> str:
    """The source's own features (prefixes, classes, features), as the build sees them."""
    from glyphsLib.builder.features import _to_ufo_features
    from lankafea.glyphspackage import load_source
    return _to_ufo_features(load_source(source), minimal=True)


def baseline_fea(case: FontCase) -> tuple[str, str]:
    """(fea, where it came from): the frozen copy if there is one, else the source."""
    frozen = BASELINES / f"{case.key}.fea"
    if frozen.exists():
        return frozen.read_text(encoding="utf-8"), f"frozen ({frozen.name})"
    return hand_written_fea(case.source), "source"


def freeze(case: FontCase) -> Path:
    BASELINES.mkdir(parents=True, exist_ok=True)
    out = BASELINES / f"{case.key}.fea"
    out.write_text(hand_written_fea(case.source), encoding="utf-8")
    return out


@dataclass
class SourceMetrics:
    """What HarfBuzz needs beyond names and cmap to position like the real font: each
    glyph's advance (zero-width glyphs such as touch-sinh stay zero) and its GDEF class,
    exactly as glyphsLib gives them to the build (``public.openTypeCategories``: only
    the glyphs it classifies are in GDEF, so mark filtering behaves as in the font)."""
    widths: dict[str, int] = field(default_factory=dict)
    categories: dict[str, str] = field(default_factory=dict)   # base/ligature/mark/component


def source_metrics(source: Path) -> SourceMetrics:
    import glyphsLib
    from lankafea.glyphspackage import load_source
    ufo = glyphsLib.to_ufos(load_source(source), minimal=True)[0]    # first master
    return SourceMetrics({g.name: int(g.width or 0) for g in ufo},
                         dict(ufo.lib.get("public.openTypeCategories", {})))


def synthetic_font(inv: FontInventory, fea: str, out: Path,
                   metrics: SourceMetrics | None = None) -> Path:
    """Empty-outline font with the source's glyphs (exporting or not, so hand-written code
    that names a non-exporting glyph still compiles) and cmap, plus the given features.
    With ``metrics``, the source's advances and GDEF mark classes too (both feature sets
    get the same ones, so they still differ only in their features)."""
    from fontTools.feaLib.builder import addOpenTypeFeatures
    from fontTools.fontBuilder import FontBuilder
    from fontTools.ttLib.tables._g_l_y_f import Glyph

    names = set(inv.glyphs) | set(inv.non_exporting)
    order = [".notdef"] + sorted(n for n in names if n != ".notdef")
    cmap = {cp: n for cp, n in inv.cmap_names.items() if n in names}
    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap(cmap)
    fb.setupGlyf({n: Glyph() for n in order})
    widths = metrics.widths if metrics else {}
    fb.setupHorizontalMetrics({n: (widths.get(n, 600), 0) for n in order})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({"familyName": "LankaAcceptance", "styleName": "Regular"})
    fb.setupOS2()
    fb.setupPost()
    if metrics and metrics.categories and "table GDEF" not in fea:
        cls = {c: " ".join(n for n in order if metrics.categories.get(n) == c)
               for c in ("base", "ligature", "mark", "component")}
        fea = fea + ("\ntable GDEF {\n    GlyphClassDef [" + cls["base"] + "], ["
                     + cls["ligature"] + "], [" + cls["mark"] + "], ["
                     + cls["component"] + "];\n} GDEF;\n")
    fea_path = out.with_suffix(".fea")
    fea_path.write_text(fea, encoding="utf-8")
    addOpenTypeFeatures(fb.font, str(fea_path))
    fb.font.save(str(out))
    return out


class Shaper:
    """One HarfBuzz font, shaping many strings: (glyph names, positions)."""

    def __init__(self, path: Path):
        import uharfbuzz as hb
        self.hb = hb
        self.font = hb.Font(hb.Face(hb.Blob.from_file_path(str(path))))

    def shape(self, text: str, features: dict[str, bool] | None = None):
        hb = self.hb
        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        hb.shape(self.font, buf, features or {})
        names, pos = [], []
        for i, p in zip(buf.glyph_infos, buf.glyph_positions):
            name = self.font.glyph_to_string(i.codepoint)
            # HarfBuzz shows a default-ignorable it keeps (a ZWJ no rule consumed) as a
            # zero-advance space. It is invisible, so it doesn't count as a difference.
            if name == "space" and p.x_advance == 0:
                continue
            names.append(name)
            pos.append((p.x_advance, p.x_offset, p.y_offset))
        return names, pos


def font_features(path: Path) -> set[str]:
    """Every GSUB/GPOS feature tag the font registers, for any script."""
    from fontTools.ttLib import TTFont
    tt = TTFont(str(path))
    tags: set[str] = set()
    for t in ("GSUB", "GPOS"):
        if t in tt:
            tags.update(fr.FeatureTag for fr in tt[t].table.FeatureList.FeatureRecord)
    tt.close()
    return tags


def _nested_lookups(obj, found: set[int]) -> None:
    if isinstance(obj, (list, tuple)):
        for item in obj:
            _nested_lookups(item, found)
    elif hasattr(obj, "__dict__"):
        if obj.__class__.__name__ == "SubstLookupRecord":
            found.add(obj.LookupListIndex)
        else:
            for value in vars(obj).values():
                _nested_lookups(value, found)


def gsub_outputs(path: Path) -> set[str]:
    """Every glyph the font's GSUB can output, through any lookup a feature reaches."""
    from fontTools.ttLib import TTFont
    tt = TTFont(str(path))
    if "GSUB" not in tt:
        return set()
    gsub = tt["GSUB"].table
    lookups = gsub.LookupList.Lookup
    todo = {i for fr in gsub.FeatureList.FeatureRecord for i in fr.Feature.LookupListIndex}
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


# ---- comparison --------------------------------------------------------------- #

@dataclass
class Difference:
    feature: str          # "default" or the tag switched on
    section: str
    label: str
    text: str
    hand: list[str]
    generated: list[str]
    kind: str = "glyphs"  # "glyphs" or "positions" (same glyphs, different GPOS)
    category: str = ""


def _has(seq, pred) -> bool:
    return any(pred(g) for g in seq)


# Known items from the plan. Each: (id, description, predicate on a Difference). The first
# that matches wins, so list the specific ones first.
KNOWN = [
    ("T1", "repaya on a touching cluster (hand: plain, after the first consonant; generated: "
           "over the join, or over the first consonant before ි/ී, from sources/lankafea)",
     lambda d: REPAYA in d.text and ZWJ + VIRAMA in d.text),
    ("T2", "pre-base vowel on a touching cluster (hand: between the two consonants)",
     lambda d: ZWJ + VIRAMA in d.text
     and any(SIGN_CHAR[s] in d.text for s in ("esign", "eesign", "aisign", "osign", "oosign", "ausign"))
     and d.hand.index("esign-sinh") > d.generated.index("esign-sinh")
     if "esign-sinh" in d.hand and "esign-sinh" in d.generated else False),
    ("P2", "repaya + ි/ී (hand: C_repha and a separate sign, the old lookup never ran; "
           "generated: the vowel ligature with the repaya in the loop, from sources/lankafea)",
     lambda d: _has(d.generated, lambda g: re.match(r"repha-sinh\.00[678]$", g))
     and not _has(d.hand, lambda g: re.match(r"repha-sinh\.00[678]$", g))),
    ("A1", "cCa + u: hand drops a ca",
     lambda d: "cU-sinh" in d.hand and "cCU-sinh" in d.generated),
    ("A2", "yasign + virama: hand drops the virama",
     lambda d: "yasign_virama-sinh" in d.generated and "yasign_virama-sinh" not in d.hand),
    ("A3", "ZWJ conjunct turned into a prenasalised letter",
     lambda d: d.section == "prenasalised"
     or (ZWJ in d.text and _has(d.hand, lambda g: re.split(r"[-_]", g)[0].rstrip("IUiu")
                                in ("mba", "nnga", "nndda", "nyja", "mb", "nng", "nndd", "nyj")))),
    ("S2", "ss02: fpa + candrabindu takes the body-height variant (hand: ss02 ran before "
           "the candrabindu lookup, so fpa kept the tall one)",
     lambda d: d.feature == "ss02" and "fpa-sinh" in d.hand
     and "candrabindu-sinh.001" in d.generated and "candrabindu-sinh" in d.hand),
    ("Q1", "Lith ten-ligatures are off by default, only in ss07 (hand: always on, rlig; "
           "also showed ෯෦ as eighty)",
     lambda d: d.feature == "default"
     and _has(d.hand, lambda g: g.endswith("_lithzero-sinh"))
     and not _has(d.generated, lambda g: g.endswith("_lithzero-sinh"))),
    ("A5", "Lith ninety: hand shows ෯෦ as eighty",
     lambda d: "litheight_lithzero-sinh" in d.hand and "lithnine_lithzero-sinh" in d.generated),
    # Fixed by the refactor, so no longer known (a difference there is a regression):
    # G1/G2 (never fire), G3 (.rasign), G5 (yansaya Da forms), S1-S3 (sets), P1
    # (candrabindu), C1 (dist, from the font config).
]


@dataclass
class Result:
    case: FontCase
    baseline: str = ""
    kept_rules: int = 0
    features_compared: list[str] = field(default_factory=list)
    total: Counter = field(default_factory=Counter)   # feature -> strings compared
    same: Counter = field(default_factory=Counter)
    differences: list[Difference] = field(default_factory=list)
    hand_unreachable: set[str] = field(default_factory=set)

    def by_category(self, feature: str | None = None) -> Counter:
        return Counter(d.category for d in self.differences
                       if feature is None or d.feature == feature)

    def unexplained(self, feature: str | None = None) -> list[Difference]:
        return [d for d in self.differences if d.category == "unexplained"
                and (feature is None or d.feature == feature)]


def categorise(d: Difference, r: Result, hand_plain, gen_plain) -> str:
    if d.feature != "default":
        # The hand-written features change this text under the feature; the generated
        # ones don't touch it: the feature (or this part of it) isn't generated yet.
        if d.hand != hand_plain and d.generated == gen_plain:
            for kid, _, pred in KNOWN:
                if pred(d):
                    return kid
            return "feature"
    only_generated = set(d.generated) - set(d.hand)
    for kid, _, pred in KNOWN:
        if pred(d):
            return kid
    # A glyph the hand-written features never form (ndRa) — and whatever follows from
    # it (ndRa takes usign.rasign) — is a reach.
    if only_generated & r.hand_unreachable:
        return "reach"
    # Under a stylistic feature, a difference that starts from a default-run reach
    # (gen forms ndRa, so ss01 then makes ndRaa._c) is that reach, not a new one.
    plain_only = set(gen_plain) - set(hand_plain)
    if d.feature != "default" and plain_only and plain_only <= r.hand_unreachable:
        return "reach"
    return "unexplained"


def run(key: str, workdir: Path) -> Result:
    case = CASES[key]
    inv = inventory_from_glyphs(case.source)
    hand_fea, where = baseline_fea(case)
    cfg = case.config()
    built = build_fea("sinhala", inv, level=3, validate=True,
                      inject_paths=cfg.inject_paths or None, assign=cfg.assign,
                      options=cfg.options)
    metrics = source_metrics(case.source)
    hand_font = synthetic_font(inv, hand_fea, workdir / f"{key}-hand.ttf", metrics)
    gen_font = synthetic_font(inv, built.fea, workdir / f"{key}-generated.ttf", metrics)

    r = Result(case, baseline=where, kept_rules=built.report.kept_rules)
    reachable = gsub_outputs(hand_font)
    r.hand_unreachable = {n for n in inv.glyphs if n not in reachable}

    hand_tags = font_features(hand_font)
    stylistic = sorted(t for t in hand_tags if re.fullmatch(r"ss\d\d|dlig|salt|cv\d\d", t))
    r.features_compared = ["default"] + stylistic

    hand_sh, gen_sh = Shaper(hand_font), Shaper(gen_font)
    corpus = corpus_strings() + [(f"text:{stem}", tok, tok) for stem, tok in text_tokens()]
    for section, label, text in corpus:
        hand_plain, hand_plain_pos = hand_sh.shape(text)
        gen_plain, gen_plain_pos = gen_sh.shape(text)
        for feat in r.features_compared:
            if feat == "default":
                h, hp, g, gp = hand_plain, hand_plain_pos, gen_plain, gen_plain_pos
            else:
                h, hp = hand_sh.shape(text, {feat: True})
                g, gp = gen_sh.shape(text, {feat: True})
                if h == hand_plain and g == gen_plain and hp == hand_plain_pos and gp == gen_plain_pos:
                    continue      # the feature touches this text in neither font
            r.total[feat] += 1
            if h == g and hp == gp:
                r.same[feat] += 1
                continue
            d = Difference(feat, section, label, text, h, g,
                           kind="glyphs" if h != g else "positions")
            d.category = categorise(d, r, hand_plain, gen_plain)
            r.differences.append(d)
    return r


def report(r: Result, limit: int = 6, show_all: bool = False) -> str:
    lines = [f"== {r.case.key} ==",
             f"baseline: hand-written features from {r.baseline}; "
             f"generated: {r.kept_rules} rules kept"]
    for feat in r.features_compared:
        diffs = [d for d in r.differences if d.feature == feat]
        cats = r.by_category(feat)
        cat_str = ", ".join(f"{k} {v}" for k, v in sorted(cats.items()))
        lines.append(f"  {feat:8s} {r.same[feat]}/{r.total[feat]} identical, "
                     f"{len(diffs)} differ" + (f" ({cat_str})" if cat_str else ""))
    known = {kid: desc for kid, desc, _ in KNOWN}
    known.update({"reach": "generated output reaches a glyph the hand-written never can",
                  "feature": "stylistic feature not generated yet",
                  "unexplained": "UNEXPLAINED"})
    order = ["unexplained"] + [k for k, _, _ in KNOWN] + ["feature", "reach"]
    for cat in order:
        diffs = [d for d in r.differences if d.category == cat]
        if not diffs:
            continue
        pairs = Counter((d.feature, tuple(d.hand), tuple(d.generated)) for d in diffs)
        lines.append(f"\n-- {cat}: {known[cat]} — {len(diffs)} differences, "
                     f"{len(pairs)} distinct")
        example = {}
        for d in diffs:
            example.setdefault((d.feature, tuple(d.hand), tuple(d.generated)), d)
        n_show = len(pairs) if (show_all or cat == "unexplained") else limit
        for (feat, hand, gen), n in pairs.most_common(n_show):
            d = example[(feat, hand, gen)]
            lines.append(f"  x{n:<3} [{feat}] {d.label!r} ({d.section})")
            lines.append(f"       hand:      {' '.join(hand)}")
            lines.append(f"       generated: {' '.join(gen)}")
        if len(pairs) > n_show:
            lines.append(f"  … {len(pairs) - n_show} more (--all)")
    return "\n".join(lines)


def to_json(r: Result) -> dict:
    return {
        "font": r.case.key, "baseline": r.baseline, "kept_rules": r.kept_rules,
        "features": {f: {"total": r.total[f], "same": r.same[f],
                         "categories": dict(r.by_category(f))} for f in r.features_compared},
        "differences": [vars(d) for d in r.differences],
    }


if __name__ == "__main__":
    import tempfile
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    opts = [a for a in sys.argv[1:] if a.startswith("--")]
    json_out = None
    if "--json" in sys.argv:
        json_out = Path(sys.argv[sys.argv.index("--json") + 1])
        args = [a for a in args if a != str(json_out)]
    keys = args or list(CASES)
    for k in keys:
        case = CASES[k]
        if not available(case):
            print(f"== {k}: skipped (source not found)")
            continue
        if "--freeze" in opts:
            print(f"froze {freeze(case)}")
        with tempfile.TemporaryDirectory() as tmp:
            res = run(k, Path(tmp))
            print(report(res, show_all="--all" in opts), "\n")
            if json_out:
                json_out.write_text(json.dumps(to_json(res), ensure_ascii=False, indent=1),
                                    encoding="utf-8")

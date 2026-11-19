"""Per-feature candidate generators.

Each builder returns unfiltered IR (Lookups grouped into Features). Nothing here
consults the font — presence-gating (:mod:`lankafea.gating`) prunes candidates to
what the font actually contains. That division is what lets the same generators
serve any font, and lets Tamil work from a broad cartesian candidate set.

Rule shape follows the Noto reference embedded in
``tools/font-processing/NotoSansSinhala.glyphs``:
  * conjunct / virama forms are ligated first (akhn),
  * reph / rakar / yansa signs are formed (rphf / vatu),
  * vowel-sign ligatures act on the (possibly already-conjuncted) BASE glyph
    (abvs / blws / psts),
  * touching clusters shift a generic ``touch`` glyph (dist).
"""

from __future__ import annotations

import re

from .model import FeatureDoc, Feature, Lookup, Rule
from .names import (
    base_a, cap, drop_a, with_ns, glyph_for_codepoint, componentize, split_ns,
)
from .scripts import ScriptProfile, ZWJ
from .yamlloader import ScriptSpecs, GlyphSpec


def _sign_glyph(profile: ScriptProfile, sign_cp: int) -> str | None:
    alone = profile.tables.sign_alone.get(sign_cp)
    return with_ns(alone, profile.namespace) if alone else None


def _seq_glyphs(profile: ScriptProfile, cps: list[int]) -> list[str] | None:
    return componentize(profile.tables, cps, profile.namespace)


# --------------------------------------------------------------------------- #
# akhn — conjunct & pure-consonant (virama) formation
# --------------------------------------------------------------------------- #

def _conjunct_sequence(profile: ScriptProfile, c1: int, c2: int) -> list[int]:
    t = profile.tables
    if profile.conjunct_zwj:
        return [c1, t.virama, ZWJ, c2]
    return [c1, t.virama, c2]


def build_akhn(specs: ScriptSpecs) -> tuple[Feature, list[Lookup]]:
    """akhn conjuncts + the halant-form lookups.

    The halant forms (ka + virama -> k) are RETURNED SEPARATELY for abvs:
    placing them in akhn would consume `ra virama` / `ma virama` before the
    rphf/vatu triggers (`... virama zwj ...`) can match — akhn runs first in
    the basic stage. Abhaya (sin_virama) and Noto (VowelLigatures) both ligate
    halant forms in abvs.
    """
    profile = specs.profile
    t = profile.tables
    feat = Feature("akhn")
    conj_lk = Lookup("ConjunctLigatures", comment="stacked consonant conjuncts")
    pure_lk = Lookup("PureConsonants", comment="al-lakuna / virama forms")

    name_to_cp = {stem: cp for cp, stem in t.consonants.items()}

    for c in specs.consonants():
        c1 = c.unicode
        stem1 = t.consonants[c1]
        c1_base = with_ns(base_a(t, c1), profile.namespace)
        # Pure consonant (drop inherent a): C + virama -> stem
        virama_glyph = _sign_glyph(profile, t.virama)
        pure_lk.rules.append(Rule(
            kind="ligature",
            inputs=[c1_base, virama_glyph],
            output=with_ns(stem1, profile.namespace),
            comment=f"{stem1}a + virama",
        ))
        # Conjuncts from metadata (Sinhala). Tamil has none -> handled below.
        for second in (c.conjunct or []):
            c2 = name_to_cp.get(_stem_of(second, t))
            if c2 is None:
                continue
            seq = _conjunct_sequence(profile, c1, c2)
            lhs = _seq_glyphs(profile, seq)
            if lhs is None:
                continue
            out = drop_a(base_a(t, c1)) + cap(base_a(t, c2))
            conj_lk.rules.append(Rule(
                kind="ligature", inputs=lhs, output=with_ns(out, profile.namespace),
                comment=f"{stem1} + {t.consonants[c2]}",
            ))

    # Full C×C cartesian product IN ADDITION to the metadata conjuncts: gating
    # keeps only pairs whose output glyph exists, so fonts with conjuncts beyond
    # the YAML lists (kRa, jhRa, ...) still get their rules — and rakar-style
    # C+halant+ZWJ+ra clusters ligate here even when the font has no rasign.
    seen_out = {r.output for r in conj_lk.rules}
    cons = list(t.consonants.keys())
    for c1 in cons:
        for c2 in cons:
            out = with_ns(drop_a(base_a(t, c1)) + cap(base_a(t, c2)),
                          profile.namespace)
            if out in seen_out:
                continue
            seq = _conjunct_sequence(profile, c1, c2)
            lhs = _seq_glyphs(profile, seq)
            if lhs is None:
                continue
            seen_out.add(out)
            conj_lk.rules.append(Rule(
                kind="ligature", inputs=lhs, output=out,
                comment=f"{t.consonants[c1]} + {t.consonants[c2]}",
            ))

    # Halant forms of the conjuncts themselves (kRa + virama -> kR): the same
    # pure-consonant collapse, applied to every conjunct output.
    virama_glyph = _sign_glyph(profile, t.virama)
    pure_conj_lk = Lookup("PureConjuncts", comment="conjunct + virama forms")
    if virama_glyph:
        for out in sorted(seen_out):
            stem = out[: -len(f"-{profile.namespace}")] \
                if out.endswith(f"-{profile.namespace}") else out
            pure_conj_lk.rules.append(Rule(
                kind="ligature", inputs=[out, virama_glyph],
                output=with_ns(drop_a(stem), profile.namespace),
                comment=f"{stem} + virama",
            ))

    feat.lookups = [lk for lk in (conj_lk,) if lk.rules]
    halant_lookups = [lk for lk in (pure_lk, pure_conj_lk) if lk.rules]
    return feat, halant_lookups


def _stem_of(name: str, t) -> str:
    """A conjunct-metadata entry like 'ssa' -> its virama stem 'ss' if the entry is
    a base-with-a name; otherwise return as-is (already a stem)."""
    for cp, stem in t.consonants.items():
        if stem + "a" == name:
            return stem
    return name


# --------------------------------------------------------------------------- #
# rphf / vatu — reph, rakaransaya, yansaya sign formation
# --------------------------------------------------------------------------- #

def build_rphf(specs: ScriptSpecs) -> Feature | None:
    profile = specs.profile
    if not profile.form_reph:
        return None
    t = profile.tables
    seq = [t.ra, t.virama, ZWJ]
    lhs = _seq_glyphs(profile, seq)
    if lhs is None:
        return None
    feat = Feature("rphf")
    feat.lookups = [Lookup("Reph", rules=[Rule(
        kind="ligature", inputs=lhs, output=with_ns("repha", profile.namespace),
        comment="ra + virama + zwj -> repaya",
    )])]
    return feat


def build_vatu(specs: ScriptSpecs) -> Feature | None:
    profile = specs.profile
    t = profile.tables
    feat = Feature("vatu")
    lk = Lookup("BelowBaseForms", comment="rakaransaya / yansaya / touching sign")
    if profile.form_rakar:
        seq = [t.virama, ZWJ, t.ra]
        lhs = _seq_glyphs(profile, seq)
        if lhs:
            lk.rules.append(Rule(
                kind="ligature", inputs=lhs, output=with_ns("rasign", profile.namespace),
                comment="virama + zwj + ra -> rakaransaya",
            ))
    if profile.form_yansa and t.ya is not None:
        seq = [t.virama, ZWJ, t.ya]
        lhs = _seq_glyphs(profile, seq)
        if lhs:
            lk.rules.append(Rule(
                kind="ligature", inputs=lhs, output=with_ns("yasign", profile.namespace),
                comment="virama + zwj + ya -> yansaya",
            ))
    if profile.form_touch:
        # Generic touching glyph: zwj + virama -> touch (per the Noto reference).
        zwj_glyph = glyph_for_codepoint(t, ZWJ, profile.namespace)
        virama_glyph = _sign_glyph(profile, t.virama)
        if zwj_glyph and virama_glyph:
            lk.rules.append(Rule(
                kind="ligature", inputs=[zwj_glyph, virama_glyph],
                output=with_ns("touch", profile.namespace),
                comment="zwj + virama -> touching glyph",
            ))
    if not lk.rules:
        return None
    feat.lookups = [lk]
    return feat


# --------------------------------------------------------------------------- #
# abvs / blws / psts — vowel-sign ligatures on base glyphs
# --------------------------------------------------------------------------- #

def _base_names(specs: ScriptSpecs) -> list[str]:
    """Bare names of glyphs that vowel signs ligate onto: simple consonants, the
    formed conjunct glyphs listed in the YAML, and every cartesian two-consonant
    conjunct (so conjunct+vowel ligatures resolve even with no YAML categories —
    presence-gating drops the ones the font lacks)."""
    names: list[str] = []
    t = specs.profile.tables
    cons = list(specs.consonants())
    for c in cons:
        names.append(base_a(t, c.unicode))
    for cat in ("Orthographical conjuncts", "Ligated consonant conjuncts",
                "Required ligature glyphs"):
        for g in specs.in_category(cat):
            names.append(g.name)
    # Cartesian conjunct bases (kSsa, nDa, ...) — covers the YAML-free path.
    for c1 in cons:
        for c2 in cons:
            names.append(drop_a(base_a(t, c1.unicode)) + cap(base_a(t, c2.unicode)))
    # Dedupe, keep order.
    seen: set[str] = set()
    out = []
    for n in names:
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out


def build_vowel_ligatures(specs: ScriptSpecs) -> dict[str, Feature]:
    """Return {feature_tag: Feature} for abvs/blws/psts/pres vowel ligatures."""
    profile = specs.profile
    t = profile.tables
    ns = profile.namespace
    features: dict[str, Feature] = {}

    def feat(tag: str) -> Feature:
        if tag not in features:
            features[tag] = Feature(tag)
        return features[tag]

    def lookup_for(feature: Feature, name: str) -> Lookup:
        for lk in feature.lookups:
            if lk.name == name:
                return lk
        lk = Lookup(name)
        feature.lookups.append(lk)
        return lk

    # sign candidates: (cp, suffix, sign_alone_name)
    sign_candidates: list[tuple[int, str, str]] = []
    for cp, suffix in t.vsign_lig.items():
        sign_candidates.append((cp, suffix, t.sign_alone[cp]))
    for cp, (_low, capv) in t.vsign_below.items():
        if cp in t.sign_alone:
            sign_candidates.append((cp, capv, t.sign_alone[cp]))

    for base in _base_names(specs):
        base_glyph = with_ns(base, ns)
        for cp, suffix, sign_alone in sign_candidates:
            tag = profile.sign_feature.get(sign_alone, "psts")
            sign_glyph = with_ns(sign_alone, ns)
            lig = drop_a(base) + suffix
            f = feat(tag)
            lk = lookup_for(f, f"VowelLig_{tag}")
            # Above-base ligatures need mark filtering so the vowel sign is seen
            # adjacent to the base (matches the reference abvs lookup).
            if tag == "abvs":
                lk.mark_filter_set = _abvs_mark_set(t, ns)
            lk.rules.append(Rule(
                kind="ligature", inputs=[base_glyph, sign_glyph],
                output=with_ns(lig, ns), comment=f"{base} + {sign_alone}",
            ))
    return features


# --------------------------------------------------------------------------- #
# Da forms: below-base vowel signs on da-shaped bases (daa._c)
#
# Optional, not default shaping: the standard lists them under "ss01 Da Forms"
# (a stylistic set), so they go in that feature, not blws/psts. A font that also
# wants them under dlig routes the DaShape group there with `assign`.
# --------------------------------------------------------------------------- #

DA_SHAPE_DEFAULT_TAG = "ss01"


def _da_shape_bases(specs: ScriptSpecs) -> list[str]:
    """Base stems that take the ._c form. Da-shape applies when the FIRST
    consonant of the cluster is da-shaped (mirrors names._is_da_shape), so
    conjuncts like dRa/dVa and nDa qualify too."""
    t = specs.profile.tables
    shaped = {base_a(t, cp) for cp in t.da_shape_first} | {"nDa"}
    for cp1 in t.da_shape_first:
        for cp2 in t.consonants:
            shaped.add(drop_a(base_a(t, cp1)) + cap(base_a(t, cp2)))
    return [b for b in _base_names(specs) if b in shaped]


def da_shape_feature(specs: ScriptSpecs) -> str:
    """The stylistic set the standard puts the ._c forms in ("ss01 Da Forms")."""
    for key, members in specs.style_sets().items():
        tag = key.split()[0]
        if re.fullmatch(r"ss\d\d", tag) and any(g.name.endswith("._c") for g in members):
            return tag
    return DA_SHAPE_DEFAULT_TAG


def build_da_shape(specs: ScriptSpecs) -> Lookup | None:
    """da + aasign -> daa._c, and with a trailing virama (the tail of a decomposed
    oo sign) -> daa_virama._c.

    Stylistic sets run after psts, so by then the virama may already be part of
    aasign_virama: both spellings are generated and presence-gating keeps the ones
    the font can use."""
    t = specs.profile.tables
    if not t.da_shape_first:
        return None
    ns = specs.profile.namespace
    virama = with_ns(t.sign_alone[t.virama], ns)
    low_of = {t.sign_alone[cp]: low for cp, (low, _capv) in t.vsign_below.items()
              if cp in t.sign_alone}
    lk = Lookup("DaShape", comment="Da forms: below-base signs on da-shaped bases")
    yasign = with_ns("yasign", ns)
    aasign = with_ns("aasign", ns)
    for base in _da_shape_bases(specs):
        base_glyph = with_ns(base, ns)
        # Yansaya on a da-shaped base (ද්‍ය -> dya._c, ද්‍යා -> dyaa._c, ද්‍යු -> dyU._c).
        # A yansaya sign may already carry its vowel (yasign_usign) or not: by the time
        # a stylistic set runs both spellings can occur, so both are generated.
        ystem = drop_a(base) + "y"
        for spellings, out in (
            ([[yasign]], "a"),
            ([[with_ns("yasign_virama", ns)], [yasign, virama]], ""),
            ([[with_ns("yasign_aasign", ns)], [yasign, aasign]], "aa"),
            ([[with_ns("yasign_aasign_virama", ns)], [with_ns("yasign_aasign", ns), virama],
              [yasign, with_ns("aasign_virama", ns)], [yasign, aasign, virama]],
             "aa_virama"),
            ([[with_ns("yasign_usign", ns)], [yasign, with_ns("usign", ns)]], "U"),
            ([[with_ns("yasign_uusign", ns)], [yasign, with_ns("uusign", ns)]], "Uu"),
        ):
            for seq in spellings:
                lk.rules.append(Rule(
                    kind="ligature", inputs=[base_glyph, *seq],
                    output=with_ns(f"{ystem}{out}._c", ns),
                    comment=f"{base} + {' + '.join(g[:-5] for g in seq)} (below-base ._c)",
                    optional=True,          # alternative spellings: not every one applies
                ))
        for sign, low in low_of.items():
            stem = drop_a(base) + low
            lk.rules.append(Rule(
                kind="ligature", inputs=[base_glyph, with_ns(sign, ns)],
                output=with_ns(stem + "._c", ns),
                comment=f"{base} + {sign} (below-base ._c)",
            ))
            for inputs in ([base_glyph, with_ns(f"{sign}_virama", ns)],
                           [base_glyph, with_ns(sign, ns), virama]):
                lk.rules.append(Rule(
                    kind="ligature", inputs=inputs,
                    output=with_ns(stem + "_virama._c", ns),
                    comment=f"{base} + {sign} + virama (below-base ._c)",
                    optional=True,          # two spellings of one form: not both apply
                ))
    return lk if lk.rules else None


def _abvs_mark_set(t, ns: str) -> list[str]:
    members = []
    for cp in (t.virama, *t.vsign_lig.keys()):
        alone = t.sign_alone.get(cp)
        if alone:
            members.append(with_ns(alone, ns))
    return members


# --------------------------------------------------------------------------- #
# Presentation-stage ligatures on formed signs (repha / rakar / yansaya)
#
# These consume the signs that rphf/vatu produce. The shaper repositions the
# reph next to its base BEFORE the presentation features run (final reordering,
# REPH_POS_AFTER_POST), so `base repha` adjacency is real at abvs time — this is
# the Abhaya sinakhands_reph model. Candidates are cartesian over the base set;
# presence-gating keeps exactly the precomposed forms the font drew.
# --------------------------------------------------------------------------- #

def _repha_carriers(specs: ScriptSpecs) -> list[str]:
    """Bare stems the repha can ligate onto: bases, pure consonants,
    conjuncts, vsign-ligated forms, and the yansaya sign."""
    t = specs.profile.tables
    carriers: list[str] = []
    for base in _base_names(specs):
        carriers.append(base)
        carriers.append(drop_a(base))                       # pure/halant form
        for suffix in t.vsign_lig.values():                 # kI, dU, ...
            carriers.append(drop_a(base) + suffix)
    carriers.append("yasign")
    seen: set[str] = set()
    out = []
    for c in carriers:
        if c and c not in seen:
            seen.add(c)
            out.append(c)
    return out


def build_repha_ligatures(specs: ScriptSpecs) -> Lookup | None:
    """psts: base + repha -> base_repha (post-reorder adjacency).

    Registered in psts (the LAST presentation feature) so vowel-ligated
    carriers formed in abvs/blws (kI, dU, ...) already exist when it runs —
    presentation lookups apply in lookup-index order.
    """
    profile = specs.profile
    if not profile.form_reph:
        return None
    ns = profile.namespace
    repha = with_ns("repha", ns)
    lk = Lookup("RephLigatures",
                comment="precomposed reph forms, after the shaper moves the reph")
    for carrier in _repha_carriers(specs):
        lk.rules.append(Rule(
            kind="ligature", inputs=[with_ns(carrier, ns), repha],
            output=with_ns(f"{carrier}_repha", ns),
            comment=f"{carrier} + repha",
        ))
    return lk if lk.rules else None


def build_rakar_ligatures(specs: ScriptSpecs) -> Lookup | None:
    """vatu: base + rasign -> <stem>Ra (e.g. dRa-sinh).

    Lives in vatu (basic stage, right after rasign forms there) so the rakar
    ligature exists BEFORE the presentation vowel ligatures run — kRa + isign
    -> kRI then resolves in abvs. Abhaya does the same (sinrakaar in vatu).
    """
    profile = specs.profile
    if not profile.form_rakar:
        return None
    ns = profile.namespace
    rasign = with_ns("rasign", ns)
    lk = Lookup("RakarLigatures", comment="precomposed rakaransaya ligatures")
    for base in _base_names(specs):
        lk.rules.append(Rule(
            kind="ligature", inputs=[with_ns(base, ns), rasign],
            output=with_ns(drop_a(base) + "Ra", ns),
            comment=f"{base} + rasign",
        ))
    return lk if lk.rules else None


def build_yansaya_sign_ligatures(specs: ScriptSpecs) -> list[tuple[str, Lookup]]:
    """Ligatures on the yansaya carrier: yasign + sign -> yasign_<sign>.

    Routed per sign (abvs/blws/psts like the plain vowel ligatures; virama
    joins abvs — the Abhaya halant-form home). Second-order chains
    (yasign_aasign + virama -> yasign_aasign_virama) live in a SEPARATE psts
    lookup so they run after the first-order ligature has formed.
    """
    profile = specs.profile
    if not profile.form_yansa:
        return []
    t = profile.tables
    ns = profile.namespace
    yasign = with_ns("yasign", ns)
    lookups: dict[str, Lookup] = {}

    def lk_for(tag: str) -> Lookup:
        if tag not in lookups:
            lookups[tag] = Lookup(f"YansayaSigns_{tag}",
                                  comment="signs carried by the yansaya")
        return lookups[tag]

    sign_names = set(t.sign_alone.values())
    for sign in sorted(sign_names):
        if sign == "virama":
            tag = "abvs"
        else:
            tag = profile.sign_feature.get(sign, "psts")
        lk_for(tag).rules.append(Rule(
            kind="ligature", inputs=[yasign, with_ns(sign, ns)],
            output=with_ns(f"yasign_{sign}", ns),
            comment=f"yasign + {sign}",
        ))
    out = [(tag, lk) for tag, lk in lookups.items() if lk.rules]

    # Second order, separate lookup: the ligated carrier takes a trailing virama.
    virama = with_ns("virama", ns)
    chained = Lookup("YansayaSignsChained",
                     comment="second-order: ligated carrier + virama")
    for sign in sorted(sign_names - {"virama"}):
        chained.rules.append(Rule(
            kind="ligature",
            inputs=[with_ns(f"yasign_{sign}", ns), virama],
            output=with_ns(f"yasign_{sign}_virama", ns),
            comment=f"yasign_{sign} + virama",
        ))
    if chained.rules:
        out.append(("psts", chained))
    return out


def build_sign_virama_ligatures(specs: ScriptSpecs) -> Lookup | None:
    """psts: spacing sign + virama -> sign_virama (e.g. aasign_virama, the
    right-side component of the decomposed oo sign)."""
    profile = specs.profile
    t = profile.tables
    ns = profile.namespace
    virama = with_ns("virama", ns)
    lk = Lookup("SignVirama", comment="split-matra right components with virama")
    for sign in sorted(set(t.sign_alone.values()) - {"virama"}):
        lk.rules.append(Rule(
            kind="ligature", inputs=[with_ns(sign, ns), virama],
            output=with_ns(f"{sign}_virama", ns),
            comment=f"{sign} + virama",
        ))
    return lk if lk.rules else None


def build_touch_ligatures(specs: ScriptSpecs) -> Lookup | None:
    """akhn: C1 + zwj + virama + C2 -> <c1stem><C2a>Touch (touching clusters).

    Consumes the per-consonant ``touch:`` YAML metadata; the LankaGlyphset
    name is dropTrailingA(c1) + Cap(c2a) + 'Touch' (generators/index.ts).
    Fonts without precomposed touch glyphs fall back to the generic
    touch-sinh + dist shift.
    """
    profile = specs.profile
    if not profile.form_touch:
        return None
    t = profile.tables
    ns = profile.namespace
    name_to_cp = {stem: cp for cp, stem in t.consonants.items()}
    lk = Lookup("TouchLigatures", comment="precomposed touching clusters")
    for c in specs.consonants():
        c1 = c.unicode
        for second in (c.touch or []):
            c2 = name_to_cp.get(_stem_of(second, t))
            if c2 is None:
                continue
            # Touching sequence: C1 + ZWJ + virama + C2 (ZWJ before halant).
            lhs = _seq_glyphs(profile, [c1]) or []
            zwj_glyph = glyph_for_codepoint(t, ZWJ, ns)
            virama_glyph = _sign_glyph(profile, t.virama)
            c2_glyph = with_ns(base_a(t, c2), ns)
            if not (lhs and zwj_glyph and virama_glyph):
                continue
            out = drop_a(base_a(t, c1)) + cap(base_a(t, c2)) + "Touch"
            lk.rules.append(Rule(
                kind="ligature",
                inputs=[lhs[0], zwj_glyph, virama_glyph, c2_glyph],
                output=with_ns(out, ns),
                comment=f"{base_a(t, c1)} |touch| {base_a(t, c2)}",
            ))
    return lk if lk.rules else None


# --------------------------------------------------------------------------- #
# dist — touching-cluster spacing (GPOS)
# --------------------------------------------------------------------------- #

DIST_DEFAULT = -90


def build_dist(specs: ScriptSpecs, amount: int | None = None) -> Feature | None:
    """Pull the second consonant of a touching cluster towards the first. The amount
    is per font (font config dist); the default suits a 1000-unit em."""
    profile = specs.profile
    if profile.touch_strategy != "gpos" or not profile.form_touch:
        return None
    touch_glyph = with_ns("touch", profile.namespace)
    amount = DIST_DEFAULT if amount is None else int(amount)
    feat = Feature("dist")
    feat.lookups = [Lookup("TouchSpacing", rules=[Rule(
        kind="pos", inputs=[touch_glyph], value=f"<0 0 {amount} 0>",
        comment="tighten touching consonant clusters",
    )])]
    return feat


# --------------------------------------------------------------------------- #
# aalt / ssNN — make alternates & stylistic sets reachable
# --------------------------------------------------------------------------- #

def _alt_base_and_index(name: str) -> tuple[str, int] | None:
    """'isign.alt3' -> ('isign', 3); 'iisign.alt' -> ('iisign', 1)."""
    if ".alt" not in name:
        return None
    base, _, tail = name.partition(".alt")
    if tail == "":
        return base, 1
    if tail.isdigit():
        return base, int(tail)
    return None


def _variant_index(variant: str) -> int | None:
    """The alternate index in a variant suffix: ``alt`` -> 1, ``alt3`` -> 3.

    Anything else (``001``, ``stylalt1``, ``_c`` …) is not a numbered alternate."""
    if variant == "alt":
        return 1
    if variant.startswith("alt") and variant[3:].isdigit():
        return int(variant[3:])
    return None


def alt_groups(specs: ScriptSpecs, names: set[str] | None = None) -> dict[str, dict[int, str]]:
    """base -> {alt index: the alternate's full glyph name}.

    Alternate glyphs are discovered from the YAML specs by default, or from ``names``
    (the font's own glyph inventory) when given — the latter is used in the YAML-free
    path so alternates come straight from the font. Both positions of the dot-suffix
    are recognised: ``isign.alt1-sinh`` and ``isign-sinh.alt1`` are both an alternate
    of ``isign``.

    Tamil has none: its ``.alt`` glyphs are shape-group alternates and ``ra.alt``,
    not numbered alternates, and the Tamil model (tamil.py) places them itself.
    """
    profile = specs.profile
    if profile.model == "tamil":
        return {}
    ns = profile.namespace

    found: list[tuple[str, str, str]] = []          # (base, variant, full name)
    if names is not None:
        for n in names:
            parts = split_ns(n, ns)
            if parts and parts[1]:
                found.append((parts[0], parts[1], n))
    else:
        for g in specs.glyphs:
            base, _, variant = g.name.partition(".")
            if variant:
                found.append((base, variant, with_ns(g.name, ns, profile.dot_suffix_after)))

    groups: dict[str, dict[int, str]] = {}
    for base, variant, full in found:
        idx = _variant_index(variant)
        if idx is None:
            continue
        groups.setdefault(base, {})[idx] = full
    return groups


def alt_index_counts(groups: dict[str, dict[int, str]]) -> dict[int, list[str]]:
    """alt index -> sorted base names that have an alternate at that index."""
    out: dict[int, list[str]] = {}
    for base, alts in groups.items():
        for idx in alts:
            out.setdefault(idx, []).append(base)
    return {i: sorted(b) for i, b in sorted(out.items())}


def build_alternates(specs: ScriptSpecs, names: set[str] | None = None,
                     alt_targets: dict[int, str] | None = None) -> list[Feature]:
    """aalt (access-all-alternates) + one feature per alternate index.

    By default index N feeds ``ssNN``. ``alt_targets`` re-routes an index to another
    tag (``{2: "dlig"}``) or, with ``"none"``, keeps it reachable through aalt only.
    Several indices routed to one tag stay in separate lookups (lower index first,
    so it wins for a base glyph both define).
    """
    ns = specs.profile.namespace
    alt_targets = alt_targets or {}
    groups = alt_groups(specs, names)

    features: list[Feature] = []
    if not groups:
        return features

    aalt = Feature("aalt")
    aalt_lk = Lookup("AllAlternates")
    for base, alts in sorted(groups.items()):
        members = [with_ns(base, ns)] + [alts[i] for i in sorted(alts)]
        aalt_lk.rules.append(Rule(
            kind="alternate", inputs=[with_ns(base, ns)], output=members,
            comment=f"alternates of {base}",
        ))
    aalt.lookups = [aalt_lk]
    features.append(aalt)

    per_index: dict[int, Lookup] = {}
    for base, alts in sorted(groups.items()):
        for idx, altname in alts.items():
            tag = alt_targets.get(idx, f"ss{idx:02d}")
            if tag == "none":
                continue
            name = (f"StylisticSet{idx:02d}" if tag == f"ss{idx:02d}"
                    else f"Alternates{idx:02d}_{tag}")
            lk = per_index.setdefault(idx, Lookup(name))
            short = altname[:-len(f"-{ns}")] if altname.endswith(f"-{ns}") else altname
            lk.rules.append(Rule(
                kind="single", inputs=[with_ns(base, ns)],
                output=altname, comment=f"{base} -> {short}",
            ))

    by_tag: dict[str, Feature] = {}
    for idx, lk in sorted(per_index.items()):
        tag = alt_targets.get(idx, f"ss{idx:02d}")
        f = by_tag.get(tag)
        if f is None:
            f = by_tag[tag] = Feature(tag)
            features.append(f)
        f.lookups.append(lk)
    return features


# --------------------------------------------------------------------------- #
# Sign variants after rakar (usign.rasign)
# --------------------------------------------------------------------------- #

def build_rakar_sign_variants(specs: ScriptSpecs) -> Lookup | None:
    """blws: ු/ූ take their ``.rasign`` variant after a rakar ligature that has no
    precomposed u/uu form (kRa usign -> kRa usign.rasign).

    Runs after the vowel ligatures, so a font that draws kRU keeps it."""
    profile = specs.profile
    if not profile.form_rakar:
        return None
    ns = profile.namespace
    lk = Lookup("RakarSignVariants", comment="u/uu sign variants after rakar ligatures")
    for sign in ("usign", "uusign"):
        variant = with_ns(f"{sign}.rasign", ns)
        for base in _base_names(specs):
            lk.rules.append(Rule(
                kind="single",
                inputs=[with_ns(drop_a(base) + "Ra", ns), with_ns(sign, ns) + "'"],
                output=variant, comment=f"{drop_a(base)}Ra + {sign}", optional=True,
            ))
    return lk


# --------------------------------------------------------------------------- #
# ං + ශ: the archaic anusvaraya + sha ligatures (anusvarayaSha)
# --------------------------------------------------------------------------- #

ANUSVARA_SHA_DEFAULT_TAG = "dlig"


def build_anusvara_sha(specs: ScriptSpecs) -> Lookup | None:
    """anusvaraya + sha (and its halant and vowel forms) -> anusvarayaSh…

    An optional historical ligature, so it is generated into ``dlig``; a font routes
    the ``AnusvaraSha`` group elsewhere with ``assign`` (Abhaya: ss03). Both
    spellings of a vowel form are generated (``shU`` already formed, or ``sha usign``
    when the font has no shU), and gating keeps those the font can use."""
    t = specs.profile.tables
    ns = specs.profile.namespace
    sha_cp = next((cp for cp, stem in t.consonants.items() if stem == "sh"), None)
    anusvara = t.sign_alone.get(0x0D82)
    if sha_cp is None or not anusvara:
        return None
    lead = with_ns(anusvara, ns)
    lk = Lookup("AnusvaraSha", comment="ං + ශ archaic ligatures")
    forms = [("sha", None), ("sh", "virama")]
    forms += [("sh" + suffix, t.sign_alone[cp]) for cp, suffix in t.vsign_lig.items()]
    for form, sign in forms:
        out = with_ns(f"{anusvara}S{form[1:]}", ns)
        lk.rules.append(Rule(kind="ligature", inputs=[lead, with_ns(form, ns)], output=out,
                             comment=f"{anusvara} + {form}", optional=True))
        if sign:
            lk.rules.append(Rule(kind="ligature",
                                 inputs=[lead, with_ns("sha", ns), with_ns(sign, ns)],
                                 output=out, comment=f"{anusvara} + sha + {sign}",
                                 optional=True))
    return lk


# --------------------------------------------------------------------------- #
# ss02 Fa: every ෆ form -> its ප + f alternate (fa -> fpa, fU -> fpU, …)
# --------------------------------------------------------------------------- #

def fa_alternate_feature(specs: ScriptSpecs) -> str | None:
    """The stylistic set the standard lists the fpa forms under ("ss02 Fa")."""
    for key, members in specs.style_sets().items():
        tag = key.split()[0]
        if re.fullmatch(r"ss\d\d", tag) and any(g.name.startswith("fp") for g in members):
            return tag
    return None


def build_fa_alternates(specs: ScriptSpecs) -> Lookup | None:
    """fa-derived glyph -> its fp counterpart, for every form the generator can make
    from ෆ (base, halant, vowel ligatures, rakar and its forms, repha forms)."""
    t = specs.profile.tables
    ns = specs.profile.namespace
    if not any(stem == "f" for stem in t.consonants.values()):
        return None
    suffixes = list(t.vsign_lig.values())
    stems = ["fa", "f", "fRa", "fR", "fa_repha", "f_repha"]
    stems += ["f" + s for s in suffixes] + ["fR" + s for s in suffixes]
    stems += [f"f{s}_repha" for s in suffixes]
    lk = Lookup("FaAlternates", comment="ෆ forms -> the ප + f alternate")
    for stem in dict.fromkeys(stems):
        lk.rules.append(Rule(kind="single", inputs=[with_ns(stem, ns)],
                             output=with_ns("fp" + stem[1:], ns),
                             comment=f"{stem} -> fp{stem[1:]}", optional=True))
    return lk


# --------------------------------------------------------------------------- #
# Numeral sets: ASCII digits -> Lith digits / archaic numbers
#
# The standard names the glyphs (Sinhala numerals) but no feature, so these are
# generated only when a font routes them (font config `numerals:`).
# --------------------------------------------------------------------------- #

# ASCII digits are shaped as DFLT (a run of digits) or latn, so the numeral sets are
# registered there as well as under the script itself.
NUMERAL_SCRIPTS = ["DFLT", "latn", "sinh"]

DIGIT_WORDS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]
TENS_WORDS = {1: "ten", 2: "twenty", 3: "thirty", 4: "forty", 5: "fifty", 6: "sixty",
              7: "seventy", 8: "eighty", 9: "ninety"}


def build_lith_digits(specs: ScriptSpecs) -> Lookup:
    ns = specs.profile.namespace
    return Lookup("LithDigits", comment="ASCII digits -> Lith digits", rules=[
        Rule(kind="single", inputs=[w], output=with_ns(f"lith{w}", ns), comment=f"{w}")
        for w in DIGIT_WORDS])


def build_lith_tens(specs: ScriptSpecs) -> Lookup:
    """Lith digit + Lith zero -> the ten-ligature (෧෦ -> lithone_lithzero)."""
    ns = specs.profile.namespace
    zero = with_ns("lithzero", ns)
    return Lookup("LithTens", comment="Lith ten-ligatures", rules=[
        Rule(kind="ligature", inputs=[with_ns(f"lith{w}", ns), zero],
             output=with_ns(f"lith{w}_lithzero", ns), comment=f"lith{w} + lithzero")
        for w in DIGIT_WORDS[1:]])


def build_archaic_numbers(specs: ScriptSpecs) -> list[Lookup]:
    """ASCII digits -> archaic numbers: units, then tens (archaicone zero -> archaicten),
    then 100 and 1000. Archaic numbers have no zero, so a zero only ever builds a
    larger unit. One lookup per step, so each sees the previous one's output."""
    ns = specs.profile.namespace
    a = lambda w: with_ns(f"archaic{w}", ns)
    return [
        Lookup("ArchaicUnits", comment="ASCII digits -> archaic units", rules=[
            Rule(kind="single", inputs=[w], output=a(w)) for w in DIGIT_WORDS[1:]]),
        Lookup("ArchaicTens", comment="archaic unit + zero -> archaic ten", rules=[
            Rule(kind="ligature", inputs=[a(DIGIT_WORDS[d]), "zero"], output=a(TENS_WORDS[d]))
            for d in range(1, 10)]),
        Lookup("ArchaicHundred", rules=[
            Rule(kind="ligature", inputs=[a("ten"), "zero"], output=a("onehundred"))]),
        Lookup("ArchaicThousand", rules=[
            Rule(kind="ligature", inputs=[a("onehundred"), "zero"], output=a("onethousand"))]),
    ]


# --------------------------------------------------------------------------- #
# Top-level assembly of all generated features
# --------------------------------------------------------------------------- #

def generate(specs: ScriptSpecs, alt_names: set[str] | None = None,
             alt_targets: dict[int, str] | None = None,
             options: dict | None = None) -> FeatureDoc:
    """``options`` carries the per-font settings (see :mod:`lankafea.fontconfig`):
    ``dist`` (the touching-cluster shift), ``numerals`` (which features get the
    Lith / archaic numeral sets) and ``featureNames`` (ssNN names)."""
    options = options or {}
    doc = FeatureDoc()
    akhn_feat, halant_lookups = build_akhn(specs)
    doc.features.append(akhn_feat)
    for f in (build_rphf(specs), build_vatu(specs)):
        if f:
            doc.features.append(f)
    for tag, f in build_vowel_ligatures(specs).items():
        doc.features.append(f)
    # Halant forms live in abvs, FIRST (before the vowel ligatures) so k-forms
    # exist for anything downstream; see build_akhn docstring for why not akhn.
    if halant_lookups:
        doc.feature("abvs").lookups[:0] = halant_lookups

    # Presentation/basic ligatures consuming the formed signs.
    touch_lk = build_touch_ligatures(specs)
    if touch_lk:
        doc.feature("akhn").lookups.append(touch_lk)
    rakar_lk = build_rakar_ligatures(specs)
    if rakar_lk:
        doc.feature("vatu").lookups.append(rakar_lk)
    sign_virama_lk = build_sign_virama_ligatures(specs)
    if sign_virama_lk:
        doc.feature("psts").lookups.append(sign_virama_lk)
    for tag, lk in build_yansaya_sign_ligatures(specs):
        doc.feature(tag).lookups.append(lk)
    repha_lk = build_repha_ligatures(specs)
    if repha_lk:
        doc.feature("psts").lookups.append(repha_lk)

    # .rasign u/uu variants: after the blws vowel ligatures, so a drawn kRU wins.
    rakar_var_lk = build_rakar_sign_variants(specs)
    if rakar_var_lk:
        doc.feature("blws").lookups.append(rakar_var_lk)

    dist = build_dist(specs, options.get("dist"))
    if dist:
        doc.features.append(dist)
    doc.features.extend(build_alternates(specs, names=alt_names,
                                         alt_targets=alt_targets))
    da_lk = build_da_shape(specs)
    if da_lk:
        # First in its feature, so a base alternate (da.alt) in the same set
        # doesn't stop the ligature from matching.
        doc.feature(da_shape_feature(specs)).lookups.insert(0, da_lk)
    fa_tag = fa_alternate_feature(specs)
    fa_lk = build_fa_alternates(specs) if fa_tag else None
    if fa_lk:
        doc.feature(fa_tag).lookups.append(fa_lk)
    anusvara_lk = build_anusvara_sha(specs)
    if anusvara_lk:
        doc.feature(ANUSVARA_SHA_DEFAULT_TAG).lookups.append(anusvara_lk)
    _add_numerals(doc, specs, options.get("numerals") or {})

    # Drop any feature that ended up with no lookups/rules.
    doc.features = [f for f in doc.features if any(lk.rules for lk in f.lookups)]
    _name_features(doc, specs, options.get("featureNames") or {})
    return doc


def _as_tags(value) -> list[str]:
    if not value:
        return []
    return [value] if isinstance(value, str) else list(value)


def _add_numerals(doc: FeatureDoc, specs: ScriptSpecs, numerals: dict) -> None:
    """``numerals: {lith: ss07, lithTens: rlig, archaic: ss08}``. The ten-ligatures
    also run in the Lith set, right after the digits it makes."""
    if specs.profile.model == "tamil":
        return
    tens_tags = _as_tags(numerals.get("lithTens"))
    for tag in tens_tags:
        lk = build_lith_tens(specs)
        lk.name = f"LithTens_{tag}" if tag != tens_tags[0] else "LithTens"
        doc.feature(tag).lookups.append(lk)
    for tag in _as_tags(numerals.get("lith")):
        tens = build_lith_tens(specs)
        tens.name = f"LithTens_{tag}"
        feature = doc.feature(tag)
        feature.lookups.extend([build_lith_digits(specs), tens])
        feature.scripts = NUMERAL_SCRIPTS
    for tag in _as_tags(numerals.get("archaic")):
        lookups = build_archaic_numbers(specs)
        if tag != _as_tags(numerals.get("archaic"))[0]:
            for lk in lookups:
                lk.name = f"{lk.name}_{tag}"
        feature = doc.feature(tag)
        feature.lookups.extend(lookups)
        feature.scripts = NUMERAL_SCRIPTS


def _name_features(doc: FeatureDoc, specs: ScriptSpecs, names: dict) -> None:
    """ssNN display names: the font's own (``featureNames``), else the name the
    standard gives the set ("ss01 Da Forms" -> "Da Forms")."""
    standard = {}
    for key in specs.style_sets():
        tag, _, label = key.partition(" ")
        if re.fullmatch(r"ss\d\d", tag) and label:
            standard[tag] = label.strip()
    for f in doc.features:
        if re.fullmatch(r"ss\d\d", f.tag):
            f.names = names.get(f.tag) or standard.get(f.tag)

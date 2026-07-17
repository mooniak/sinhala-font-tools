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

from .model import FeatureDoc, Feature, Lookup, Rule
from .names import (
    base_a, cap, drop_a, with_ns, glyph_for_codepoint, componentize,
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

    # Below/spacing signs that take the lowercase ._c form on da-shaped bases.
    low_of = {t.sign_alone[cp]: low for cp, (low, _capv) in t.vsign_below.items()
              if cp in t.sign_alone}
    # Da-shape applies when the FIRST consonant of the cluster is da-shaped
    # (mirrors names._is_da_shape), so conjuncts like dRa/dVa qualify too.
    da_shape_names = {base_a(t, cp) for cp in t.da_shape_first} | {"nDa"}
    for cp1 in t.da_shape_first:
        for cp2 in t.consonants:
            da_shape_names.add(drop_a(base_a(t, cp1)) + cap(base_a(t, cp2)))

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
            # Da-shaped bases also get the below-base ._c candidate (daa._c);
            # presence-gating keeps whichever variant the font drew.
            if base in da_shape_names and sign_alone in low_of:
                lk.rules.append(Rule(
                    kind="ligature", inputs=[base_glyph, sign_glyph],
                    output=with_ns(drop_a(base) + low_of[sign_alone] + "._c", ns),
                    comment=f"{base} + {sign_alone} (below-base ._c)",
                ))

    # Chained: a formed ._c ligature takes a trailing virama (the oo-sign
    # decomposition tail: da + aasign + virama -> daa._c -> daa_virama._c).
    virama_glyph = with_ns(t.sign_alone[t.virama], ns)
    chained = Lookup("DaShapeViramaChained",
                     comment="below-base ._c ligature + virama")
    for base in _base_names(specs):
        if base not in da_shape_names:
            continue
        for low in set(low_of.values()):
            stem = drop_a(base) + low
            chained.rules.append(Rule(
                kind="ligature",
                inputs=[with_ns(stem + "._c", ns), virama_glyph],
                output=with_ns(stem + "_virama._c", ns),
                comment=f"{stem}._c + virama",
            ))
    if chained.rules:
        f = feat("psts")
        f.lookups.append(chained)
    return features


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

def build_dist(specs: ScriptSpecs) -> Feature | None:
    profile = specs.profile
    if profile.touch_strategy != "gpos" or not profile.form_touch:
        return None
    touch_glyph = with_ns("touch", profile.namespace)
    feat = Feature("dist")
    feat.lookups = [Lookup("TouchSpacing", rules=[Rule(
        kind="pos", inputs=[touch_glyph], value="<0 0 -90 0>",
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


def build_alternates(specs: ScriptSpecs, names: set[str] | None = None) -> list[Feature]:
    """aalt (access-all-alternates) + one ssNN per alternate index.

    Alternate glyphs are discovered from the YAML specs by default, or from ``names``
    (the font's own glyph inventory) when given — the latter is used in the YAML-free
    path so alternates come straight from the font. Names are matched with the
    namespace stripped so ``isign.alt1-sinh`` -> base ``isign``.
    """
    profile = specs.profile
    ns = profile.namespace
    suffix = f"-{ns}"

    if names is not None:
        candidate_names = [n[:-len(suffix)] if n.endswith(suffix) else n for n in names]
    else:
        candidate_names = [g.name for g in specs.glyphs]

    # Collect base -> {index: altname} from all glyphs carrying a .alt suffix.
    groups: dict[str, dict[int, str]] = {}
    for gname in candidate_names:
        parsed = _alt_base_and_index(gname)
        if not parsed:
            continue
        base, idx = parsed
        groups.setdefault(base, {})[idx] = gname

    features: list[Feature] = []
    if groups:
        aalt = Feature("aalt")
        aalt_lk = Lookup("AllAlternates")
        for base, alts in sorted(groups.items()):
            members = [with_ns(base, ns)] + [
                with_ns(alts[i], ns) for i in sorted(alts)
            ]
            aalt_lk.rules.append(Rule(
                kind="alternate", inputs=[with_ns(base, ns)], output=members,
                comment=f"alternates of {base}",
            ))
        aalt.lookups = [aalt_lk]
        features.append(aalt)

        # ssNN: alt index N -> feature ssNN, single substitution from the default.
        ss: dict[int, Lookup] = {}
        for base, alts in sorted(groups.items()):
            for idx, altname in alts.items():
                lk = ss.setdefault(idx, Lookup(f"StylisticSet{idx:02d}"))
                lk.rules.append(Rule(
                    kind="single", inputs=[with_ns(base, ns)],
                    output=with_ns(altname, ns), comment=f"{base} -> {altname}",
                ))
        for idx, lk in sorted(ss.items()):
            f = Feature(f"ss{idx:02d}")
            f.lookups = [lk]
            features.append(f)
    return features


# --------------------------------------------------------------------------- #
# Top-level assembly of all generated features
# --------------------------------------------------------------------------- #

def generate(specs: ScriptSpecs, alt_names: set[str] | None = None) -> FeatureDoc:
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

    dist = build_dist(specs)
    if dist:
        doc.features.append(dist)
    doc.features.extend(build_alternates(specs, names=alt_names))
    # Drop any feature that ended up with no lookups/rules.
    doc.features = [f for f in doc.features if any(lk.rules for lk in f.lookups)]
    return doc

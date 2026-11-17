"""The Tamil feature model.

Tamil is not Sinhala with a few switches off. A Tamil syllable never needs a joiner,
there is no reph, rakar, yansa or touching cluster, and the standard
(docs/naming-standard.md, Tamil §4–5) lets a font meet a consonant + sign *form* in
either of two ways:

  1. its own glyph, a ligature rule:            sub ka-taml isign-taml by kI-taml;
  2. the shape-group alternate of the sign:     sub @isign_ka isign-taml' by isign-taml.ka;

A consonant that is in no group of a sign takes the plain sign, so there is nothing
to generate for it. Which forms the standard *requires* (and from which level) is
read from the glyphset YAML; every other form is generated too, but only when the
font has its glyph, and a missing one is never reported.

Where things go (D6): க்ஷ and ஸ்ரீ in ``akhn``; ி/ீ forms in ``abvs``; ு/ூ forms in
``psts``; the traditional (pre-1978) orthography in one stylistic set, ``ss09``, so
modern text keeps its modern shapes. There are no ``pres`` rules and no
consonant + consonant conjuncts.
"""

from __future__ import annotations

from dataclasses import dataclass

from .model import FeatureDoc, GlyphClass, Lookup, Rule
from .names import drop_a, with_ns
from .validation import _resolve_class, _strip_marker
from .yamlloader import ScriptSpecs

# Where each sign's ligatures and shape-group alternates are registered.
SIGN_FEATURE = {"isign": "abvs", "iisign": "abvs", "usign": "psts", "uusign": "psts"}
DEFAULT_SIGNS = tuple(SIGN_FEATURE)

# ர shows its alternate form before these (the traditional style).
RA_ALT_FOLLOWERS = ("virama", "anusvaraya", "isign", "iisign")

# The pre-base signs sit BEFORE the consonant once the shaper has reordered them.
PRE_BASE_SIGNS = {"esign", "eesign", "aisign"}


@dataclass
class Unit:
    """Something the standard can require: a form, a conjunct, a letter variant."""

    name: str                    # bare name: "kI", "kSsa", "ra.alt"
    glyph: str                   # full name: "kI-taml"
    tier: int | None             # tier file that enumerates it (None: not enumerated)
    kind: str                    # "form" | "single"
    consonant: str | None = None   # bare: "ka", "kSsa"
    sign: str | None = None
    group: str | None = None       # shape group of `sign` the consonant is in
    alt_glyph: str | None = None   # "isign-taml.ka"
    traditional: bool = False

    def required(self, level: int) -> bool:
        return self.tier is not None and self.tier <= level


def class_name(sign: str, group: str) -> str:
    return f"{sign}_{group}"


def _sign_abbrs(profile) -> dict[str, str]:
    """sign glyph name -> the capital abbreviation used in form names (I, Ii, U …)."""
    t = profile.tables
    out: dict[str, str] = {}
    for cp, suffix in t.vsign_lig.items():
        out[t.sign_alone[cp]] = suffix
    for cp, (_low, capv) in t.vsign_below.items():
        out[t.sign_alone[cp]] = capv
    return out


def _rows(specs: ScriptSpecs) -> list[str]:
    """The consonants forms are built on: the 23 letters, then the க்ஷ conjunct."""
    return [c.name for c in specs.consonants()] + ["kSsa"]


def _parse_form(name: str, rows: list[str], by_abbr: dict[str, str]) -> tuple[str, str] | None:
    """kI -> ("ka", "isign"); llAi -> ("lla", "aisign"). Longest matching stem wins."""
    best: tuple[str, str, str] | None = None
    for row in rows:
        stem = drop_a(row)
        rest = name[len(stem):]
        if name.startswith(stem) and rest in by_abbr:
            if best is None or len(stem) > len(best[0]):
                best = (stem, row, by_abbr[rest])
    return (best[1], best[2]) if best else None


def build_units(specs: ScriptSpecs) -> dict[str, Unit]:
    """Every unit the Tamil model can generate or the standard can require."""
    profile = specs.profile
    ns, after = profile.namespace, profile.dot_suffix_after
    abbr = _sign_abbrs(profile)
    by_abbr = {v: k for k, v in abbr.items() if v}
    rows = _rows(specs)
    group_of = {(sign, member): group
                for sign, groups in specs.groups.items()
                for group, members in groups.items() for member in members}
    traditional = [g.name for g in specs.glyphs
                   if g.category.startswith(profile.traditional_feature + " ")]

    def tier_of(name: str) -> int | None:
        spec = specs.by_name.get(name)
        return spec.tier if spec else None

    def form(consonant: str, sign: str, trad: bool) -> Unit:
        name = drop_a(consonant) + abbr[sign]
        group = group_of.get((sign, consonant))
        return Unit(
            name=name, glyph=with_ns(name, ns, after), tier=tier_of(name), kind="form",
            consonant=consonant, sign=sign, group=group,
            alt_glyph=with_ns(f"{sign}.{group}", ns, after) if group else None,
            traditional=trad)

    units: dict[str, Unit] = {}
    for row in rows:
        for sign in DEFAULT_SIGNS:
            u = form(row, sign, False)
            units[u.name] = u
    for name in traditional:
        parsed = _parse_form(name, rows, by_abbr)
        if parsed:
            units[name] = form(parsed[0], parsed[1], True)
    # Single-glyph units: the conjuncts, the alternate ra, and the pulli forms.
    for name in ("kSsa", "shree", "ra.alt"):
        units[name] = Unit(name, with_ns(name, ns, after), tier_of(name), "single",
                           traditional=(name == "ra.alt"))
    for row in rows:
        stem = drop_a(row)
        units.setdefault(stem, Unit(stem, with_ns(stem, ns, after), None, "single"))
    return units


def generate_tamil(specs: ScriptSpecs) -> FeatureDoc:
    """Candidate rules for Tamil: broad, presence-gated later, driven by the standard."""
    profile = specs.profile
    ns, after = profile.namespace, profile.dot_suffix_after

    def g(stem: str) -> str:
        return with_ns(stem, ns, after)

    units = build_units(specs)
    abbr = _sign_abbrs(profile)
    rows = _rows(specs)
    virama = g("virama")
    doc = FeatureDoc()
    doc.meta["units"] = units
    doc.meta["level"] = profile.level

    # --- akhn: க்ஷ and ஸ்ரீ (both spellings, ஶ and ஸ, form one glyph) --------------
    akhands = Lookup("Akhands", comment="க்ஷ and ஸ்ரீ / ஶ்ரீ")
    akhands.rules.append(Rule(
        "ligature", [g("ka"), virama, g("ssa")], g("kSsa"),
        comment="ka + pulli + ssa", unit="kSsa", route="single"))
    for letter in ("sha", "sa"):
        akhands.rules.append(Rule(
            "ligature", [g(letter), virama, g("ra"), g("iisign")], g("shree"),
            comment=f"{letter} + pulli + ra + iisign", unit="shree", route="single"))
    doc.feature("akhn").lookups.append(akhands)

    # --- abvs: pulli forms, then ி/ீ forms; psts: ு/ூ forms --------------------------
    pure = Lookup("PureConsonants", comment="consonant + pulli forms, where the font draws them")
    for row in rows:
        stem = drop_a(row)
        pure.rules.append(Rule(
            "ligature", [g(row), virama], g(stem),
            comment=f"{row} + virama", unit=stem, route="single"))
    doc.feature("abvs").lookups.append(pure)

    for tag, signs in (("abvs", ("isign", "iisign")), ("psts", ("usign", "uusign"))):
        ligatures = Lookup(f"SignLigatures_{tag}", comment="dedicated consonant + sign glyphs")
        for row in rows:
            for sign in signs:
                u = units[drop_a(row) + abbr[sign]]
                ligatures.rules.append(Rule(
                    "ligature", [g(row), g(sign)], u.glyph,
                    comment=f"{row} + {sign}", unit=u.name, route="ligature",
                    hint=(f"or draw the shape-group alternate {u.alt_glyph}"
                          if u.alt_glyph else None)))
        doc.feature(tag).lookups.append(ligatures)

        alternates = Lookup(f"SignAlternates_{tag}", comment="shape-group sign alternates")
        for sign in signs:
            for group, members in specs.groups.get(sign, {}).items():
                _add_group(doc, alternates, g, units, abbr, sign, group, members,
                           pre_base=False)
        if alternates.rules:
            doc.feature(tag).lookups.append(alternates)

    # --- ss09: the traditional (pre-1978) orthography -----------------------------
    tag = profile.traditional_feature
    aa = Lookup("TraditionalAa", comment="ணா னா றா")
    ai = Lookup("TraditionalAi", comment="ணை னை லை ளை; ை comes before its consonant")
    for u in units.values():
        if not (u.traditional and u.kind == "form"):
            continue
        if u.sign == "aasign":
            aa.rules.append(Rule(
                "ligature", [g(u.consonant), g("aasign")], u.glyph,
                comment=f"{u.consonant} + aasign", unit=u.name, route="ligature"))
        elif u.sign == "aisign":
            ai.rules.append(Rule(
                "ligature", [g("aisign"), g(u.consonant)], u.glyph,
                comment=f"aisign + {u.consonant}", unit=u.name, route="ligature",
                hint=(f"or draw the shape-group alternate {u.alt_glyph}"
                      if u.alt_glyph else None)))
    ai_alt = Lookup("TraditionalAiAlternates", comment="ை shaped for ண ன ல ள")
    for group, members in specs.groups.get("aisign", {}).items():
        _add_group(doc, ai_alt, g, units, abbr, "aisign", group, members, pre_base=True)

    ra = Lookup("TraditionalRa", comment="the alternate ர before pulli, anusvara, ி and ீ")
    doc.classes.append(GlyphClass("ra_alt_next", [g(x) for x in RA_ALT_FOLLOWERS]))
    ra.rules.append(Rule(
        "single", [f"{g('ra')}'", "@ra_alt_next"], g("ra.alt"),
        comment="ra -> ra.alt before pulli / anusvara / i / ii",
        unit="ra.alt", route="single"))
    for lk in (aa, ai, ai_alt, ra):
        if lk.rules:
            doc.feature(tag).lookups.append(lk)
    return doc


def _add_group(doc: FeatureDoc, lookup: Lookup, g, units: dict[str, Unit],
               abbr: dict[str, str], sign: str, group: str, members: list[str],
               pre_base: bool) -> None:
    """One class rule: the sign becomes its <sign>.<group> alternate next to a member."""
    cls = class_name(sign, group)
    doc.classes.append(GlyphClass(cls, [g(m) for m in members]))
    covered = [drop_a(m) + abbr[sign] for m in members]
    covered = [n for n in covered if n in units]
    sign_token = f"{g(sign)}'"
    inputs = [sign_token, f"@{cls}"] if pre_base else [f"@{cls}", sign_token]
    first = ", ".join(units[n].glyph for n in covered[:3])
    lookup.rules.append(Rule(
        "single", inputs, g(f"{sign}.{group}"),
        comment=f"{sign} -> {sign}.{group} next to @{cls}",
        units=covered, route="alternate",
        hint=f"or draw the dedicated glyphs ({first}{' …' if len(covered) > 3 else ''})"))


def adopt_source_classes(doc: FeatureDoc, source_classes: dict[str, list[str]]) -> None:
    """A designer's own class of the same name wins over the standard's default
    members (how a font narrows a shape group: it draws those as ligatures)."""
    for cls in doc.classes:
        members = source_classes.get(cls.name)
        if members:
            cls.members = list(members)


def resolve_requirements(doc: FeatureDoc, present: set[str],
                         level: int | None = None) -> list[dict]:
    """Decide, from the font's glyphs, which rules the standard actually requires.

    A form is met by its own glyph OR by the sign's shape-group alternate, so:
      * a ligature rule is optional when the form is not required at ``level`` or
        its alternate meets it;
      * a class rule is optional when every required form it could meet already
        has its own glyph;
      * a single-glyph rule is optional when it is not required at ``level``.
    A blocked optional rule is dropped silently; a required form met neither way
    keeps both rules mandatory, so the report names the missing glyphs of both.

    Returns the per-form report (forms required at ``level``) for the validator.
    """
    units: dict[str, Unit] = doc.meta.get("units") or {}
    if not units:
        return []
    level = doc.meta.get("level", 2) if level is None else level

    classes = {c.name: c for c in doc.classes}
    live = {n: set(_resolve_class(n, classes, present, set())) for n in classes}

    def tokens_present(rule: Rule) -> bool:
        out = rule.output if isinstance(rule.output, list) else [rule.output]
        for token in [*rule.inputs, *out]:
            token = _strip_marker(token)
            if token.startswith("@"):
                if not live.get(token[1:]):
                    return False
            elif token not in present:
                return False
        return True

    lig_rules: dict[str, list[Rule]] = {}
    alt_rules: list[Rule] = []
    alt_of_unit: dict[str, Rule] = {}
    for feature in doc.features:
        for lookup in feature.lookups:
            for rule in lookup.rules:
                if rule.unit:
                    lig_rules.setdefault(rule.unit, []).append(rule)
                elif rule.units:
                    alt_rules.append(rule)
                    for name in rule.units:
                        alt_of_unit.setdefault(name, rule)

    def consonant_glyph(unit: Unit, rule: Rule) -> str:
        pos = 1 if unit.sign in PRE_BASE_SIGNS else 0
        return rule.inputs[pos]

    def alt_available(unit: Unit, rule: Rule | None, cglyph: str | None) -> bool:
        if rule is None or cglyph is None:
            return False
        sign_tok = next(_strip_marker(t) for t in rule.inputs if not t.startswith("@"))
        cls = next(_strip_marker(t) for t in rule.inputs if t.startswith("@"))[1:]
        return (rule.output in present and sign_tok in present
                and cglyph in live.get(cls, ()))

    status: dict[str, tuple[bool, bool]] = {}      # unit -> (own glyph, alternate)
    for name, unit in units.items():
        rules = lig_rules.get(name, [])
        own = bool(rules) and all(tokens_present(r) for r in rules)
        cglyph = consonant_glyph(unit, rules[0]) if rules and unit.kind == "form" else None
        alt = unit.kind == "form" and alt_available(unit, alt_of_unit.get(name), cglyph)
        status[name] = (own, alt)
        for rule in rules:
            rule.optional = (not unit.required(level)) or (unit.alt_glyph is not None and alt)

    for rule in alt_rules:
        rule.optional = not any(
            units[n].required(level) and not status[n][0] for n in rule.units)

    report: list[dict] = []
    for name, unit in units.items():
        if unit.tier is None or unit.tier > level:
            continue
        own, alt = status[name]
        report.append({
            "form": unit.glyph, "level": unit.tier,
            "met": "glyph" if own else ("alternate" if alt else None),
            "alternate": unit.alt_glyph, "traditional": unit.traditional,
        })
    return report

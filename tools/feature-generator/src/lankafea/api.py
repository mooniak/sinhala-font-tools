"""High-level orchestration: YAML + font -> gated .fea (-> optional binary)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import generators, injection as inj_mod
from .assembler import assemble
from .inventory import FontInventory
from .scripts import ScriptProfile, get_profile
from .validation import ValidationReport, analyze, flag_non_exporting, gate, summarize
from .verify import check_syntax
from .yamlloader import load_specs, synth_specs


@dataclass
class BuildResult:
    fea: str
    report: ValidationReport
    inventory: FontInventory
    profile: ScriptProfile
    doc: "object" = None            # the gated FeatureDoc (for Glyphs-source writeback)
    raw_snippets: list[str] = field(default_factory=list)
    assign_warnings: list[str] = field(default_factory=list)


# ---- the two candidate models ----------------------------------------------- #
# Sinhala uses the Indic model (generators.py); Tamil has its own (tamil.py), whose
# forms are met by a ligature OR a shape-group alternate.

def _generate(profile: ScriptProfile, specs, inventory: FontInventory, asg):
    if profile.model == "tamil":
        from .tamil import generate_tamil
        return generate_tamil(specs)
    from . import assign as assign_mod
    return generators.generate(specs, alt_names=inventory.glyphs,
                               alt_targets=assign_mod.alt_targets(asg))


def _adapt(doc, profile: ScriptProfile, inventory: FontInventory) -> list[str]:
    if profile.model == "tamil":
        # A designer's own class of the same name narrows a shape group.
        from .tamil import adopt_source_classes
        adopt_source_classes(doc, inventory.source_classes)
        return []
    from .adaptation import add_variant_selection
    return add_variant_selection(doc, profile, inventory)


def _resolve(doc, profile: ScriptProfile, inventory: FontInventory) -> list[dict]:
    if profile.model != "tamil":
        return []
    from .tamil import resolve_requirements
    return resolve_requirements(doc, inventory.glyphs, profile.level)


def _attach_forms(report: ValidationReport, profile: ScriptProfile, forms: list[dict]) -> None:
    if forms:
        report.forms = forms
        report.forms_level = profile.level


def build_fea(
    script: str,
    inventory: FontInventory,
    level: int = 3,
    inject_paths: list[Path] | None = None,
    prefer_feacomposer: bool = False,
    validate: bool = True,
    use_yaml: bool = True,
    assign=None,
    aliases: dict[str, str] | None = None,
    adopt_legacy_names: bool = False,
) -> BuildResult:
    """``assign`` — optional feature assignments (see ``lankafea.assign``): a plain
    dict ``{"groups": [...], "alts": {...}}`` or an ``Assign``.

    ``aliases`` maps a standard glyph name to the font's own name for it, and
    ``adopt_legacy_names`` adds the deterministic pre-standard Tamil renames
    (see ``lankafea.aliases``)."""
    from . import assign as assign_mod
    asg = assign if isinstance(assign, assign_mod.Assign) else assign_mod.parse_assign(assign)
    profile = get_profile(script, level=level)
    # use_yaml=False runs standalone: specs come from the built-in codepoint tables
    # and alternates from the font inventory, with no glyphset YAML at all.
    specs = load_specs(profile) if use_yaml else synth_specs(profile)

    doc = _generate(profile, specs, inventory, asg)

    raw_snips: list[str] = []
    if inject_paths:
        injection = inj_mod.load_injection(inject_paths, profile)
        inj_mod.merge(doc, injection)
        raw_snips = [s.text for s in injection.raw]

    # Noto-model adaptation: shape-group variant selection from harvested classes.
    # (Tamil's shape groups come from the standard; see tamil.py.)
    variant_findings = _adapt(doc, profile, inventory)

    # User routing of rule groups into dlig / ssNN / ... (after every generator
    # and injection has contributed, so any group can be addressed).
    group_warnings, moved = assign_mod.apply_groups(doc, asg)

    # Adopt the font's own names for control glyphs (e.g. U+200D encoded as
    # 'zwj') before gating, so a nonstandard name doesn't kill the rules.
    from .aliases import apply_aliases, compute_aliases
    apply_aliases(doc, compute_aliases(inventory, aliases, adopt_legacy_names,
                                       profile.namespace))

    forms = _resolve(doc, profile, inventory)
    doc, report = gate(doc, inventory.glyphs)
    _attach_forms(report, profile, forms)
    flag_non_exporting(report, inventory.non_exporting)
    report.anchor_findings.extend(variant_findings)
    assign_warnings = (list(asg.warnings) + group_warnings
                       + assign_mod.consumer_warnings(doc, moved))

    fea = assemble(doc, profile.language_systems, prefer_feacomposer=prefer_feacomposer)
    if raw_snips:
        fea = fea.rstrip() + "\n\n# --- injected raw snippets ---\n" + "\n\n".join(raw_snips) + "\n"

    if validate:
        check_syntax(fea, inventory.glyphs)

    return BuildResult(fea=fea, report=report, inventory=inventory,
                       profile=profile, doc=doc, raw_snippets=raw_snips,
                       assign_warnings=assign_warnings)


def validate_font(
    script: str,
    inventory: FontInventory,
    level: int = 3,
    inject_paths: list[Path] | None = None,
    use_yaml: bool = True,
    assign=None,
    aliases: dict[str, str] | None = None,
    adopt_legacy_names: bool = False,
) -> ValidationReport:
    """Dependency validation only: generate candidates, analyze, report.

    Does NOT emit .fea, assemble, or syntax-check — it answers "which rules
    are satisfiable, what blocks the rest, and which glyphs are orphaned".
    """
    profile = get_profile(script, level=level)
    specs = load_specs(profile) if use_yaml else synth_specs(profile)

    from . import assign as assign_mod
    asg = assign if isinstance(assign, assign_mod.Assign) else assign_mod.parse_assign(assign)
    doc = _generate(profile, specs, inventory, asg)
    if inject_paths:
        injection = inj_mod.load_injection(inject_paths, profile)
        inj_mod.merge(doc, injection)

    from .adaptation import anchor_findings, satisfied_sign_counts
    variant_findings = _adapt(doc, profile, inventory)
    assign_mod.apply_groups(doc, asg)

    from .aliases import apply_aliases, compute_aliases
    apply_aliases(doc, compute_aliases(inventory, aliases, adopt_legacy_names,
                                       profile.namespace))

    forms = _resolve(doc, profile, inventory)
    checks, live_class_members = analyze(doc, inventory.glyphs)
    report = summarize(checks, live_class_members)
    _attach_forms(report, profile, forms)
    flag_non_exporting(report, inventory.non_exporting)
    report.anchor_findings = variant_findings + anchor_findings(
        inventory, satisfied_sign_counts(checks, profile), profile, specs)

    from .orphans import find_orphans
    report.orphans = find_orphans(inventory, checks, profile,
                                  class_members=live_class_members)

    # Glyph-info validation: Sinhala dependent vowel signs must be spacing marks.
    from .glyphinfo import check_glyph_info
    gi = check_glyph_info(inventory.glyphs, inventory.glyph_info)
    report.glyph_info_available = gi["available"]
    report.glyph_info_present = gi["present"]
    report.glyph_info_findings = gi["findings"]
    return report


@dataclass
class Assignables:
    """What the assignment dialog can offer for one font."""
    groups: list = field(default_factory=list)     # assign.GroupInfo
    alts: list = field(default_factory=list)       # AltInfo


@dataclass
class AltInfo:
    index: int
    count: int
    examples: list[str]
    default_tag: str


def describe_assignables(
    script: str,
    inventory: FontInventory,
    level: int = 3,
    use_yaml: bool = True,
) -> Assignables:
    """List the rule groups and alternate indices the user may route to dlig/ssNN.

    Groups are the generator's lookups *before* the user's own routing, with
    ``present`` = how many of their rules the font can actually satisfy.
    """
    import copy
    from . import assign as assign_mod
    from .adaptation import add_variant_selection
    from .aliases import apply_aliases, compute_aliases

    profile = get_profile(script, level=level)
    specs = load_specs(profile) if use_yaml else synth_specs(profile)
    doc = _generate(profile, specs, inventory, None)
    _adapt(doc, profile, inventory)
    apply_aliases(doc, compute_aliases(inventory))

    groups = assign_mod.list_groups(doc)
    gated, _ = gate(copy.deepcopy(doc), inventory.glyphs)
    kept = {lk.name: len(lk.rules) for f in gated.features for lk in f.lookups}
    for g in groups:
        g.present = kept.get(g.name, 0)

    alts = [
        AltInfo(idx, len(bases), bases[:6], assign_mod.default_alt_tag(idx))
        for idx, bases in generators.alt_index_counts(
            generators.alt_groups(specs, inventory.glyphs)).items()
    ]
    return Assignables(groups=groups, alts=alts)

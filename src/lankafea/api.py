"""High-level orchestration: YAML + font -> gated .fea (-> optional binary)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import generators, injection as inj_mod
from .assembler import assemble
from .inventory import FontInventory
from .scripts import ScriptProfile, get_profile
from .validation import ValidationReport, analyze, gate, summarize
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


def build_fea(
    script: str,
    inventory: FontInventory,
    level: int = 3,
    inject_paths: list[Path] | None = None,
    prefer_feacomposer: bool = False,
    validate: bool = True,
    use_yaml: bool = True,
) -> BuildResult:
    profile = get_profile(script, level=level)
    # use_yaml=False runs standalone: specs come from the built-in codepoint tables
    # and alternates from the font inventory, with no glyphset YAML at all.
    specs = load_specs(profile) if use_yaml else synth_specs(profile)

    doc = generators.generate(specs, alt_names=inventory.glyphs)

    raw_snips: list[str] = []
    if inject_paths:
        injection = inj_mod.load_injection(inject_paths, profile)
        inj_mod.merge(doc, injection)
        raw_snips = [s.text for s in injection.raw]

    # Noto-model adaptation: shape-group variant selection from harvested classes.
    from .adaptation import add_variant_selection
    variant_findings = add_variant_selection(doc, profile, inventory)

    # Adopt the font's own names for control glyphs (e.g. U+200D encoded as
    # 'zwj') before gating, so a nonstandard name doesn't kill the rules.
    from .aliases import apply_aliases, compute_aliases
    apply_aliases(doc, compute_aliases(inventory))

    doc, report = gate(doc, inventory.glyphs)
    report.anchor_findings.extend(variant_findings)

    fea = assemble(doc, profile.language_systems, prefer_feacomposer=prefer_feacomposer)
    if raw_snips:
        fea = fea.rstrip() + "\n\n# --- injected raw snippets ---\n" + "\n\n".join(raw_snips) + "\n"

    if validate:
        check_syntax(fea, inventory.glyphs)

    return BuildResult(fea=fea, report=report, inventory=inventory,
                       profile=profile, doc=doc, raw_snippets=raw_snips)


def validate_font(
    script: str,
    inventory: FontInventory,
    level: int = 3,
    inject_paths: list[Path] | None = None,
    use_yaml: bool = True,
) -> ValidationReport:
    """Dependency validation only: generate candidates, analyze, report.

    Does NOT emit .fea, assemble, or syntax-check — it answers "which rules
    are satisfiable, what blocks the rest, and which glyphs are orphaned".
    """
    profile = get_profile(script, level=level)
    specs = load_specs(profile) if use_yaml else synth_specs(profile)

    doc = generators.generate(specs, alt_names=inventory.glyphs)
    if inject_paths:
        injection = inj_mod.load_injection(inject_paths, profile)
        inj_mod.merge(doc, injection)

    from .adaptation import (add_variant_selection, anchor_findings,
                             satisfied_sign_counts)
    variant_findings = add_variant_selection(doc, profile, inventory)

    from .aliases import apply_aliases, compute_aliases
    apply_aliases(doc, compute_aliases(inventory))

    checks, live_class_members = analyze(doc, inventory.glyphs)
    report = summarize(checks, live_class_members)
    report.anchor_findings = variant_findings + anchor_findings(
        inventory, satisfied_sign_counts(checks, profile), profile)

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

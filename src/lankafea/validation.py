"""Dependency analysis + presence-gating.

Every candidate rule is a dependency edge: its *input* glyphs and its *output*
glyph must all exist in the font for the rule to be emitted. ``analyze`` walks
every rule once and records exactly which dependencies fail; ``gate`` filters
the document down to satisfiable rules using that same analysis.

This replaces the count-only gating.py report: the validator can now say
"zerowidthjoiner blocks 29,478 rules across akhn/rphf/vatu" instead of
silently dropping them.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field

from .model import FeatureDoc, GlyphClass, Rule

# Fix-it hints keyed by missing glyph name (extend as new hazards are found).
HINTS = {
    "zerowidthjoiner": (
        "add a 'zerowidthjoiner' glyph (U+200D, zero width, empty outline, "
        "exported) — required to match ්‍ sequences; "
        "use `generate --fix-zwj` on a Glyphs source to add it automatically"
    ),
}


def _is_class_ref(token: str) -> bool:
    return token.startswith("@")


def _strip_marker(token: str) -> str:
    """Remove the contextual marker (') that contextual rules carry."""
    return token[:-1] if token.endswith("'") else token


def _resolve_class(name: str, classes: dict[str, GlyphClass], present: set[str],
                   seen: set[str]) -> list[str]:
    """Return the pruned member list of a class (transitively), or [] if dead."""
    if name in seen:  # cycle guard
        return []
    seen.add(name)
    cls = classes.get(name)
    if cls is None:
        return []
    out: list[str] = []
    for m in cls.members:
        if _is_class_ref(m):
            out += _resolve_class(m[1:], classes, present, seen)
        elif m in present:
            out.append(m)
    return out


def rule_str(rule: Rule) -> str:
    """Human-readable one-line rendering of a rule (for reports)."""
    if rule.kind == "pos":
        return f"pos {' '.join(rule.inputs)} {rule.value}"
    out = rule.output
    if isinstance(out, list):
        out = " ".join(out)
    if rule.kind == "alternate":
        return f"sub {rule.inputs[0]} from {out}"
    return f"sub {' '.join(rule.inputs)} by {out}"


@dataclass
class RuleCheck:
    """One candidate rule, evaluated against the font's glyph inventory."""

    feature: str
    lookup: str
    rule: Rule
    missing_inputs: list[str] = field(default_factory=list)
    missing_outputs: list[str] = field(default_factory=list)

    @property
    def satisfiable(self) -> bool:
        return not self.missing_inputs and not self.missing_outputs

    @property
    def missing(self) -> list[str]:
        return self.missing_inputs + self.missing_outputs


@dataclass
class Blocker:
    """One missing glyph (or dead class), ranked by how many rules it blocks."""

    glyph: str
    blocked_rules: int = 0
    features: dict[str, int] = field(default_factory=dict)   # tag -> rule count
    hint: str | None = None
    samples: list[str] = field(default_factory=list)         # up to 3 rule strings


@dataclass
class Orphan:
    """A namespaced glyph present in the font that no satisfiable rule consumes."""

    glyph: str
    reason: str = ""


@dataclass
class FeatureStats:
    candidates: int = 0
    satisfiable: int = 0

    @property
    def blocked(self) -> int:
        return self.candidates - self.satisfiable


@dataclass
class ValidationReport:
    """Full dependency report. Also carries the legacy gate counts."""

    per_feature: dict[str, FeatureStats] = field(default_factory=dict)
    blockers: list[Blocker] = field(default_factory=list)
    orphans: list[Orphan] = field(default_factory=list)
    dead_classes: list[str] = field(default_factory=list)
    anchor_findings: list[str] = field(default_factory=list)
    collisions: list[str] = field(default_factory=list)
    # glyph-info validation (Sinhala spacing marks); see glyphinfo.py.
    glyph_info_findings: list[dict] = field(default_factory=list)
    glyph_info_present: int = 0
    glyph_info_available: bool = False
    # legacy count API (cli.py / api.py compatibility)
    kept_rules: int = 0
    dropped_rules: int = 0
    dropped_lookups: int = 0
    dropped_features: int = 0

    def to_json(self) -> str:
        return json.dumps({
            "per_feature": {
                tag: {"candidates": s.candidates, "satisfiable": s.satisfiable,
                      "blocked": s.blocked}
                for tag, s in sorted(self.per_feature.items())
            },
            "blockers": [
                {"glyph": b.glyph, "blocked_rules": b.blocked_rules,
                 "features": b.features, "hint": b.hint, "samples": b.samples}
                for b in self.blockers
            ],
            "orphans": [{"glyph": o.glyph, "reason": o.reason} for o in self.orphans],
            "dead_classes": self.dead_classes,
            "anchor_findings": self.anchor_findings,
            "collisions": self.collisions,
            "glyph_info": {
                "available": self.glyph_info_available,
                "present": self.glyph_info_present,
                "findings": self.glyph_info_findings,
            },
            "counts": {
                "kept_rules": self.kept_rules,
                "dropped_rules": self.dropped_rules,
                "dropped_lookups": self.dropped_lookups,
                "dropped_features": self.dropped_features,
            },
        }, indent=2, ensure_ascii=False)

    def to_text(self, verbose: bool = False) -> str:
        lines: list[str] = []
        lines.append("== dependency validation ==")
        lines.append(f"rules: {self.kept_rules} satisfiable, "
                     f"{self.dropped_rules} blocked")
        lines.append("")
        lines.append("per feature:")
        for tag, s in sorted(self.per_feature.items()):
            mark = "ok " if s.blocked == 0 else ("--" if s.satisfiable == 0 else "! ")
            lines.append(f"  [{mark:>3}] {tag:<5} {s.satisfiable:>6}/{s.candidates:<6}"
                         f" satisfiable")
        if self.glyph_info_available:
            lines.append("")
            findings = self.glyph_info_findings
            if findings:
                lines.append(f"glyph info — spacing marks with wrong/unset Category "
                             f"(Mark) or Subcategory (Spacing), "
                             f"{len(findings)} of {self.glyph_info_present} present:")
                for f in findings:
                    lines.append(f"  {f['glyph']:<24} {f['reason']}")
            else:
                lines.append(f"glyph info — all {self.glyph_info_present} present "
                             f"spacing marks are Mark/Spacing [ok]")
        if self.blockers:
            lines.append("")
            n = len(self.blockers) if verbose else min(10, len(self.blockers))
            lines.append(f"top blockers (missing glyphs), {n} of {len(self.blockers)}:")
            for b in self.blockers[:n]:
                feats = ", ".join(f"{t}:{c}" for t, c in
                                  sorted(b.features.items(), key=lambda kv: -kv[1]))
                lines.append(f"  {b.glyph:<28} blocks {b.blocked_rules:>6} rules"
                             f"  ({feats})")
                if b.hint:
                    lines.append(f"      hint: {b.hint}")
                if verbose:
                    for s_ in b.samples:
                        lines.append(f"      e.g. {s_}")
        if self.collisions:
            lines.append("")
            lines.append("collisions (hand-authored features with generated tags):")
            for c in self.collisions:
                lines.append(f"  {c}")
        if self.anchor_findings:
            lines.append("")
            lines.append("anchor findings:")
            for a in self.anchor_findings:
                lines.append(f"  {a}")
        if self.orphans:
            lines.append("")
            n = len(self.orphans) if verbose else min(20, len(self.orphans))
            lines.append(f"orphaned glyphs (no rule consumes them), "
                         f"{n} of {len(self.orphans)}:")
            for o in self.orphans[:n]:
                lines.append(f"  {o.glyph}" + (f" — {o.reason}" if o.reason else ""))
        if self.dead_classes:
            lines.append("")
            lines.append(f"dead classes: {', '.join(self.dead_classes)}")
        return "\n".join(lines) + "\n"


# Back-compat alias: api.py/cli.py historically imported GateReport.
GateReport = ValidationReport


def analyze(doc: FeatureDoc, present: set[str]) -> tuple[list[RuleCheck], dict[str, list[str]]]:
    """Walk every rule once; record which glyph deps fail per rule.

    Returns (checks, live_class_members).
    """
    classes = {c.name: c for c in doc.classes}
    live_class_members: dict[str, list[str]] = {}
    for c in doc.classes:
        live_class_members[c.name] = _resolve_class(c.name, classes, present, set())
    live_classes = {name for name, m in live_class_members.items() if m}

    def token_missing(token: str) -> bool:
        t = _strip_marker(token)
        if _is_class_ref(t):
            return t[1:] not in live_classes
        return t not in present

    checks: list[RuleCheck] = []
    for feature in doc.features:
        for lookup in feature.lookups:
            for rule in lookup.rules:
                inputs, outputs = rule.dep_split()
                check = RuleCheck(feature=feature.tag, lookup=lookup.name, rule=rule)
                check.missing_inputs = [
                    _strip_marker(t) for t in inputs if token_missing(t)]
                check.missing_outputs = [
                    _strip_marker(t) for t in outputs if token_missing(t)]
                checks.append(check)
    return checks, live_class_members


def summarize(checks: list[RuleCheck],
              live_class_members: dict[str, list[str]] | None = None,
              sample_limit: int = 3) -> ValidationReport:
    """Aggregate rule checks into a ranked ValidationReport."""
    report = ValidationReport()
    blocker_map: dict[str, Blocker] = {}
    feat_counts: dict[str, FeatureStats] = defaultdict(FeatureStats)

    for check in checks:
        stats = feat_counts[check.feature]
        stats.candidates += 1
        if check.satisfiable:
            stats.satisfiable += 1
            report.kept_rules += 1
            continue
        report.dropped_rules += 1
        for g in dict.fromkeys(check.missing):   # dedupe, keep order
            b = blocker_map.setdefault(g, Blocker(glyph=g, hint=HINTS.get(g)))
            b.blocked_rules += 1
            b.features[check.feature] = b.features.get(check.feature, 0) + 1
            if len(b.samples) < sample_limit:
                b.samples.append(rule_str(check.rule))

    report.per_feature = dict(feat_counts)
    report.blockers = sorted(blocker_map.values(), key=lambda b: -b.blocked_rules)
    if live_class_members is not None:
        report.dead_classes = [n for n, m in live_class_members.items() if not m]
    return report


def gate(doc: FeatureDoc, present: set[str]) -> tuple[FeatureDoc, ValidationReport]:
    """Filter the document to satisfiable rules; return it with the full report.

    Same pruning semantics as the original gating: drop unsatisfiable rules,
    then empty lookups, then empty features; prune class members / mark-filter
    sets to present glyphs; emit only referenced live classes.
    """
    checks, live_class_members = analyze(doc, present)
    report = summarize(checks, live_class_members)

    ok: dict[int, bool] = {id(c.rule): c.satisfiable for c in checks}

    kept_features = []
    for feature in doc.features:
        kept_lookups = []
        for lookup in feature.lookups:
            surviving = [r for r in lookup.rules if ok.get(id(r), False)]
            if surviving:
                lookup.rules = surviving
                if lookup.mark_filter_set:
                    lookup.mark_filter_set = [
                        g for g in lookup.mark_filter_set if g in present
                    ] or None
                kept_lookups.append(lookup)
            else:
                report.dropped_lookups += 1
        if kept_lookups:
            feature.lookups = kept_lookups
            kept_features.append(feature)
        else:
            report.dropped_features += 1

    doc.features = kept_features
    referenced = _referenced_classes(doc)
    doc.classes = [
        GlyphClass(c.name, live_class_members[c.name])
        for c in doc.classes
        if live_class_members[c.name] and c.name in referenced
    ]
    return doc, report


def _referenced_classes(doc: FeatureDoc) -> set[str]:
    refs: set[str] = set()
    for feature in doc.features:
        for lookup in feature.lookups:
            for rule in lookup.rules:
                for t in rule.glyph_refs():
                    t = _strip_marker(t)
                    if _is_class_ref(t):
                        refs.add(t[1:])
    return refs

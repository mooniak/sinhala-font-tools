"""Orphan detection: namespaced glyphs in the font that no rule consumes.

A glyph earns its place in the font by being reachable: encoded (cmap), the
input or output of a satisfiable rule, or a service/component glyph. Everything
else in the script namespace is an orphan — inventory the designer drew that
the feature code never wires up (e.g. aggnni's ``ka_repha-sinh`` set before the
repha-ligature generators existed).
"""

from __future__ import annotations

from .inventory import FontInventory
from .scripts import ScriptProfile
from .validation import Orphan, RuleCheck, _is_class_ref, _strip_marker

# Glyphs that are infrastructure rather than shaping targets.
_SERVICE_PREFIXES = ("_",)
_SERVICE_NAMES = {".notdef", ".null", "NULL", "CR", "nonmarkingreturn"}


def _consumed_glyphs(checks: list[RuleCheck],
                     class_members: dict[str, list[str]] | None = None) -> set[str]:
    """All glyph names referenced by a satisfiable rule (classes expanded)."""
    consumed: set[str] = set()
    members = class_members or {}
    for check in checks:
        if not check.satisfiable:
            continue
        for t in check.rule.glyph_refs():
            t = _strip_marker(t)
            if _is_class_ref(t):
                consumed.update(members.get(t[1:], []))
            else:
                consumed.add(t)
    return consumed


def find_orphans(inventory: FontInventory, checks: list[RuleCheck],
                 profile: ScriptProfile,
                 class_members: dict[str, list[str]] | None = None,
                 extra_consumed: set[str] | None = None) -> list[Orphan]:
    """Namespaced glyphs neither encoded nor consumed by any satisfiable rule.

    ``extra_consumed`` lets callers whitelist glyphs referenced by injected or
    hand-authored feature code (scanned elsewhere).
    """
    ns_suffix = f"-{profile.namespace}"
    consumed = _consumed_glyphs(checks, class_members)
    if extra_consumed:
        consumed |= extra_consumed
    encoded = inventory.encoded_names

    # Blocked-rule cross-reference: glyph -> first blocked rule that would
    # consume it, so the report can say WHY it is unreachable today.
    blocked_consumer: dict[str, str] = {}
    for check in checks:
        if check.satisfiable:
            continue
        for t in check.rule.glyph_refs():
            t = _strip_marker(t)
            if not _is_class_ref(t) and t not in blocked_consumer:
                missing = ", ".join(check.missing)
                from .validation import rule_str
                blocked_consumer[t] = (
                    f"would be consumed by {check.feature} "
                    f"\"{rule_str(check.rule)}\" — blocked by missing: {missing}")

    from .nameparse import parse as parse_name

    orphans: list[Orphan] = []
    for name in sorted(inventory.glyphs):
        if not name.endswith(ns_suffix):
            continue
        base = name[: -len(ns_suffix)]
        if name in consumed or name in encoded:
            continue
        if base in _SERVICE_NAMES or any(base.startswith(p) for p in _SERVICE_PREFIXES):
            continue
        reason = blocked_consumer.get(name, "")
        if not reason:
            parsed = parse_name(name, profile.tables, profile.namespace)
            if parsed:
                reason = f"looks like a {parsed.kind}: {parsed.description}"
        orphans.append(Orphan(glyph=name, reason=reason))
    return orphans

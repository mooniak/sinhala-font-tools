"""User feature assignments: route generated rule groups / alternates to dlig, ssNN, ...

Two independent layers, both optional and both stored per project (the Glyphs
plugin keeps them in ``font.userData``, so they live inside the .glyphspackage):

* **groups** — a *rule group* is one generated Lookup (``TouchLigatures``,
  ``RakarLigatures``, ``VowelLig_abvs`` ...). A group rule moves (or copies) that
  whole lookup into another feature, e.g. ``TouchLigatures -> dlig``.
* **alts** — glyphs named ``base.alt`` / ``base.alt2`` ... form *alternate
  indices* (1, 2, ...). By default index N feeds ``ssNN``; an alt rule sends an
  index to a different tag instead (``2 -> dlig``, ``3 -> ss07``) or keeps it
  out of every feature but ``aalt`` (``none``).

Serialised shape (JSON / plist friendly)::

    {"groups": [{"group": "TouchLigatures", "to": "dlig", "mode": "move"}],
     "alts":   {"1": "ss01", "2": "dlig", "3": "none"}}
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field

from .model import FeatureDoc, Feature, Lookup

# Tags a rule group / alternate index may be routed to.
STYLISTIC_TAGS = [f"ss{n:02d}" for n in range(1, 21)]
TARGET_TAGS = ["dlig", "hlig", "liga", "clig", "calt"] + STYLISTIC_TAGS
NONE_TARGET = "none"          # alts only: reachable through aalt, nothing else
MODES = ("move", "copy")


@dataclass
class GroupRule:
    group: str
    to: str
    mode: str = "move"


@dataclass
class Assign:
    groups: list[GroupRule] = field(default_factory=list)
    alts: dict[int, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not self.groups and not self.alts

    def to_plain(self) -> dict:
        return {
            "groups": [{"group": g.group, "to": g.to, "mode": g.mode}
                       for g in self.groups],
            "alts": {str(k): v for k, v in sorted(self.alts.items())},
        }


def parse_assign(raw) -> Assign:
    """Tolerant parse of the stored shape. Bad entries become warnings, never errors."""
    out = Assign()
    if not raw:
        return out
    try:
        groups = list(raw.get("groups") or [])
        alts = dict(raw.get("alts") or {})
    except (AttributeError, TypeError, ValueError):
        out.warnings.append("assignment settings unreadable; ignored")
        return out

    seen: set[str] = set()
    for entry in groups:
        try:
            name = str(entry["group"]).strip()
            to = str(entry["to"]).strip()
            mode = str(entry.get("mode") or "move").strip()
        except (KeyError, TypeError, AttributeError):
            out.warnings.append(f"bad group rule ignored: {entry!r}")
            continue
        if not name or to not in TARGET_TAGS:
            out.warnings.append(f"group rule {name!r} -> {to!r} ignored (unknown target)")
            continue
        if mode not in MODES:
            mode = "move"
        if name in seen:
            out.warnings.append(f"group {name!r} assigned twice; first rule wins")
            continue
        seen.add(name)
        out.groups.append(GroupRule(name, to, mode))

    for key, tag in alts.items():
        try:
            idx = int(key)
        except (TypeError, ValueError):
            out.warnings.append(f"alternate index {key!r} ignored")
            continue
        tag = str(tag).strip()
        if tag != NONE_TARGET and tag not in TARGET_TAGS:
            out.warnings.append(f"alternate {idx} -> {tag!r} ignored (unknown target)")
            continue
        if idx >= 1:
            out.alts[idx] = tag
    return out


def default_alt_tag(idx: int) -> str:
    return f"ss{idx:02d}"


def alt_targets(assign: Assign | None) -> dict[int, str]:
    """Index -> tag overrides (only those that differ from the ssNN default)."""
    if not assign:
        return {}
    return {i: t for i, t in assign.alts.items() if t != default_alt_tag(i)}


# --------------------------------------------------------------------------- #
# Rule groups
# --------------------------------------------------------------------------- #

@dataclass
class GroupInfo:
    name: str
    feature: str                 # feature the generator put it in
    rules: int                   # candidate rules generated
    comment: str = ""
    present: int | None = None   # rules whose glyphs exist in the font (if known)


def list_groups(doc: FeatureDoc) -> list[GroupInfo]:
    out = []
    for f in doc.features:
        for lk in f.lookups:
            out.append(GroupInfo(lk.name, f.tag, len(lk.rules), lk.comment or ""))
    return out


def _glyph_tokens(tokens) -> set[str]:
    return {t for t in tokens if t and not t.startswith("@")}


def _rule_io(lookup: Lookup) -> tuple[set[str], set[str]]:
    ins: set[str] = set()
    outs: set[str] = set()
    for r in lookup.rules:
        i, o = r.dep_split()
        ins |= _glyph_tokens(i)
        outs |= _glyph_tokens(o)
    return ins, outs


def apply_groups(doc: FeatureDoc, assign: Assign) -> tuple[list[str], list[tuple[Lookup, str, str]]]:
    """Move/copy lookups per the group rules.

    Returns ``(warnings, moved)``; pass ``moved`` to ``consumer_warnings`` AFTER
    gating, when only rules the font can really satisfy are left.
    """
    warnings: list[str] = []
    moved: list[tuple[Lookup, str, str]] = []     # (lookup, from_tag, to_tag)

    for rule in assign.groups:
        sources = [(f, lk) for f in doc.features for lk in f.lookups
                   if lk.name == rule.group]
        if not sources:
            warnings.append(f"group {rule.group!r} was not generated for this font; skipped")
            continue
        for feature, lookup in sources:
            if feature.tag == rule.to and rule.mode == "move":
                continue                                 # already there
            target = doc.feature(rule.to)
            if rule.mode == "copy":
                clone = copy.deepcopy(lookup)
                clone.name = f"{lookup.name}_{rule.to}"
                target.lookups.append(clone)
            else:
                feature.lookups.remove(lookup)
                target.lookups.append(lookup)
                moved.append((lookup, feature.tag, rule.to))

    doc.features = [f for f in doc.features if f.lookups]
    return warnings, moved


def consumer_warnings(doc: FeatureDoc, moved: list[tuple[Lookup, str, str]]) -> list[str]:
    """A moved group's output glyphs may feed lookups that stayed in their old
    feature: with the new feature off they would see unformed glyphs. Warn."""
    warnings: list[str] = []
    live = {id(lk) for f in doc.features for lk in f.lookups}
    moved_ids = {id(m[0]) for m in moved}
    for lookup, from_tag, to_tag in moved:
        if id(lookup) not in live:
            continue                                      # nothing survived gating
        _ins, outs = _rule_io(lookup)
        consumers = sorted({
            other.name
            for f in doc.features for other in f.lookups
            if id(other) not in moved_ids and other is not lookup
            and (_rule_io(other)[0] & outs)
        })
        if consumers:
            warnings.append(
                f"{lookup.name} ({from_tag} -> {to_tag}) forms glyphs used by "
                f"{', '.join(consumers)}; those only see them while {to_tag} is on")
    return warnings

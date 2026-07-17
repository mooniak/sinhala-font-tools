"""Merge user-authored custom rules/sets into the generated IR.

Two input forms (see the project plan):

* ``*.yaml`` — declarative: ``classes:``, ``lookups:`` (each with ``feature``,
  ``flags``, ``rules``), and an optional ``order`` anchor. Merged into the IR
  BEFORE gating, so injected rules are presence-filtered exactly like generated
  ones. This is the home for the hand-tuned shape-group / ssNN lookups that are not
  derivable from the base YAML.
* ``*.fea`` — raw escape hatch: appended verbatim after the generated features
  (NOT gated — documented limitation; validate the whole file with verify.check_syntax).

Bare glyph names in inject files are namespaced automatically (``va`` -> ``va-sinh``);
tokens already suffixed, ``@class`` refs, and control glyphs are left untouched.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .model import FeatureDoc, Feature, Lookup, GlyphClass, Rule
from .names import NO_NAMESPACE
from .scripts import ScriptProfile


@dataclass
class RawSnippet:
    source: str
    text: str


@dataclass
class Injection:
    doc: FeatureDoc = field(default_factory=FeatureDoc)
    raw: list[RawSnippet] = field(default_factory=list)


_CONTROL_NAMES = set(NO_NAMESPACE.values()) | {"space"}


def _apply_ns(token: str, namespace: str) -> str:
    if token.startswith("@"):
        return token
    contextual = token.endswith("'")
    core = token[:-1] if contextual else token
    if (core.endswith(f"-{namespace}") or core in _CONTROL_NAMES
            or "-" in core.split(".")[0]):  # already looks namespaced/qualified
        out = core
    else:
        out = f"{core}-{namespace}"
    return out + "'" if contextual else out


def _rule_from_spec(spec: dict, namespace: str) -> Rule:
    if "pos" in spec:
        return Rule(kind="pos",
                    inputs=[_apply_ns(spec["pos"], namespace)],
                    value=spec.get("value", "<0 0 0 0>"))
    sub = spec["sub"]
    inputs = [_apply_ns(t, namespace) for t in (sub if isinstance(sub, list) else [sub])]
    by = spec.get("by")
    if isinstance(by, list):
        out = [_apply_ns(t, namespace) for t in by]
        kind = "multiple" if len(inputs) == 1 else "ligature"
    else:
        out = _apply_ns(by, namespace) if by else None
        kind = "single" if len(inputs) == 1 else "ligature"
    return Rule(kind=kind, inputs=inputs, output=out, comment=spec.get("comment"))


def load_injection(paths: list[Path], profile: ScriptProfile) -> Injection:
    inj = Injection()
    ns = profile.namespace
    for path in paths:
        if path.suffix.lower() == ".fea":
            inj.raw.append(RawSnippet(str(path), path.read_text(encoding="utf-8")))
            continue
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for cname, members in (data.get("classes") or {}).items():
            inj.doc.classes.append(GlyphClass(
                cname, [_apply_ns(m, ns) for m in members]))
        for lk_spec in (data.get("lookups") or []):
            tag = lk_spec.get("feature")
            if not tag:
                continue
            lookup = Lookup(
                name=lk_spec.get("name", f"Injected_{tag}"),
                flags=list(lk_spec.get("flags", [])),
                mark_filter_set=(
                    [_apply_ns(m, ns) for m in lk_spec["markFilteringSet"]]
                    if lk_spec.get("markFilteringSet") else None),
                comment=lk_spec.get("comment"),
            )
            for r in lk_spec.get("rules", []):
                lookup.rules.append(_rule_from_spec(r, ns))
            inj.doc.feature(tag).lookups.append(lookup)
    return inj


def merge(base: FeatureDoc, inj: Injection) -> FeatureDoc:
    """Fold injected classes/lookups into the generated doc (pre-gating)."""
    base.classes.extend(inj.doc.classes)
    for injected in inj.doc.features:
        target = base.feature(injected.tag)
        target.lookups.extend(injected.lookups)
    return base


def collect_paths(inject_dir: Path | None, files: list[Path] | None) -> list[Path]:
    paths: list[Path] = []
    if inject_dir and inject_dir.is_dir():
        paths += sorted(p for p in inject_dir.iterdir()
                        if p.suffix.lower() in (".yaml", ".yml", ".fea"))
    if files:
        paths += files
    return paths

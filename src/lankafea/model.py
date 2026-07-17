"""Engine-agnostic intermediate representation.

Generators, injection and gating all operate on this IR so they are independent of
the feacomposer / feaLib backend. The assembler is the only consumer that turns IR
into .fea text.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class GlyphClass:
    """A named glyph class: @name = [members]."""

    name: str
    members: list[str]


@dataclass
class Rule:
    """A single substitution or positioning rule.

    kind:
      - "ligature": sub <inputs> by <output>            (GSUB type 4)
      - "single":   sub <inputs[0]> by <output>         (GSUB type 1)
      - "multiple": sub <inputs[0]> by <outputs>        (GSUB type 2, output is a list)
      - "alternate":sub <inputs[0]> from <alt_class>    (GSUB type 3, aalt)
      - "pos":      pos <inputs[0]> <value>             (GPOS single)
    ``inputs`` and members may reference classes as "@name".
    """

    kind: str
    inputs: list[str]
    output: str | list[str] | None = None
    value: str | None = None          # for kind == "pos", e.g. "<0 0 -90 0>"
    comment: str | None = None

    def glyph_refs(self) -> list[str]:
        """Every glyph/class token this rule references."""
        refs = list(self.inputs)
        if isinstance(self.output, list):
            refs += self.output
        elif isinstance(self.output, str):
            refs.append(self.output)
        return refs

    def dep_split(self) -> tuple[list[str], list[str]]:
        """Dependency view of the rule: (input glyph deps, output glyph deps)."""
        outputs: list[str] = []
        if isinstance(self.output, list):
            outputs = list(self.output)
        elif isinstance(self.output, str):
            outputs = [self.output]
        return list(self.inputs), outputs


@dataclass
class Lookup:
    name: str
    rules: list[Rule] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)      # e.g. ["IgnoreMarks"]
    mark_filter_set: list[str] | None = None            # UseMarkFilteringSet members
    comment: str | None = None


@dataclass
class Feature:
    tag: str
    lookups: list[Lookup] = field(default_factory=list)


@dataclass
class FeatureDoc:
    """The whole generated document: classes + ordered features."""

    classes: list[GlyphClass] = field(default_factory=list)
    features: list[Feature] = field(default_factory=list)

    def feature(self, tag: str) -> Feature:
        for f in self.features:
            if f.tag == tag:
                return f
        f = Feature(tag)
        self.features.append(f)
        return f

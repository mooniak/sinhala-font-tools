"""Noto's three-tier ිී (ispilla) i-vowel system, mined from the anchor reference.

`ි`/`ී` are not one shape: Noto Sans Sinhala processes them through three tiers
(docs/sinhala.min.yaml `reading`):

  fused     — a precomposed ligature glyph exists (khI-sinh, yI-sinh, ttI-sinh …);
              the i-vowel is drawn into the base. Stays drawn.
  alternate — a per-class contextual alternate mark (`isign-sinh.altN`) attached
              by the iVowel anchor. The base belongs to an `iVowelAltN` OT class
              (iVowelAlt→.alt1, iVowelAlt3→.alt3, …). Composite: base + alternate.
  default   — the plain `isign-sinh` attached by the iVowel anchor. Composite.

So `kI-sinh` = ka + `isign-sinh.alt3` (ka ∈ iVowelAlt3), `ghI-sinh` = gha +
`isign-sinh` (default), while `yI-sinh` is a fused ligature that stays drawn.

Mined live from the anchor font's OT classes and glyph inventory, so it tracks
that font rather than a hardcoded table. If the anchor font has no `iVowelAltN`
classes, every non-fused form falls back to the default `isign-sinh`.
"""
import re

from . import glyphsio

_CLASS_RE = re.compile(r"^iVowelAlt(\d*)$")


class IspillaModel:
    def __init__(self, anchor_font):
        self.names = {g.name for g in anchor_font.glyphs}
        self.alt_suffix = {}  # base glyph name -> ".altN" ("" = default)
        for cls in getattr(anchor_font, "classes", []) or []:
            m = _CLASS_RE.match(cls.name or "")
            if not m:
                continue
            suffix = f".alt{m.group(1) or '1'}"  # bare iVowelAlt == .alt1
            for gname in (cls.code or "").split():
                self.alt_suffix[gname.strip()] = suffix

    def is_fused(self, stem, long=False):
        """True if the anchor font precomposes this i-form as a ligature glyph."""
        target = f"{stem}{'Ii' if long else 'I'}-sinh"
        return target in self.names

    def component(self, base, long=False):
        """The i/ii sign component a composite should reference for this base."""
        sign = "iisign-sinh" if long else "isign-sinh"
        return sign + self.alt_suffix.get(base, "")

    def alternates_used(self, bases):
        """The set of i/ii sign glyphs (incl. alternates) referenced across the
        given base glyph names — for documenting the required sign inventory."""
        out = set()
        for base in bases:
            out.add(self.component(base, long=False))
            out.add(self.component(base, long=True))
        return sorted(out)

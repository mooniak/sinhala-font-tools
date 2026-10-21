"""Contextual ු ූ / ්‍ර sign variants, mined from the anchor reference's GSUB.

Noto Sans Sinhala has no precomposed `sU-sinh` / `ttRa-sinh`; it picks a sign
variant by the preceding base at shaping time:

    sub @saShapeGroup usign-sinh' by usign-sinh.alt2;
    sub @rakarVaShapeGroup rasign-sinh' by rasign-sinh.alt2;

So a composite built from the map must reference that variant, not the plain
sign: `sU-sinh` = sa + the medium u-sign, `ttRa-sinh` = tta + the medium rakar.

Rules are read in feature-code order and the first match per (base, sign) wins,
as in the shaper. Only rules whose output is a variant of the same sign are
kept (`rasign usign' -> aesign.low` and similar are a different mechanism).

Noto's `.altN` suffixes are opaque, so each is given a semantic SLOT (judged
from the outlines: tail length for u, bowl width for rakar). Components use
`<sign>.<slot>` — e.g. `usign-sinh.medium` — matching the short/medium/long
names Dedigama and Maname already use. An alternate missing from SLOTS keeps
its Noto suffix, so a new variant shows up rather than being dropped.
"""
import re

SIGNS = ("usign-sinh", "uusign-sinh", "rasign-sinh")

# Noto alternate -> semantic slot.
SLOTS = {
    "usign-sinh.alt1": "tta",       # default length, joins high (ච ට ථ ඵ ම ව)
    "usign-sinh.alt2": "medium",
    "usign-sinh.alt3": "long",
    "uusign-sinh.alt1": "tta",
    "uusign-sinh.alt2": "medium",
    "uusign-sinh.alt3": "long",
    "rasign-sinh.alt1": "pa",       # pa-shaped bowls (ප ෂ ෆ)
    "rasign-sinh.alt2": "medium",
    "rasign-sinh.alt3": "long",
    "rasign-sinh.alt4": "short",
    "rasign-sinh.alone": "alone",   # spacing, no _rakar anchor (ල ර ළ)
}

_RULE_RE = re.compile(
    r"sub\s+(?P<ctx>@[\w.-]+|\[[^\]]*\]|[\w.-]+)\s+"
    r"(?P<sign>(?:u|uu|ra)sign-sinh)'\s+by\s+(?P<out>[\w.-]+)\s*;"
)


def slot_of(noto_name):
    if noto_name in SLOTS:
        return SLOTS[noto_name]
    return noto_name.split(".", 1)[1]


def variant_name(sign, slot):
    return sign if slot is None else f"{sign}.{slot}"


class SignVariants:
    def __init__(self, anchor_font):
        names = {g.name for g in anchor_font.glyphs}
        classes = {c.name: (c.code or "").split() for c in (anchor_font.classes or [])}
        self.slot = {}       # (base, sign) -> slot
        self.noto = {}       # semantic variant name -> Noto glyph name
        for fea in anchor_font.features or []:
            for m in _RULE_RE.finditer(_strip_comments(fea.code or "")):
                sign, out = m.group("sign"), m.group("out")
                if not out.startswith(sign + ".") or out not in names:
                    continue
                slot = slot_of(out)
                self.noto[variant_name(sign, slot)] = out
                for base in _expand(m.group("ctx"), classes):
                    self.slot.setdefault((base, sign), slot)

    def component(self, base, sign):
        """The sign glyph a composite of `base` + `sign` should reference."""
        if sign not in SIGNS:
            return sign
        return variant_name(sign, self.slot.get((base, sign)))

    def table(self):
        """{variant name: {sign, slot, noto}} — the variant inventory, so a
        consumer can fall back to the plain sign when a font lacks one."""
        out = {}
        for name, noto in sorted(self.noto.items()):
            sign, slot = name.split(".", 1)
            out[name] = {"sign": sign, "slot": slot, "noto": noto}
        return out


def _expand(ctx, classes):
    if ctx.startswith("@"):
        return classes.get(ctx[1:], [])
    if ctx.startswith("["):
        return ctx[1:-1].split()
    return [ctx]


def _strip_comments(code):
    return re.sub(r"#[^\n]*", "", code)

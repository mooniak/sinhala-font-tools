"""Build a minimal but shapeable test font whose glyphs use LankaGlyphset names.

Produces a real .ttf (empty outlines, correct cmap + GDEF categories) so the full
generate -> strip -> compile -> shape pipeline can be exercised end-to-end.
"""

from __future__ import annotations

from pathlib import Path

from fontTools.fontBuilder import FontBuilder
from fontTools.ttLib import newTable

from lankafea.scripts import ScriptProfile
from lankafea.yamlloader import load_specs
from lankafea.names import with_ns


def aggnni_like_extras(profile: ScriptProfile) -> list[str]:
    """Per-consonant repha ligatures + yasign sign family, as found in the
    fontmaster fonts (aggnni-font is the reference)."""
    ns = profile.namespace
    bare = [
        "ka_repha", "kha_repha", "ga_repha", "ma_repha", "sa_repha", "dU_repha",
        "yasign_usign", "yasign_iisign", "yasign_aasign",
        "yasign_virama", "yasign_repha", "yasign_aasign_virama",
        "kRa", "dRa",
    ]
    return [with_ns(n, ns) for n in bare]


def build_test_font(profile: ScriptProfile, out_path: Path,
                    extra_glyphs: list[str] | None = None,
                    with_zwj: bool = True) -> Path:
    specs = load_specs(profile)
    t = profile.tables
    ns = profile.namespace

    # Glyph inventory: every glyph the YAML declares + control/generic glyphs.
    # (The kernel YAML itself declares zerowidthjoiner, so the no-ZWJ variant
    # must actively exclude it.)
    skip = set() if with_zwj else {"zerowidthjoiner", "zerowidthnonjoiner"}
    glyph_names = [".notdef"]
    seen = {".notdef"}
    for g in specs.glyphs:
        if g.full_name not in seen and g.full_name not in skip:
            seen.add(g.full_name)
            glyph_names.append(g.full_name)
    control = ["zerowidthjoiner"] if with_zwj else []
    for name in [*control, with_ns("touch", ns),
                 with_ns("rasign", ns), with_ns("repha", ns), with_ns("yasign", ns),
                 *(extra_glyphs or [])]:
        if name not in seen:
            seen.add(name)
            glyph_names.append(name)

    # cmap: codepoint -> nominal glyph. Consonants -> base(with 'a'), signs -> *sign,
    # independent vowels -> name, plus virama / ZWJ.
    cmap: dict[int, str] = {}

    def put(cp: int, name: str):
        if name in seen:
            cmap[cp] = name

    for cp, stem in t.consonants.items():
        put(cp, with_ns(stem + "a", ns))
    for cp, name in t.independent_vowels.items():
        put(cp, with_ns(name, ns))
    for cp, alone in t.sign_alone.items():
        put(cp, with_ns(alone, ns))
    if with_zwj:
        cmap[0x200D] = "zerowidthjoiner"

    upem = 1000
    fb = FontBuilder(upem, isTTF=True)
    fb.setupGlyphOrder(glyph_names)
    fb.setupCharacterMap(cmap)
    advances = {n: (600 if n != ".notdef" else 500) for n in glyph_names}
    # Empty outlines.
    from fontTools.ttLib.tables._g_l_y_f import Glyph
    glyf = {n: Glyph() for n in glyph_names}
    fb.setupGlyf(glyf)
    fb.setupHorizontalMetrics({n: (advances[n], 0) for n in glyph_names})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({"familyName": f"LankaTest-{ns}", "styleName": "Regular"})
    fb.setupOS2()
    fb.setupPost()
    fb.font.save(str(out_path))
    return out_path


def build_test_glyphs_source(profile: ScriptProfile, out_path: Path):
    """A minimal Glyphs source (.glyphs or .glyphspackage by extension) whose glyphs
    use LankaGlyphset names — enough to exercise the source read/writeback path."""
    from glyphsLib.classes import GSFont, GSGlyph, GSFontMaster

    specs = load_specs(profile)
    font = GSFont()
    font.familyName = f"LankaTest-{profile.namespace}"
    master = GSFontMaster()
    master.name = "Regular"
    font.masters.append(master)

    names = [g.full_name for g in specs.glyphs]
    for extra in ["zerowidthjoiner", with_ns("touch", profile.namespace),
                  with_ns("rasign", profile.namespace),
                  with_ns("repha", profile.namespace),
                  with_ns("yasign", profile.namespace)]:
        names.append(extra)
    seen = set()
    for name in names:
        if name in seen:
            continue
        seen.add(name)
        font.glyphs.append(GSGlyph(name))

    from lankafea.glyphspackage import save_source
    save_source(font, out_path)
    return out_path

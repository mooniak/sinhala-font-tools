"""Refresh the generated half of the Glyphs plugin bundle.

glyphs-plugin/SinhalaGlyphBuilder.glyphsPlugin is checked in. Its plugin.py,
add_glyphs.py, Info.plist and loader binary are hand-maintained; everything
under Contents/Resources/sinhala_glyph_builder/ is generated here:

  buildplan.py     verbatim copy of this package's composite planning module
  catalogue.py     verbatim copy of this package's catalogue/dependency module
  map.json         the map sections the plugin reads (so the bundle reads no
                   repo paths and needs no PyYAML)
  catalogue.json   copy of tools/_generated/sinhala-glyph-catalogue.json
                   (built by glyph-catalogue/build.js)
"""
import json
from pathlib import Path

from .lanka_data import PREBASE_SIGNS, REPO_ROOT, SPACING_SIGNS

HERE = Path(__file__).resolve().parents[1]
PLUGIN = HERE / "glyphs-plugin" / "SinhalaGlyphBuilder.glyphsPlugin"
CORE = PLUGIN / "Contents" / "Resources" / "sinhala_glyph_builder"
VENDORED = ("buildplan.py", "catalogue.py")
CATALOGUE_JS = HERE / "glyph-catalogue" / "build.js"
CATALOGUE_JSON = REPO_ROOT / "tools" / "_generated" / "sinhala-glyph-catalogue.json"

_PY_HEADER = ("# GENERATED copy of tools/composite-map/composite_map/{name} — edit that\n"
              "# file, then run:  python -m composite_map build-plugin\n")


def payload(map_data):
    return {
        "meta": map_data.get("meta", {}),
        "sign_variants": map_data.get("atoms", {}).get("sign_variants", {}),
        "spacing_signs": SPACING_SIGNS,
        "prebase_signs": PREBASE_SIGNS,
        "composites": {n: {"components": s["components"], "tier": s["tier"]}
                       for n, s in map_data.get("composites", {}).items()},
        "keep_drawn": map_data.get("keep_drawn", {}),
        "review": {n: r.get("guess") for n, r in map_data.get("review", {}).items()},
    }


def outputs(map_data):
    """-> {path: text} for every generated file in the bundle."""
    src = Path(__file__).resolve().parent
    out = {CORE / "__init__.py": _PY_HEADER.format(name="(package)")}
    for name in VENDORED:
        out[CORE / name] = _PY_HEADER.format(name=name) + (src / name).read_text(encoding="utf-8")
    out[CORE / "map.json"] = json.dumps(payload(map_data), ensure_ascii=False, indent=1) + "\n"
    if not CATALOGUE_JSON.exists():
        raise FileNotFoundError(f"{CATALOGUE_JSON} — run node {CATALOGUE_JS}")
    out[CORE / "catalogue.json"] = CATALOGUE_JSON.read_text(encoding="utf-8")
    return out


def stale(map_data):
    return [p for p, text in outputs(map_data).items()
            if not p.exists() or p.read_text(encoding="utf-8") != text]


def write(map_data):
    written = []
    for p, text in outputs(map_data).items():
        if p.exists() and p.read_text(encoding="utf-8") == text:
            continue
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        written.append(p)
    return written

"""Refresh the generated half of the Glyphs plugin bundle.

glyphs-plugin/SinhalaSpacing.glyphsPlugin is checked in. Its plugin.py,
Info.plist and loader binary are hand-maintained; everything under
Contents/Resources/sinhala_spacing/ is generated here:

  keyplan.py, names.py   verbatim copies of this package's pure modules
  scheme.json            the scheme sections the plugin reads, plus the
                         lanka-glyphsets char -> name table names.py needs and
                         each composite's base glyph (from sinhala-composites.yaml,
                         for keyplan's base fallback) — so the bundle reads no
                         repo paths and needs no PyYAML
"""
import json
from pathlib import Path

import yaml

from . import names

COMPOSITES_YAML = names.REPO_ROOT / "sinhala-composites.yaml"

PLUGIN = Path(__file__).resolve().parents[1] / "glyphs-plugin" / "SinhalaSpacing.glyphsPlugin"
CORE = PLUGIN / "Contents" / "Resources" / "sinhala_spacing"
VENDORED = ("keyplan.py", "names.py")
SECTIONS = ("meta", "classes", "forms", "exceptions")

_PY_HEADER = ("# GENERATED copy of tools/spacing-map/spacing_map/{name} — edit that\n"
              "# file, then run:  python -m spacing_map build-plugin\n")


def outputs(scheme):
    """-> {path: text} for every generated file in the bundle."""
    src = Path(__file__).resolve().parent
    out = {CORE / "__init__.py": _PY_HEADER.format(name="(package)")}
    for name in VENDORED:
        out[CORE / name] = _PY_HEADER.format(name=name) + (src / name).read_text(encoding="utf-8")
    payload = {k: scheme[k] for k in SECTIONS if k in scheme}
    payload["lgs_names"] = names.lgs_char_to_name()
    payload["composites"] = composite_bases()
    out[CORE / "scheme.json"] = json.dumps(payload, ensure_ascii=False, indent=1) + "\n"
    return out


def composite_bases(path=COMPOSITES_YAML):
    """Composite glyph name -> its base (first) component."""
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return {n: s["components"][0] for n, s in sorted((data.get("composites") or {}).items())}


def stale(scheme):
    """Generated files whose content differs from what would be written."""
    return [p for p, text in outputs(scheme).items()
            if not p.exists() or p.read_text(encoding="utf-8") != text]


def write(scheme):
    written = []
    for p, text in outputs(scheme).items():
        if p.exists() and p.read_text(encoding="utf-8") == text:
            continue
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        written.append(p)
    return written

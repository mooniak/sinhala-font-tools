"""Per-font settings: the one file a font repo keeps for lankafea.

A font's source sits in ``sources/``; its lankafea settings sit next to it in
``sources/lankafea.yaml``, keyed by script so a source with both scripts keeps one
file::

    sinhala:
      inject: [lankafea]            # inject dirs/files, relative to this file
      assign:                       # feature routing (lankafea.assign)
        groups:
          - {group: DaShape, to: dlig, mode: copy}
          - {group: AnusvaraSha, to: ss03}
      dist: -113                    # touching-cluster shift (GPOS dist)
      numerals: {lith: ss07, lithTens: rlig, archaic: ss08}
      featureNames: {ss01: Sinhala Da forms}

Everything is optional. ``inject`` and ``assign`` are the existing mechanisms
(``--inject``, ``--assign``); ``dist``, ``numerals`` and ``featureNames`` are
generator options. See docs/font-config.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

CONFIG_NAME = "lankafea.yaml"
KNOWN_KEYS = {"inject", "assign", "dist", "numerals", "featureNames"}


@dataclass
class FontConfig:
    path: Path | None = None
    inject_paths: list[Path] = field(default_factory=list)
    assign: dict | None = None
    options: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def find_config(font_path: Path | str) -> Path | None:
    """``sources/lankafea.yaml`` beside a source, if there is one."""
    candidate = Path(font_path).resolve().parent / CONFIG_NAME
    return candidate if candidate.is_file() else None


def load_font_config(path: Path | str | None, script: str) -> FontConfig:
    """Read one script's settings. A missing file or script section is no settings."""
    if not path:
        return FontConfig()
    path = Path(path)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    section = data.get(script) or {}
    cfg = FontConfig(path=path)
    for key in section:
        if key not in KNOWN_KEYS:
            cfg.warnings.append(f"{path.name}: unknown setting {script}.{key} ignored")

    from .injection import collect_paths
    inject = section.get("inject") or []
    for entry in ([inject] if isinstance(inject, str) else inject):
        p = (path.parent / entry).resolve()
        if p.is_dir():
            cfg.inject_paths += collect_paths(p, None)
        elif p.is_file():
            cfg.inject_paths.append(p)
        else:
            cfg.warnings.append(f"{path.name}: inject path {entry!r} not found")

    cfg.assign = section.get("assign") or None
    for key in ("dist", "numerals", "featureNames"):
        if section.get(key) is not None:
            cfg.options[key] = section[key]
    return cfg

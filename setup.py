"""Build shim: copy the canonical glyphset YAMLs into the package at build time.

All project metadata lives in pyproject.toml. This file exists only to bundle
the glyphset standard into the wheel/sdist without duplicating it in the repo.

The single source of truth is the repository's top-level ``glyphsets/`` directory
(``../../glyphsets`` from here). We do NOT keep a committed copy under
``src/mnik/lankaglyphsets/data/glyphsets/`` — it would drift. Instead a custom
``build_py`` copies the YAMLs in just before the package is assembled, so an
installed wheel is self-contained (see ``scripts.glyphsets_dir()``), while a
source checkout falls back to the repo's ``glyphsets/`` directly.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py as _build_py

_HERE = Path(__file__).resolve().parent
_CANONICAL = _HERE.parents[1] / "glyphsets"          # lanka-glyphsets/glyphsets
_BUNDLE_REL = "mnik/lankaglyphsets/data/glyphsets"    # under src/


def _sync_glyphsets(dest_root: Path) -> None:
    dest = dest_root / _BUNDLE_REL
    if not _CANONICAL.is_dir():
        # No canonical dir (e.g. building from an sdist that already carries the
        # bundle): leave whatever is present in place.
        return
    dest.mkdir(parents=True, exist_ok=True)
    for yaml in sorted(_CANONICAL.glob("*.yaml")):
        shutil.copy2(yaml, dest / yaml.name)


class build_py(_build_py):
    def run(self) -> None:
        # Copy into the source tree first so setuptools' package-data glob
        # (declared in pyproject.toml) picks the YAMLs up, then build normally.
        _sync_glyphsets(_HERE / "src")
        super().run()


setup(cmdclass={"build_py": build_py})

"""The Glyphs plugin writes into the LIVE font through the Glyphs API, not glyphsLib, so
it has its own copy of the writeback. This runs that code against a stand-in for the
Glyphs API and checks it does exactly what lankafea.glyphsource does (R1)."""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest

from lankafea.api import build_fea
from lankafea.glyphsource import inventory_from_glyphs, write_features_to_glyphs
from lankafea.glyphspackage import load_source
from lankafea.ownership import owner_script
from test_multiscript import (HAND_SINH_AKHN, HAND_TAML_AKHN, mixed_source)

PLUGIN = (Path(__file__).resolve().parents[1] / "glyphs-plugin" / "LankaFeatures.glyphsPlugin"
          / "Contents" / "Resources" / "plugin.py")


class _Obj:
    def __init__(self, name=None, code=None):
        self.name, self.code = name, code


class GSFeature(_Obj): ...
class GSClass(_Obj): ...
class GSFeaturePrefix(_Obj): ...


class FakeGlyph:
    def __init__(self, name):
        self.name, self.export = name, True


class FakeFont:
    def __init__(self, glyphs, features=(), prefixes=(), classes=()):
        self.glyphs = [FakeGlyph(n) for n in glyphs]
        self.features = list(features)
        self.featurePrefixes = list(prefixes)
        self.classes = list(classes)


@pytest.fixture()
def plugin(monkeypatch):
    """Import plugin.py with the macOS / Glyphs modules it needs replaced by stand-ins."""
    def module(name, **attrs):
        m = types.ModuleType(name)
        m.__dict__.update(attrs)
        monkeypatch.setitem(sys.modules, name, m)
        return m

    monkeypatch.setattr(sys, "dont_write_bytecode", True)     # no __pycache__ in the plugin
    anything = type("Any", (), {})
    module("objc", python_method=lambda f: f)
    module("AppKit", NSAlert=anything, NSMenu=anything, NSMenuItem=anything,
           NSOnState=1, NSOffState=0, NSTextField=anything)
    module("Foundation", NSObject=object)
    module("GlyphsApp", Glyphs=anything(), GSGlyph=anything, GSFeature=GSFeature,
           GSClass=GSClass, GSFeaturePrefix=GSFeaturePrefix, GLYPH_MENU=0,
           UPDATEINTERFACE=0, DOCUMENTOPENED=0, DOCUMENTWASSAVED=0, DOCUMENTACTIVATED=0)
    module("GlyphsApp.plugins", GeneralPlugin=anything)
    module("PyObjCTools", AppHelper=anything)
    sys.modules["PyObjCTools"].AppHelper = anything
    spec = importlib.util.spec_from_file_location("lanka_plugin_under_test", PLUGIN)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["lanka_plugin_under_test"] = mod
    spec.loader.exec_module(mod)
    yield mod
    sys.modules.pop("lanka_plugin_under_test", None)


def fake_from_source(src):
    """The same font the library would load, as the plugin sees it."""
    f = load_source(src)
    return FakeFont(
        [g.name for g in f.glyphs],
        [GSFeature(x.name, x.code) for x in f.features],
        [GSFeaturePrefix(x.name, x.code) for x in f.featurePrefixes],
        [GSClass(x.name, x.code) for x in f.classes])


def result_for(script, inv):
    level = 3 if script == "sinhala" else 2
    return build_fea(script, inv, level=level)


def snapshot(features, prefixes, classes):
    return (sorted((f.name, f.code) for f in features),
            sorted((p.name, p.code) for p in prefixes),
            sorted((c.name, c.code) for c in classes))


def test_plugin_and_library_write_the_same_thing(plugin, tmp_path):
    """Sinhala, then Tamil, into a source with hand-written code: both writers agree."""
    src = mixed_source(tmp_path)
    inv = inventory_from_glyphs(src)
    sinh, taml = result_for("sinhala", inv), result_for("tamil", inv)

    # library
    a, b = tmp_path / "a.glyphs", tmp_path / "b.glyphs"
    write_features_to_glyphs(sinh.doc, sinh.profile.language_systems, src, a,
                             script="sinhala")
    inv_a = inventory_from_glyphs(a)
    taml_a = result_for("tamil", inv_a)
    write_features_to_glyphs(taml_a.doc, taml_a.profile.language_systems, a, b,
                             script="tamil", replace_tags={"akhn"})
    lib = load_source(b)

    # plugin, same steps
    font = fake_from_source(src)
    plugin.write_features(font, sinh.doc, sinh.profile.language_systems, script="sinhala")
    taml_p = result_for("tamil", inv_a)
    plugin.write_features(font, taml_p.doc, taml_p.profile.language_systems,
                          script="tamil", replace_tags={"akhn"})

    assert snapshot(font.features, font.featurePrefixes, font.classes) == \
        snapshot(lib.features, lib.featurePrefixes, lib.classes)


def test_plugin_leaves_the_other_script_alone(plugin, tmp_path):
    src = mixed_source(tmp_path, hand=False)
    inv = inventory_from_glyphs(src)
    font = fake_from_source(src)
    s = result_for("sinhala", inv)
    plugin.write_features(font, s.doc, s.profile.language_systems, script="sinhala")
    sinhala_code = sorted((f.name, f.code) for f in font.features)
    t = result_for("tamil", inv)
    summary = plugin.write_features(font, t.doc, t.profile.language_systems, script="tamil")
    assert summary["written_features"] > 0
    kept = sorted((f.name, f.code) for f in font.features
                  if owner_script(f.code) == "sinhala")
    assert kept == sinhala_code
    # and a second Tamil run replaces only Tamil's
    tamil_before = sorted(f.code for f in font.features if owner_script(f.code) == "tamil")
    plugin.write_features(font, t.doc, t.profile.language_systems, script="tamil")
    assert sorted(f.code for f in font.features if owner_script(f.code) == "tamil") == tamil_before
    assert sorted((f.name, f.code) for f in font.features
                  if owner_script(f.code) == "sinhala") == sinhala_code


def test_plugin_replace_removes_only_the_collision_of_that_script(plugin, tmp_path):
    src = mixed_source(tmp_path)
    font = fake_from_source(src)
    t = result_for("tamil", inventory_from_glyphs(src))
    summary = plugin.write_features(font, t.doc, t.profile.language_systems,
                                    script="tamil", replace_tags={"akhn"})
    assert summary["collisions"]["akhn"] == "replace"
    akhn = [f.code for f in font.features if f.name == "akhn"]
    assert HAND_SINH_AKHN in akhn and HAND_TAML_AKHN not in akhn


def test_plugin_without_a_script_behaves_as_before(plugin, tmp_path):
    """No script: every generated block is ours, and a single-script source is unscoped."""
    from make_font import build_test_glyphs_source
    from lankafea.scripts import get_profile
    src = build_test_glyphs_source(get_profile("tamil", 2), tmp_path / "t.glyphs")
    font = fake_from_source(src)
    t = result_for("tamil", inventory_from_glyphs(src))
    plugin.write_features(font, t.doc, t.profile.language_systems)
    abvs = next(f for f in font.features if f.name == "abvs")
    assert "script taml;" not in abvs.code and "lankafea:script" not in abvs.code
    n = len(font.features)
    plugin.write_features(font, t.doc, t.profile.language_systems)       # idempotent
    assert len(font.features) == n
    assert [p.name for p in font.featurePrefixes].count("lankafea-manifest") == 1

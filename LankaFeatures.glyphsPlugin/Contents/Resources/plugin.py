# encoding: utf-8
"""Lanka Features — Glyphs 3 general plugin.

Runs the lankafea feature generator (Sinhala / Tamil OpenType features, gated on
the glyphs actually present) against the frontmost font, and can re-run it
automatically whenever the font's glyph set changes.

Hand-written features are never touched: only code carrying the lankafea
ownership marker (and classes listed in the manifest prefix) is replaced.
"""

from __future__ import division, print_function, unicode_literals

import hashlib
import os
import sys
import threading
import traceback

import objc
from AppKit import (NSAlert, NSMenu, NSMenuItem, NSOnState, NSOffState,
                    NSTextField)
from Foundation import NSObject
from GlyphsApp import (Glyphs, GSGlyph, GSFeature, GSClass, GSFeaturePrefix,
                       GLYPH_MENU, UPDATEINTERFACE, DOCUMENTOPENED,
                       DOCUMENTWASSAVED, DOCUMENTACTIVATED)
from GlyphsApp.plugins import GeneralPlugin
from PyObjCTools import AppHelper

_RES = os.path.dirname(os.path.abspath(__file__))
if _RES not in sys.path:
    sys.path.insert(0, _RES)

# Same ownership contract as lankafea.glyphsource — keep in sync.
MARKER = "# lankafea:generated v1 — do not edit; regenerate with lankafea"
MANIFEST_PREFIX = "lankafea-manifest"
INJECTED_PREFIX = "lankafea-injected"

DEFAULTS = {"auto": False, "script": "auto", "level": 3, "replace": ""}
USERDATA_KEY = "com.mooniak.lankafea"
POLL_SECONDS = 1.0


# --------------------------------------------------------------------------- #
# Font <-> lankafea bridge (pure functions; no UI)
# --------------------------------------------------------------------------- #

def _owned_class_names(font):
    for prefix in font.featurePrefixes:
        if prefix.name == MANIFEST_PREFIX:
            for line in (prefix.code or "").splitlines():
                if line.startswith("# classes:"):
                    return set(line[len("# classes:"):].split())
    return set()


def _unicodes(glyph):
    out = []
    for u in (glyph.unicodes or []):
        try:
            out.append(int(str(u), 16))
        except ValueError:
            pass
    return out


def build_inventory(font):
    """Snapshot a GSFont into a lankafea FontInventory (main thread only)."""
    from lankafea.inventory import FontInventory

    names, cmap_names, anchors, glyph_info = set(), {}, {}, {}
    master_id = font.masters[0].id if font.masters else None
    for g in font.glyphs:
        if not g.name:
            continue
        names.add(g.name)
        glyph_info[g.name] = {"category": g.category, "subCategory": g.subCategory}
        for cp in _unicodes(g):
            cmap_names.setdefault(cp, g.name)
        if master_id:
            layer = g.layers[master_id]
            if layer is not None and layer.anchors:
                anchors[g.name] = {a.name for a in layer.anchors if a.name}
    owned = _owned_class_names(font)
    classes = {c.name: (c.code or "").split()
               for c in font.classes if c.name and c.name not in owned}
    return FontInventory(names, set(cmap_names), cmap_names, anchors, classes,
                         glyph_info)


def detect_script(font):
    """'sinhala' / 'tamil' by codepoint majority, or None."""
    sinh = tamil = 0
    for g in font.glyphs:
        for cp in _unicodes(g):
            if 0x0D80 <= cp <= 0x0DFF:
                sinh += 1
            elif 0x0B80 <= cp <= 0x0BFF:
                tamil += 1
    if not (sinh or tamil):
        return None
    return "sinhala" if sinh >= tamil else "tamil"


def glyph_signature(font):
    """Cheap fingerprint of what gating depends on: names + encodings."""
    h = hashlib.md5()
    for g in font.glyphs:
        h.update(("%s|%s;" % (g.name, g.unicodes or "")).encode("utf-8"))
    return h.hexdigest()


def write_features(font, doc, language_systems, raw_snippets=(),
                   replace_tags=(), keep_tags=()):
    """Replace lankafea-owned layout code in `font`; preserve everything else.

    Mirrors lankafea.glyphsource.write_features_to_glyphs, on live GS objects.
    """
    from lankafea.feacomposer_adapter import TextBackend

    owned_classes = _owned_class_names(font)
    summary = {"collisions": {}, "written_features": 0, "written_classes": 0}

    def is_ours(code):
        return (code or "").lstrip().startswith("# lankafea:generated")

    for i in reversed(range(len(font.features))):
        if is_ours(font.features[i].code):
            del font.features[i]
    for i in reversed(range(len(font.featurePrefixes))):
        p = font.featurePrefixes[i]
        if is_ours(p.code) or p.name in (MANIFEST_PREFIX, INJECTED_PREFIX):
            del font.featurePrefixes[i]
    for i in reversed(range(len(font.classes))):
        if font.classes[i].name in owned_classes:
            del font.classes[i]

    user_tags = {f.name for f in font.features}
    user_classes = {c.name for c in font.classes}
    text = TextBackend()

    if not any(p.name == "Languagesystems" for p in font.featurePrefixes):
        lines = ["languagesystem %s %s;" % (s, lang)
                 for s, langs in language_systems.items() for lang in langs]
        prefix = GSFeaturePrefix()
        prefix.name = "Languagesystems"
        prefix.code = MARKER + "\n" + "\n".join(lines)
        font.featurePrefixes.append(prefix)

    written_classes = []
    for cls in doc.classes:
        if not cls.members:
            continue
        if cls.name in user_classes:
            summary["collisions"]["@" + cls.name] = "keep"
            continue
        c = GSClass()
        c.name = cls.name
        c.code = " ".join(cls.members)
        font.classes.append(c)
        written_classes.append(cls.name)

    for feature in doc.features:
        body = text.emit_feature_body(feature)
        if not body:
            continue
        if feature.tag in user_tags:
            action = "replace" if feature.tag in replace_tags else "keep"
            summary["collisions"][feature.tag] = action
            if action != "replace":
                continue
            for i in reversed(range(len(font.features))):
                if font.features[i].name == feature.tag:
                    del font.features[i]
        f = GSFeature()
        f.name = feature.tag
        f.code = MARKER + "\n" + body
        font.features.append(f)
        summary["written_features"] += 1

    if raw_snippets:
        p = GSFeaturePrefix()
        p.name = INJECTED_PREFIX
        p.code = MARKER + "\n" + "\n\n".join(raw_snippets)
        font.featurePrefixes.append(p)

    m = GSFeaturePrefix()
    m.name = MANIFEST_PREFIX
    m.code = MARKER + "\n# classes: " + " ".join(written_classes)
    font.featurePrefixes.append(m)
    summary["written_classes"] = len(written_classes)
    return summary


def add_control_glyphs(font):
    """Add zero-width ZWJ/ZWNJ if missing (by name or codepoint). Returns names."""
    have_names = {g.name for g in font.glyphs}
    have_cps = {cp for g in font.glyphs for cp in _unicodes(g)}
    added = []
    for name, cp in (("zerowidthjoiner", 0x200D), ("zerowidthnonjoiner", 0x200C)):
        if name in have_names or cp in have_cps:
            continue
        g = GSGlyph(name)
        g.unicode = "%04X" % cp
        font.glyphs.append(g)
        for layer in g.layers:
            layer.width = 0
        added.append(name)
    return added


# --------------------------------------------------------------------------- #
# Plugin
# --------------------------------------------------------------------------- #

class LankaFeatures(GeneralPlugin):

    @objc.python_method
    def settings(self):
        self.name = Glyphs.localize({"en": "Lanka Features"})

    @objc.python_method
    def start(self):
        self._signatures = {}      # font id -> last seen glyph signature
        self._last_poll = {}       # font id -> timestamp
        self._busy = set()         # font ids with a build in flight
        self._pending = set()      # font ids needing another pass

        menu = NSMenu.alloc().initWithTitle_(self.name)
        self._items = {}

        def add(key, title, action):
            item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                title, action, "")
            item.setTarget_(self)
            menu.addItem_(item)
            self._items[key] = item
            return item

        add("generate", "Generate Features Now", "generateNow:")
        add("auto", "Auto-Generate When Glyphs Change", "toggleAuto:")
        add("report", "Dependency Report (Macro Window)", "showReport:")
        add("replace", "Replace Hand-Written Features…", "setReplace:")
        add("zwj", "Add ZWJ / ZWNJ Control Glyphs", "addControlGlyphs:")
        menu.addItem_(NSMenuItem.separatorItem())
        for key, title, action in (
                ("s_auto", "Script: Auto-detect", "setScript:"),
                ("s_sinhala", "Script: Sinhala", "setScript:"),
                ("s_tamil", "Script: Tamil", "setScript:")):
            add(key, title, action).setRepresentedObject_(key[2:])
        menu.addItem_(NSMenuItem.separatorItem())
        for lvl in range(4):
            add("l%d" % lvl, "Sinhala Level %d" % lvl,
                "setLevel:").setRepresentedObject_(lvl)

        root = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            self.name, None, "")
        root.setSubmenu_(menu)
        menu.setDelegate_(self)
        Glyphs.menu[GLYPH_MENU].append(root)

        Glyphs.addCallback(self.interfaceUpdate_, UPDATEINTERFACE)
        Glyphs.addCallback(self.documentEvent_, DOCUMENTOPENED)
        Glyphs.addCallback(self.documentEvent_, DOCUMENTWASSAVED)
        Glyphs.addCallback(self.documentEvent_, DOCUMENTACTIVATED)

    # -- per-font settings (stored in the font so they travel with the file) -- #

    @objc.python_method
    def _config(self, font):
        stored = font.userData[USERDATA_KEY] if font else None
        cfg = dict(DEFAULTS)
        if stored:
            for k in DEFAULTS:
                if k in stored:
                    cfg[k] = stored[k]
        return cfg

    @objc.python_method
    def _set(self, font, **changes):
        cfg = self._config(font)
        cfg.update(changes)
        font.userData[USERDATA_KEY] = cfg

    @objc.python_method
    def _font(self):
        return Glyphs.font

    # -- menu ----------------------------------------------------------------- #

    def menuWillOpen_(self, menu):
        self.refreshMenu()

    @objc.python_method
    def refreshMenu(self):
        font = self._font()
        cfg = self._config(font)
        on = lambda b: NSOnState if b else NSOffState
        self._items["auto"].setState_(on(cfg["auto"]))
        for key in ("auto", "sinhala", "tamil"):
            self._items["s_" + key].setState_(on(cfg["script"] == key))
        for lvl in range(4):
            self._items["l%d" % lvl].setState_(on(cfg["level"] == lvl))

    def validateMenuItem_(self, item):
        return self._font() is not None

    def generateNow_(self, sender):
        self.generate(self._font(), announce=True)

    def toggleAuto_(self, sender):
        font = self._font()
        if font is None:
            return
        on = not self._config(font)["auto"]
        self._set(font, auto=on)
        if on:
            self._signatures.pop(id(font), None)
            self.generate(font, announce=True)

    def setScript_(self, sender):
        font = self._font()
        if font:
            self._set(font, script=sender.representedObject())
            self.generate(font, announce=True)

    def setLevel_(self, sender):
        font = self._font()
        if font:
            self._set(font, level=int(sender.representedObject()))
            self.generate(font, announce=True)

    def setReplace_(self, sender):
        font = self._font()
        if font is None:
            return
        alert = NSAlert.alloc().init()
        alert.setMessageText_("Replace hand-written features")
        alert.setInformativeText_(
            "Comma-separated feature tags (e.g. abvs,blws) whose hand-written "
            "code should be REPLACED by generated rules. Leave empty to always "
            "keep your own.")
        field = NSTextField.alloc().initWithFrame_(((0, 0), (260, 24)))
        field.setStringValue_(self._config(font)["replace"])
        alert.setAccessoryView_(field)
        alert.addButtonWithTitle_("OK")
        alert.addButtonWithTitle_("Cancel")
        if alert.runModal() == 1000:
            self._set(font, replace=str(field.stringValue()).strip())
            self.generate(font, announce=True)

    def addControlGlyphs_(self, sender):
        font = self._font()
        if font is None:
            return
        added = add_control_glyphs(font)
        self._notify("Control glyphs",
                     "Added " + ", ".join(added) if added
                     else "ZWJ / ZWNJ already present.")

    def showReport_(self, sender):
        font = self._font()
        if font is None:
            return
        script = self._resolve_script(font)
        if not script:
            return self._notify("Lanka Features",
                                "No Sinhala or Tamil glyphs found.")
        try:
            from lankafea.api import validate_font
            report = validate_font(script, build_inventory(font),
                                   level=self._config(font)["level"],
                                   use_yaml=self._have_yaml())
        except Exception:
            return self._notify("Lanka Features", "Report failed — see Macro Window.",
                                detail=traceback.format_exc())
        Glyphs.showMacroWindow()
        print(report.to_text())

    # -- triggers ------------------------------------------------------------- #

    def interfaceUpdate_(self, notification):
        font = self._font()
        if font is None or not self._config(font)["auto"]:
            return
        import time
        now = time.time()
        key = id(font)
        if now - self._last_poll.get(key, 0) < POLL_SECONDS:
            return
        self._last_poll[key] = now
        sig = glyph_signature(font)
        if sig != self._signatures.get(key):
            self.generate(font)

    def documentEvent_(self, notification):
        # Catch glyph-set changes made while auto was off/while another doc
        # was frontmost (open, save, switch document).
        font = self._font()
        if font is not None and self._config(font)["auto"]:
            if glyph_signature(font) != self._signatures.get(id(font)):
                self.generate(font)

    # -- generation ----------------------------------------------------------- #

    @objc.python_method
    def _have_yaml(self):
        try:
            import yaml  # noqa: F401
            return True
        except ImportError:
            return False

    @objc.python_method
    def _resolve_script(self, font):
        choice = self._config(font)["script"]
        return detect_script(font) if choice == "auto" else choice

    @objc.python_method
    def generate(self, font, announce=False):
        """Snapshot on the main thread, build off-thread, apply on main."""
        if font is None:
            return
        key = id(font)
        if key in self._busy:
            self._pending.add(key)   # glyphs changed mid-build: go again after
            return
        script = self._resolve_script(font)
        if not script:
            if announce:
                self._notify("Lanka Features", "No Sinhala or Tamil glyphs found.")
            return
        cfg = self._config(font)
        sig = glyph_signature(font)
        inventory = build_inventory(font)
        use_yaml = self._have_yaml()
        self._busy.add(key)

        def work():
            try:
                from lankafea.api import build_fea
                result = build_fea(script=script, inventory=inventory,
                                   level=cfg["level"], use_yaml=use_yaml)
                err = None
            except Exception:
                result, err = None, traceback.format_exc()
            AppHelper.callAfter(self._apply, font, key, sig, script, result,
                                err, announce, use_yaml)

        threading.Thread(target=work, daemon=True).start()

    @objc.python_method
    def _apply(self, font, key, sig, script, result, err, announce, used_yaml):
        self._busy.discard(key)
        if err:
            self._signatures[key] = sig    # don't retry-loop on a broken state
            return self._notify("Lanka Features", "Generation failed — see Macro Window.",
                                detail=err)
        if font not in Glyphs.fonts:
            return
        font.disableUpdateInterface()
        try:
            summary = write_features(
                font, result.doc, result.profile.language_systems,
                raw_snippets=result.raw_snippets,
                replace_tags={t.strip() for t in
                              self._config(font)["replace"].split(",") if t.strip()})
        finally:
            font.enableUpdateInterface()
        # Signature of the glyph set we built for. If glyphs changed while the
        # worker ran, the next poll sees a different signature and rebuilds.
        self._signatures[key] = sig
        if key in self._pending:
            self._pending.discard(key)
            self._last_poll[key] = 0
        r = result.report
        kept = [t for t, a in summary["collisions"].items() if a == "keep"]
        if kept and not announce:
            # Auto runs must not fail silently: hand-written code is winning.
            self._notify("Lanka Features",
                         "Kept your hand-written: %s. Use Replace Hand-Written "
                         "Features… to let generated rules take over." % ", ".join(kept))
        if announce:
            msg = "%s: %d rules kept, %d blocked; %d features, %d classes written." % (
                script, r.kept_rules, r.dropped_rules,
                summary["written_features"], summary["written_classes"])
            if kept:
                msg += " Kept your hand-written: " + ", ".join(kept) + "."
            if not used_yaml:
                msg += " (PyYAML missing: used built-in tables.)"
            self._notify("Lanka Features", msg)

    # -- helpers -------------------------------------------------------------- #

    @objc.python_method
    def _notify(self, title, message, detail=None):
        if detail:
            Glyphs.showMacroWindow()
            print(detail)
        Glyphs.showNotification(title, message)

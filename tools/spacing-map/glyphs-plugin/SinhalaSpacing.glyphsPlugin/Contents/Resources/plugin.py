# encoding: utf-8
"""Sinhala Spacing — Glyphs 3 general plugin.

Wires the Sinhala spacing scheme (sinhala-spacing.yaml, bundled here as
sinhala_spacing/scheme.json) into the open font as metrics keys: every class
member inherits its rep's sidebearing via leftMetricsKey/rightMetricsKey.

  Auto mode (on by default, Glyph > Sinhala Spacing): whenever a glyph is
  added or renamed into a scheme entry, it gets the keys the map gives it.
  Only NEW glyphs are touched — opening an existing font changes nothing.

  Composites (sinhala-composites.yaml) the scheme doesn't key inherit from
  their base glyph. Glyphs that Glyphs auto-aligns (a composite with a spacing sign,
  ා ැ …) are skipped: their spacing comes from their components, and Glyphs
  can't apply name keys to an auto-aligned layer.

  Automatic runs only fill keys, never overwrite. A key that disagrees with the
  map (hand-set, copied, a formula) is flagged, and listed by Key Report.
  Override Disagreeing Keys… replaces them with the map's keys, on request.

The decision logic lives in sinhala_spacing/keyplan.py, shared with the
spacing-map CLI; regenerate the bundled copy with
`python -m spacing_map build-plugin`.
"""

from __future__ import division, print_function, unicode_literals

import json
import os
import sys
import time
import traceback

import objc
from AppKit import NSAlert, NSMenu, NSMenuItem, NSOnState, NSOffState
from GlyphsApp import (Glyphs, GLYPH_MENU, UPDATEINTERFACE, DOCUMENTOPENED,
                       DOCUMENTACTIVATED)
from GlyphsApp.plugins import GeneralPlugin

_RES = os.path.dirname(os.path.abspath(__file__))
if _RES not in sys.path:
    sys.path.insert(0, _RES)

from sinhala_spacing import keyplan, names  # noqa: E402

PREFIX = "com.mooniak.SinhalaSpacing"
AUTO_DEFAULT = PREFIX + ".auto"
NAMES_USERDATA = PREFIX + ".names"     # optional per-font {entry: glyph name}
POLL_SECONDS = 0.5
ATTR = {"left": "leftMetricsKey", "right": "rightMetricsKey"}
SIDE_ABBR = {"left": "L", "right": "R"}


def load_scheme():
    with open(os.path.join(_RES, "sinhala_spacing", "scheme.json"),
              encoding="utf-8") as f:
        return json.load(f)


# --------------------------------------------------------------------------- #
# Font bridge (main thread only)
# --------------------------------------------------------------------------- #

def glyph_names(font):
    return {g.name for g in font.glyphs if g.name}


def resolver_for(font, scheme):
    by_unicode = {}
    for g in font.glyphs:
        for u in (g.unicodes or []):
            try:
                by_unicode.setdefault(int(str(u), 16), g.name)
            except ValueError:
                pass
    overrides = font.userData[NAMES_USERDATA] or {}
    r = names.Resolver(glyph_names(font), by_unicode, dict(overrides),
                       lgs_names=scheme["lgs_names"])

    def resolve(entry):
        name, how = r.resolve(entry)
        return name if how in ("override", "unicode", "name") else None
    return resolve


def keys_of(font):
    """Glyph-level key plus each master layer's override, per side."""
    def get(name, side):
        glyph = font.glyphs[name]
        if glyph is None:
            return []
        attr = ATTR[side]
        keys = [getattr(glyph, attr)]
        for m in font.masters:
            layer = glyph.layers[m.id]
            if layer is not None:
                keys.append(getattr(layer, attr))
        return [k for k in keys if k]
    return get


def auto_aligned(font, name):
    glyph = font.glyphs[name]
    return glyph is not None and any(
        glyph.layers[m.id] is not None and glyph.layers[m.id].isAligned
        for m in font.masters)


def build_plan(font, scheme, only=None):
    expected, waiting = keyplan.expected_keys(
        scheme, resolver_for(font, scheme),
        composites=scheme.get("composites"),
        exists=lambda n: font.glyphs[n] is not None)
    aligned = sorted(n for n in expected if auto_aligned(font, n))
    for n in aligned:
        del expected[n]
    p = keyplan.plan(expected, keys_of(font), only=only)
    p["waiting"] = [w for w in waiting if only is None or w[0] in only]
    p["aligned"] = [n for n in aligned if only is None or n in only]
    return p


def apply_keys(font, rows):
    """Write glyph-level keys for 'set' or 'conflict' rows, clearing any
    per-layer key on that side (it would shadow the glyph-level one); re-sync
    drawn master layers whose rep is drawn too. One undo step per glyph."""
    by_glyph = {}
    for name, side, rep_name, _c, _e, _f in rows:
        by_glyph.setdefault(name, []).append((side, rep_name))
    font.disableUpdateInterface()
    try:
        for name, sides in by_glyph.items():
            glyph = font.glyphs[name]
            glyph.beginUndo()
            try:
                for side, rep_name in sides:
                    setattr(glyph, ATTR[side], rep_name)
                    for m in font.masters:
                        layer = glyph.layers[m.id]
                        if layer is not None and getattr(layer, ATTR[side]):
                            setattr(layer, ATTR[side], None)
                reps = {font.glyphs[r] for _, r in sides}
                for m in font.masters:
                    layer = glyph.layers[m.id]
                    if layer is None or not layer.shapes:
                        continue
                    if all(r is not None and r.layers[m.id] is not None
                           and r.layers[m.id].shapes for r in reps):
                        layer.syncMetrics()
                        layer.alignComponents()   # re-seat anchored signs
            finally:
                glyph.endUndo()
    finally:
        font.enableUpdateInterface()
    return by_glyph


def describe(row):
    name, side, rep_name, cname, entry, found = row
    s = "%s %s %s: %s" % (entry, name, SIDE_ABBR[side], rep_name)
    if found:
        s = "%s %s %s = %s  (map: %s, class %s)" % (
            entry, name, SIDE_ABBR[side], " / ".join(found), rep_name, cname)
    return s


# --------------------------------------------------------------------------- #
# Plugin
# --------------------------------------------------------------------------- #

class SinhalaSpacing(GeneralPlugin):

    @objc.python_method
    def settings(self):
        self.name = Glyphs.localize({"en": "Sinhala Spacing"})

    @objc.python_method
    def start(self):
        Glyphs.registerDefaults({AUTO_DEFAULT: True})
        try:
            self.scheme = load_scheme()
        except Exception:
            self.scheme = None
            self._notify("Sinhala Spacing", "Could not load the bundled scheme "
                         "— see Macro Window.", detail=traceback.format_exc())
        self._known = {}       # font id -> glyph names last seen
        self._pending = {}     # font id -> new glyph names not yet keyed
        self._last_poll = {}
        self._busy = False

        menu = NSMenu.alloc().initWithTitle_(self.name)
        self._items = {}

        def add(key, title, action):
            item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                title, action, "")
            item.setTarget_(self)
            menu.addItem_(item)
            self._items[key] = item

        add("auto", "Auto-Apply Keys to New Glyphs", "toggleAuto:")
        menu.addItem_(NSMenuItem.separatorItem())
        add("apply", "Apply Keys to Whole Font…", "applyAll:")
        add("report", "Key Report (Macro Window + Tab)", "showReport:")
        menu.addItem_(NSMenuItem.separatorItem())
        add("override_sel", "Override Disagreeing Keys — Selected Glyphs…",
            "overrideSelected:")
        add("override_all", "Override Disagreeing Keys — Whole Font…",
            "overrideAll:")

        root = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            self.name, None, "")
        root.setSubmenu_(menu)
        menu.setDelegate_(self)
        Glyphs.menu[GLYPH_MENU].append(root)

        Glyphs.addCallback(self.interfaceUpdate_, UPDATEINTERFACE)
        Glyphs.addCallback(self.documentEvent_, DOCUMENTOPENED)
        Glyphs.addCallback(self.documentEvent_, DOCUMENTACTIVATED)

    @objc.python_method
    def _auto(self):
        return bool(Glyphs.defaults[AUTO_DEFAULT])

    # -- menu ----------------------------------------------------------------- #

    def menuWillOpen_(self, menu):
        self._items["auto"].setState_(NSOnState if self._auto() else NSOffState)

    def validateMenuItem_(self, item):
        if self.scheme is None:
            return False
        return item == self._items["auto"] or Glyphs.font is not None

    def toggleAuto_(self, sender):
        on = not self._auto()
        Glyphs.defaults[AUTO_DEFAULT] = on
        font = Glyphs.font
        if on and font is not None:
            # glyphs added while auto was off are not "new": re-baseline
            self._baseline(font)
        self._notify("Sinhala Spacing", "Auto-apply keys %s." % ("on" if on else "off"))

    def applyAll_(self, sender):
        font = Glyphs.font
        if font is None:
            return
        p = build_plan(font, self.scheme)
        if not p["set"]:
            self._notify("Sinhala Spacing", "Nothing to set: %d keys match the map, "
                         "%d conflict." % (len(p["ok"]), len(p["conflict"])))
            if p["conflict"]:
                self.report(font, p)
            return
        glyphs = {r[0] for r in p["set"]}
        alert = NSAlert.alloc().init()
        alert.setMessageText_("Apply spacing keys")
        alert.setInformativeText_(
            "Set %d metrics keys on %d glyphs and update their sidebearings "
            "from their class reps?\n\n%d keys already match. %d keys disagree "
            "with the map and will be left as they are (see Key Report). "
            "%d glyphs wait for a rep that isn't in the font yet."
            % (len(p["set"]), len(glyphs), len(p["ok"]), len(p["conflict"]),
               len({w[0] for w in p["waiting"]})))
        alert.addButtonWithTitle_("Apply")
        alert.addButtonWithTitle_("Cancel")
        if alert.runModal() != 1000:
            return
        self._run(lambda: apply_keys(font, p["set"]))
        self._notify("Sinhala Spacing", "Set %d keys on %d glyphs." % (
            len(p["set"]), len(glyphs)))
        if p["conflict"]:
            self.report(font, p)

    def overrideSelected_(self, sender):
        font = Glyphs.font
        if font is None:
            return
        selected = {l.parent.name for l in (font.selectedLayers or [])
                    if l.parent is not None}
        if not selected:
            return self._notify("Sinhala Spacing", "Select glyphs in the font "
                                "view (or open one in Edit view) first.")
        self._override(font, selected)

    def overrideAll_(self, sender):
        font = Glyphs.font
        if font is not None:
            self._override(font, None)

    @objc.python_method
    def _override(self, font, only):
        """Replace keys that disagree with the map. Destructive, so it always
        confirms and lists what is about to be lost."""
        p = build_plan(font, self.scheme, only=only)
        rows = p["conflict"]
        scope = "%d selected glyph(s)" % len(only) if only else "the whole font"
        if not rows:
            return self._notify("Sinhala Spacing", "No keys disagree with the map "
                                "in %s." % scope)
        glyphs = {r[0] for r in rows}
        sample = "\n".join("  " + describe(r) for r in rows[:8])
        if len(rows) > 8:
            sample += "\n  … and %d more" % (len(rows) - 8)
        alert = NSAlert.alloc().init()
        alert.setMessageText_("Override %d disagreeing key(s)?" % len(rows))
        alert.setInformativeText_(
            "In %s, %d key(s) on %d glyph(s) will be replaced by the map's, "
            "and per-master overrides on those sides cleared. Sidebearings "
            "will change to match each class rep. Undo restores them.\n\n%s"
            % (scope, len(rows), len(glyphs), sample))
        alert.addButtonWithTitle_("Override")
        alert.addButtonWithTitle_("Cancel")
        if alert.runModal() != 1000:
            return
        self._run(lambda: apply_keys(font, rows))
        print("Sinhala Spacing — overridden keys:")
        for row in rows:
            print("  " + describe(row))
        self._notify("Sinhala Spacing", "Overrode %d key(s) on %d glyph(s)." % (
            len(rows), len(glyphs)))

    def showReport_(self, sender):
        font = Glyphs.font
        if font is not None:
            self.report(font, build_plan(font, self.scheme), always=True)

    # -- triggers ------------------------------------------------------------- #

    def interfaceUpdate_(self, notification):
        font = Glyphs.font
        if font is None or self._busy or self.scheme is None or not self._auto():
            return
        key = id(font)
        now = time.time()
        if now - self._last_poll.get(key, 0) < POLL_SECONDS:
            return
        self._last_poll[key] = now
        self._check(font)

    def documentEvent_(self, notification):
        font = Glyphs.font
        if font is not None and self.scheme is not None and self._auto():
            self._check(font)

    @objc.python_method
    def _baseline(self, font):
        self._known[id(font)] = glyph_names(font)
        self._pending[id(font)] = set()

    @objc.python_method
    def _check(self, font):
        key = id(font)
        if key not in self._known:
            self._baseline(font)      # first sight: what exists is not new
            return
        current = glyph_names(font)
        new = current - self._known[key]
        self._known[key] = current
        pending = (self._pending.get(key, set()) | new) & current
        if not new or not pending:
            # pending glyphs wait for their rep; that only changes when the
            # glyph set does, so there is nothing to retry
            self._pending[key] = pending
            return
        try:
            p = build_plan(font, self.scheme, only=pending)
        except Exception:
            self._pending[key] = set()
            return self._notify("Sinhala Spacing", "Key check failed — see Macro "
                                "Window.", detail=traceback.format_exc())
        # keep only glyphs still waiting for a rep; the rest are settled
        self._pending[key] = {w[0] for w in p["waiting"]}
        if p["set"]:
            self._run(lambda: apply_keys(font, p["set"]))
            print("Sinhala Spacing — keys set:")
            for row in p["set"]:
                print("  " + describe(row))
            shown = sorted({r[4] for r in p["set"]})
            self._notify("Sinhala Spacing", "Keyed %s from the spacing map." % (
                " ".join(shown[:8]) + (" …" if len(shown) > 8 else "")))
        if p["conflict"]:
            print("Sinhala Spacing — keys that disagree with the map (left as is):")
            for row in p["conflict"]:
                print("  " + describe(row))
            self._notify("Sinhala Spacing", "%d key(s) on new glyphs disagree with "
                         "the map: %s. Left as is — see Key Report." % (
                             len(p["conflict"]),
                             ", ".join(describe(r) for r in p["conflict"][:2])))

    # -- report --------------------------------------------------------------- #

    @objc.python_method
    def report(self, font, p, always=False):
        Glyphs.showMacroWindow()
        print("\n" + "=" * 60)
        print("Sinhala Spacing — key report: %s" % (font.familyName or "untitled"))
        print("scheme: model %s" % self.scheme.get("meta", {}).get("model_version", "?"))
        print("  %d match the map, %d missing, %d disagree, %d glyphs waiting for a rep"
              % (len(p["ok"]), len(p["set"]), len(p["conflict"]),
                 len({w[0] for w in p["waiting"]})))
        for label, rows in (("DISAGREE with the map (never overwritten)", p["conflict"]),
                            ("MISSING (Apply Keys to Whole Font… sets these)", p["set"])):
            if rows:
                print("\n" + label + ":")
                for row in rows:
                    print("  " + describe(row))
        if p["aligned"]:
            print("\nAUTO-ALIGNED (spaced by their components, never keyed): %s"
                  % " ".join(p["aligned"]))
        if p["waiting"]:
            print("\nWAITING for a class rep that isn't in the font:")
            for name, side, cname, rep in p["waiting"]:
                print("  %s %s: rep %s (class %s)" % (name, SIDE_ABBR[side], rep, cname))

        lines = []
        for rows in (p["conflict"], p["set"]):
            seen = []
            for r in rows:
                if r[0] not in seen:
                    seen.append(r[0])
            if seen:
                lines.append("".join("/" + n for n in seen))
        if lines:
            font.newTab("\n".join(lines))
        elif always:
            self._notify("Sinhala Spacing", "All %d keys match the map." % len(p["ok"]))

    # -- helpers -------------------------------------------------------------- #

    @objc.python_method
    def _run(self, fn):
        self._busy = True
        try:
            return fn()
        finally:
            self._busy = False

    @objc.python_method
    def _notify(self, title, message, detail=None):
        if detail:
            Glyphs.showMacroWindow()
            print(detail)
        Glyphs.showNotification(title, message)

    @objc.python_method
    def __file__(self):
        return __file__

# encoding: utf-8
"""Sinhala Glyph Builder — Glyphs 3 general plugin.

Adds and builds Sinhala glyphs (Glyph > Sinhala Glyph Builder):

  Add Glyphs… — a visual picker over the whole glyph catalogue: every stage
  glyph, every grapheme attested in the corpus, the composite map and the
  sign variants. Each glyph is made as Draw (an outline glyph), Composite
  (components) or Features (no precomposed glyph — shaping assembles it; the
  decision is recorded in the font). A glyph whose parents — design parents
  in the stage model, or the parts it is made of — are not in the font is
  locked until they are added (or ticked alongside it).

  Composites from the composite map (sinhala-composites.yaml, bundled as
  sinhala_glyph_builder/map.json): each mapped glyph becomes its base + sign
  components, by canonical names — `ttU-sinh` = tta-sinh + usign-sinh.tta,
  `sRa-sinh` = sa-sinh + rasign-sinh.short.

  Auto mode (on by default): a glyph added under a mapped name, while still
  empty, is built at once — e.g. via Add Glyphs. Glyphs added by the picker
  are made as chosen there instead.

  A sign variant the font lacks (usign-sinh.medium …) is seeded from its plain
  sign's outlines and coloured orange for redesign. Nothing falls back to the
  plain sign.

  Spacing: a composite with an attached sign (ු ්‍ර ි …) has its base placed
  at the origin WITHOUT automatic alignment — signs stay anchored — so its
  sidebearings come from metrics keys (Sinhala Spacing writes them) rather
  than from the base's width, which would leave the sign hanging past the
  right edge. A composite with a spacing sign (ා ැ ෑ …) or led by a pre-base
  sign (ෙ ෛ) stays fully auto-aligned so every part advances; it carries no
  keys.

  The map's keep_drawn and review glyphs are never built by the map commands.
  Drawn glyphs are only replaced through Build Selected Glyphs…, after a
  confirmation.

The decisions live in sinhala_glyph_builder/buildplan.py and catalogue.py,
generated from tools/composite-map with `python -m composite_map build-plugin`;
the font edits in glyphbuild.py; the picker in add_glyphs.py.
"""

from __future__ import division, print_function, unicode_literals

import os
import sys
import time
import traceback

import objc
from AppKit import (NSAlert, NSMenu, NSMenuItem, NSOnState, NSOffState,
                    NSTextField, NSMakeRect)
from GlyphsApp import (Glyphs, GLYPH_MENU, UPDATEINTERFACE, DOCUMENTOPENED,
                       DOCUMENTACTIVATED)
from GlyphsApp.plugins import GeneralPlugin

_RES = os.path.dirname(os.path.abspath(__file__))
if _RES not in sys.path:
    sys.path.insert(0, _RES)

import glyphbuild  # noqa: E402
from glyphbuild import (apply_plan, build_plan, describe, font_state,  # noqa: E402
                        glyph_names, known_names, print_plan, remember_names,
                        summary)

PREFIX = "com.mooniak.SinhalaGlyphBuilder"
AUTO_DEFAULT = PREFIX + ".auto"
POLL_SECONDS = 0.5


def event_font(notification):
    """The font a document notification is about, rather than whichever font
    happens to be frontmost when it arrives."""
    try:
        font = notification.object().font
        font = font() if callable(font) else font
        if font is not None:
            return font
    except Exception:
        pass
    return Glyphs.font


def confirm(title, text, button):
    alert = NSAlert.alloc().init()
    alert.setMessageText_(title)
    alert.setInformativeText_(text)
    alert.addButtonWithTitle_(button)
    alert.addButtonWithTitle_("Cancel")
    return alert.runModal() == 1000


def ask_names():
    alert = NSAlert.alloc().init()
    alert.setMessageText_("Build Sinhala composites")
    alert.setInformativeText_("Glyph names, separated by spaces "
                              "(e.g. ttU-sinh sU-sinh kRa-sinh):")
    field = NSTextField.alloc().initWithFrame_(NSMakeRect(0, 0, 360, 24))
    alert.setAccessoryView_(field)
    alert.addButtonWithTitle_("Build")
    alert.addButtonWithTitle_("Cancel")
    alert.window().setInitialFirstResponder_(field)
    if alert.runModal() != 1000:
        return []
    return [n for n in field.stringValue().replace(",", " ").split() if n]


# --------------------------------------------------------------------------- #
# Plugin
# --------------------------------------------------------------------------- #

class SinhalaGlyphBuilder(GeneralPlugin):

    @objc.python_method
    def settings(self):
        self.name = Glyphs.localize({"en": glyphbuild.TITLE})

    @objc.python_method
    def start(self):
        Glyphs.registerDefaults({AUTO_DEFAULT: True})
        try:
            self.cmap = glyphbuild.load_map()
            self.cat = glyphbuild.load_catalogue()
        except Exception:
            self.cmap = self.cat = None
            self._notify("Could not load the bundled data — see Macro Window.",
                         detail=traceback.format_exc())
        self._last_poll = 0
        self._busy = False
        self._picker = None

        menu = NSMenu.alloc().initWithTitle_(self.name)
        self._items = {}

        def add(key, title, action):
            item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                title, action, "")
            item.setTarget_(self)
            menu.addItem_(item)
            self._items[key] = item

        add("picker", "Add Glyphs…", "addGlyphs:")
        menu.addItem_(NSMenuItem.separatorItem())
        add("auto", "Auto-Build New Composites", "toggleAuto:")
        menu.addItem_(NSMenuItem.separatorItem())
        add("names", "Build Composites by Name…", "buildByName:")
        add("selected", "Build Selected Composites…", "buildSelected:")
        add("all", "Build All Composites…", "buildAll:")
        menu.addItem_(NSMenuItem.separatorItem())
        add("report", "Composite Report", "showReport:")

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
        if self.cmap is None:
            return False
        return item == self._items["auto"] or Glyphs.font is not None

    def addGlyphs_(self, sender):
        font = Glyphs.font
        if font is None:
            return
        from add_glyphs import AddGlyphsWindow
        if self._picker is not None:
            try:
                if self._picker.font == font and self._picker.w.getNSWindow().isVisible():
                    return self._picker.w.makeKey()
                self._picker.w.close()
            except Exception:
                pass
        try:
            self._picker = AddGlyphsWindow(font, self.cmap, self.cat, self)
        except Exception:
            self._notify("Could not open Add Glyphs — see Macro Window.",
                         detail=traceback.format_exc())

    def toggleAuto_(self, sender):
        on = not self._auto()
        Glyphs.defaults[AUTO_DEFAULT] = on
        if on and Glyphs.font is not None:
            remember_names(Glyphs.font)
        self._notify("Auto-build %s." % ("on" if on else "off"))

    def buildByName_(self, sender):
        font = Glyphs.font
        if font is None:
            return
        names = ask_names()
        if names:
            # named explicitly but possibly absent: never replaces drawing
            self._build(font, build_plan(font, self.cmap, targets=names), names)

    def buildSelected_(self, sender):
        font = Glyphs.font
        if font is None:
            return
        selected = []
        for layer in font.selectedLayers or []:
            if layer.parent is not None and layer.parent.name not in selected:
                selected.append(layer.parent.name)
        if not selected:
            return self._notify("Select glyphs in the font view (or open one "
                                "in Edit view) first.")
        p = build_plan(font, self.cmap, targets=selected, overwrite=True)
        drawn = [r[0] for r in p["build"] if r[2] == "rebuild"
                 and font_state(font)[1](r[0])[0] == "drawn"]
        if drawn and not confirm(
                "Replace %d drawn glyph(s)?" % len(drawn),
                "Their outlines will be replaced by components:\n\n  %s\n\n"
                "Undo restores them." % "  ".join(drawn[:20])
                + (" …" if len(drawn) > 20 else ""), "Replace"):
            return
        self._build(font, p, selected)

    def buildAll_(self, sender):
        font = Glyphs.font
        if font is None:
            return
        p = build_plan(font, self.cmap)
        if not p["build"]:
            print_plan(p, "Sinhala Glyph Builder — all composites")
            return self._notify("Nothing to build: %d composites already right." % len(p["ok"]))
        if not confirm("Build Sinhala composites",
                       "%s.\n\nDrawn glyphs are left as they are; %d glyph(s) "
                       "are skipped (listed in the Macro Window)."
                       % (summary(p).capitalize(), len(p["skip"])), "Build"):
            return
        self._build(font, p, None)

    def showReport_(self, sender):
        font = Glyphs.font
        if font is None:
            return
        p = build_plan(font, self.cmap)
        print_plan(p, "Sinhala Glyph Builder — report: %s (Build All Composites would do this)"
                   % (font.familyName or "untitled"))
        names = list(p["seed"]) + [r[0] for r in p["build"]]
        tab = "".join("/" + n for n in names if font.glyphs[n] is not None)
        if tab:
            font.newTab(tab)

    # -- triggers ------------------------------------------------------------- #

    def interfaceUpdate_(self, notification):
        font = Glyphs.font
        if font is None or self._busy or self.cmap is None or not self._auto():
            return
        now = time.time()
        if now - self._last_poll < POLL_SECONDS:
            return
        self._last_poll = now
        self._check(font)

    def documentEvent_(self, notification):
        font = event_font(notification)
        if font is not None and self.cmap is not None and self._auto():
            self._check(font)

    @objc.python_method
    def _check(self, font):
        current = glyph_names(font)
        known = known_names(font)
        remember_names(font, current)
        if known is None:
            return                          # first sight: what exists is not new
        new = current - known
        new = [n for n in new if n in self.cmap["composites"]]
        if not new:
            return
        try:
            p = build_plan(font, self.cmap, targets=sorted(new))
        except Exception:
            return self._notify("Composite check failed — see Macro Window.",
                                detail=traceback.format_exc())
        if p["build"]:
            self._build(font, p, None, quiet=True)

    # -- build ---------------------------------------------------------------- #

    @objc.python_method
    def _build(self, font, p, requested, quiet=False):
        if p["build"]:
            self._busy = True
            try:
                apply_plan(font, self.cmap, p)
            except Exception:
                return self._notify("Build failed — see Macro Window.",
                                    detail=traceback.format_exc())
            finally:
                self._busy = False
                remember_names(font)
        print("Sinhala Glyph Builder — built:")
        for row in p["build"]:
            print("  " + describe(row))
        for variant, source in sorted(p["seed"].items()):
            print("  %-22s seeded from %s (orange)" % (variant, source))
        if p["skip"] and requested is not None:
            print_plan(p, "Sinhala Glyph Builder")
        msg = "Built %d glyph(s)" % len(p["build"])
        if p["seed"]:
            msg += ", seeded %d sign variant(s) to redesign" % len(p["seed"])
        if p["skip"]:
            msg += ", skipped %d" % len(p["skip"])
        self._notify(msg + ".")
        if not quiet and p["build"]:
            built = [r[0] for r in p["build"]]
            font.newTab("".join("/" + n for n in built + sorted(p["seed"])))

    @objc.python_method
    def _notify(self, message, detail=None):
        if detail:
            Glyphs.showMacroWindow()
            print(detail)
        Glyphs.showNotification(glyphbuild.TITLE, message)

    @objc.python_method
    def __file__(self):
        return __file__

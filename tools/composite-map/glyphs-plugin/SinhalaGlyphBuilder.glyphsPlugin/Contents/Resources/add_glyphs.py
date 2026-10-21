# encoding: utf-8
"""Add Sinhala Glyphs — the Sinhala Glyph Builder's visual picker.

Every glyph of the catalogue (stage glyphs, every grapheme attested in the
corpus, the composite map, sign variants) is a tile: the font's own drawing
when it has one, else the grapheme set in a reference Sinhala font. Click a
tile to tick it for adding; option-click only inspects it. The panel on the
right shows how the selected glyph can be made — Draw, Composite or Features —
and what it needs.

A glyph is locked until everything it depends on (its design parents in the
stage model and the parts it is made of) is in the font, recorded as made by
features, or ticked in the same session — so parents always come first.
"""

from __future__ import division, print_function, unicode_literals

import math
import traceback

import objc
from AppKit import (NSAffineTransform, NSAttributedString, NSBeep, NSBezierPath,
                    NSColor, NSFont, NSFontAttributeName,
                    NSForegroundColorAttributeName, NSLineBreakByTruncatingMiddle,
                    NSMakeRect, NSMenuItem, NSMutableAttributedString,
                    NSMutableParagraphStyle, NSNotificationCenter,
                    NSParagraphStyleAttributeName, NSView,
                    NSViewFrameDidChangeNotification, NSViewHeightSizable,
                    NSViewWidthSizable, NSCenterTextAlignment)
from GlyphsApp import Glyphs
from vanilla import (Button, CheckBox, Group, List2, PopUpButton, ScrollView,
                     SearchBox, SegmentedButton, TextBox, Window)

import glyphbuild
from sinhala_glyph_builder import catalogue as C

TILE_W, TILE_H, GLYPH_H, GAP = 78, 100, 66, 6
REFERENCE_FONTS = ("Noto Sans Sinhala", "Noto Serif Sinhala", "Sinhala Sangam MN",
                   "Sinhala MN")
MODE_TITLES = {C.DRAW: "Draw", C.COMPOSITE: "Composite", C.FEATURES: "Features"}
PREFER = [("Recommended", None), ("Prefer draw", C.DRAW),
          ("Prefer composite", C.COMPOSITE), ("Prefer features", C.FEATURES)]
OPTION_KEY = 1 << 19
KEY_LEFT, KEY_RIGHT, KEY_DOWN, KEY_UP = 123, 124, 125, 126


def reference_font(size):
    for name in REFERENCE_FONTS:
        f = NSFont.fontWithName_size_(name, size)
        if f is not None:
            return f
    return NSFont.systemFontOfSize_(size)


def _para(align=NSCenterTextAlignment):
    p = NSMutableParagraphStyle.alloc().init()
    p.setAlignment_(align)
    p.setLineBreakMode_(NSLineBreakByTruncatingMiddle)
    return p


def _attr(text, font, color, para=None):
    attrs = {NSFontAttributeName: font, NSForegroundColorAttributeName: color}
    if para is not None:
        attrs[NSParagraphStyleAttributeName] = para
    return NSAttributedString.alloc().initWithString_attributes_(text, attrs)


def _tint(color, alpha):
    return color.colorWithAlphaComponent_(alpha)


# --------------------------------------------------------------------------- #
# Views (drawing and events are forwarded to the controller)
# --------------------------------------------------------------------------- #

class SGBGlyphGrid(NSView):

    def isFlipped(self):
        return True

    def acceptsFirstResponder(self):
        return True

    def drawRect_(self, rect):
        ctl = getattr(self, "ctl", None)
        if ctl is not None:
            ctl.draw_grid(rect)

    def mouseDown_(self, event):
        ctl = getattr(self, "ctl", None)
        if ctl is not None:
            pt = self.convertPoint_fromView_(event.locationInWindow(), None)
            ctl.grid_click(pt, event.modifierFlags())

    def keyDown_(self, event):
        ctl = getattr(self, "ctl", None)
        if ctl is None or not ctl.grid_key(event.keyCode(), event.characters()):
            objc.super(SGBGlyphGrid, self).keyDown_(event)

    def clipFrameChanged_(self, notification):
        ctl = getattr(self, "ctl", None)
        if ctl is not None:
            ctl.relayout()


class SGBGlyphPreview(NSView):

    def isFlipped(self):
        return True

    def drawRect_(self, rect):
        ctl = getattr(self, "ctl", None)
        if ctl is not None:
            ctl.draw_preview(self.bounds())


# --------------------------------------------------------------------------- #
# Controller
# --------------------------------------------------------------------------- #

class AddGlyphsWindow(object):

    def __init__(self, font, cmap, cat, plugin=None):
        self.font = font
        self.cmap = cmap
        self.cat = cat
        self.plugin = plugin
        self.items = C.index(cat)
        self.order = [it["name"] for it in cat["items"]]
        self.rank = {n: i for i, n in enumerate(self.order)}
        self.prefer = None
        self.modes = {n: it["default"] for n, it in self.items.items()}
        self.checked = {}
        self.valid = {}
        self.current = None
        self.visible = []
        self._paths = {}
        self._ref_small = reference_font(30)
        self._ref_big = reference_font(110)
        self._label_font = NSFont.systemFontOfSize_(9)
        self._badge_font = NSFont.boldSystemFontOfSize_(9)
        self._filters = self._build_filters()
        self._build_window()
        self.refresh_font()
        self.w.open()
        self.relayout()
        self.w.makeKey()

    # -- filters ------------------------------------------------------------- #

    def _build_filters(self):
        """[(title, predicate)], None for a menu separator."""
        out = [("All glyphs", lambda it: True)]
        out.append(None)
        staged = {it.get("stage") for it in self.cat["items"]}
        for st in self.cat["stages"]:
            n = st["n"]
            if n in staged:
                out.append(("Stage %d — %s" % (n, st["name"]),
                            (lambda n: lambda it: it.get("stage") == n)(n)))
        out.append(("Not scheduled", lambda it: it.get("stage") is None))
        out.append(None)
        for g in self.cat["groups"]:
            out.append((g["title"], (lambda gid: lambda it: gid in it["groups"])(g["id"])))
        return out

    # -- window -------------------------------------------------------------- #

    def _build_window(self):
        title = "Add Sinhala Glyphs — %s" % (self.font.familyName or "untitled")
        self.w = Window((1120, 740), title, minSize=(940, 560),
                        autosaveName="com.mooniak.SinhalaGlyphBuilder.addGlyphs")
        w = self.w

        # unique placeholders: NSPopUpButton drops duplicate titles
        titles = [f[0] if f else "-%d-" % i for i, f in enumerate(self._filters)]
        w.filter = PopUpButton((10, 10, 250, 24), titles, callback=self.filterChanged_)
        menu = w.filter.getNSPopUpButton().menu()
        for i in reversed([i for i, f in enumerate(self._filters) if f is None]):
            menu.removeItemAtIndex_(i)
            menu.insertItem_atIndex_(NSMenuItem.separatorItem(), i)
        w.search = SearchBox((270, 10, 210, 24), placeholder="name or Sinhala text",
                             callback=self.filterChanged_)
        w.hideInFont = CheckBox((495, 11, 105, 22), "Hide in font",
                                value=False, callback=self.filterChanged_)
        w.hideLocked = CheckBox((605, 11, 100, 22), "Hide locked",
                                value=False, callback=self.filterChanged_)
        # base + ා ැ ෑ ෙ ේ ො ෝ ෛ ෞ ්‍ය …: optional glyphs, shaped from their
        # parts unless a font chooses to precompose them
        w.showFeatures = CheckBox((710, 11, 200, 22), "Show feature-only glyphs",
                                  value=False, callback=self.filterChanged_)

        self.grid = SGBGlyphGrid.alloc().initWithFrame_(NSMakeRect(0, 0, 700, 500))
        self.grid.ctl = self
        w.gridScroll = ScrollView((10, 44, -340, -52), self.grid,
                                  hasHorizontalScroller=False, autohidesScrollers=True)
        clip = w.gridScroll.getNSScrollView().contentView()
        clip.setPostsFrameChangedNotifications_(True)
        NSNotificationCenter.defaultCenter().addObserver_selector_name_object_(
            self.grid, "clipFrameChanged:", NSViewFrameDidChangeNotification, clip)

        # detail pane
        x, pw = -330, 320
        w.previewBox = Group((x, 44, pw, 200))
        self.preview = SGBGlyphPreview.alloc().initWithFrame_(NSMakeRect(0, 0, pw, 200))
        self.preview.ctl = self
        self.preview.setAutoresizingMask_(NSViewWidthSizable | NSViewHeightSizable)
        w.previewBox.getNSView().addSubview_(self.preview)
        w.name = TextBox((x, 252, pw, 22), "", sizeStyle="regular")
        w.info = TextBox((x, 276, pw, 34), "", sizeStyle="small")
        w.note = TextBox((x, 312, pw, 46), "", sizeStyle="small")
        w.modeLabel = TextBox((x, 366, 70, 20), "Make as", sizeStyle="small")
        w.mode = SegmentedButton((x + 62, 362, pw - 62, 24),
                                 [dict(title=MODE_TITLES[m]) for m in C.MODES],
                                 callback=self.modeChanged_, sizeStyle="small")
        w.recipe = TextBox((x, 394, pw, 34), "", sizeStyle="small")
        w.needsLabel = TextBox((x, 432, pw, 18), "Needs", sizeStyle="small")
        w.needs = List2((x, 452, pw, -100), [], allowsSorting=False,
                        allowsMultipleSelection=False,
                        doubleClickCallback=self.needDoubleClicked_)
        w.forget = Button((x, -94, pw, 22), "Forget the features decision",
                          callback=self.forget_, sizeStyle="small")
        w.legend = TextBox((x, -64, pw, 18), self._legend())

        # bottom bar
        w.status = TextBox((10, -40, -800, 34), "", sizeStyle="small")
        w.prefer = PopUpButton((-790, -38, 160, 24), [p[0] for p in PREFER],
                               callback=self.preferChanged_)
        w.fromParts = CheckBox((-620, -38, 190, 24), "Start drawings from parts",
                               value=True)
        w.checkAll = Button((-424, -38, 150, 24), "Tick all in view",
                            callback=self.checkAll_)
        w.clear = Button((-268, -38, 70, 24), "Clear", callback=self.clear_)
        w.add = Button((-192, -38, 182, 24), "Add", callback=self.add_)
        w.setDefaultButton(w.add)
        w.bind("became key", self.becameKey_)
        w.bind("close", self.closed_)

    def _legend(self):
        s = NSMutableAttributedString.alloc().init()
        small = NSFont.systemFontOfSize_(10)
        for color, label in ((self._color_in_font(), "in font"),
                             (self._color_empty(), "empty"),
                             (self._color_features(), "features"),
                             (self._color_checked(), "to add"),
                             (NSColor.tertiaryLabelColor(), "locked")):
            s.appendAttributedString_(_attr("● ", small, color.colorWithAlphaComponent_(1)))
            s.appendAttributedString_(_attr(label + "   ", small, NSColor.secondaryLabelColor()))
        return s

    @staticmethod
    def _color_in_font():
        return NSColor.systemGreenColor()

    @staticmethod
    def _color_empty():
        return NSColor.systemYellowColor()

    @staticmethod
    def _color_features():
        return NSColor.systemTealColor()

    @staticmethod
    def _color_checked():
        return NSColor.controlAccentColor()

    # -- state --------------------------------------------------------------- #

    def refresh_font(self):
        font = self.font
        self.glyphs = glyphbuild.glyph_names(font)
        self.designed = glyphbuild.designed_names(font)
        self.features = glyphbuild.recorded_features(font)
        master = font.selectedFontMaster or font.masters[0]
        self.master_id = master.id
        self.metrics = (master.ascender or 800, master.descender or -200)
        self._paths = {}
        self.recompute()

    def recompute(self):
        self.checked = {n: m for n, m in self.checked.items() if n not in self.glyphs}
        self.valid = C.resolve(self.items, self.glyphs, self.features, self.checked)
        dropped = [n for n in self.checked if n not in self.valid]
        for n in dropped:
            del self.checked[n]
        self.state = C.states(self.items, self.glyphs, self.features, self.valid, self.modes)
        self._dropped = dropped
        self.apply_filter()

    def feature_only(self, name):
        """Recommended as Features (an optional glyph), and neither in the
        font nor ticked — what Show feature-only glyphs reveals."""
        return (self.items[name]["default"] == C.FEATURES
                and self.state[name][0] not in (C.IN_FONT, C.CHECKED))

    def apply_filter(self):
        idx = self.w.filter.get()
        f = self._filters[idx] if 0 <= idx < len(self._filters) else None
        pred = f[1] if f else (lambda it: True)
        query = (self.w.search.get() or "").strip()
        ql = query.lower()
        hide_font = self.w.hideInFont.get()
        hide_locked = self.w.hideLocked.get()
        show_features = self.w.showFeatures.get()
        out = []
        self._hidden_features = 0
        for name in self.order:
            it = self.items[name]
            if not pred(it):
                continue
            if query and ql not in name.lower() and query not in (it.get("text") or ""):
                continue
            st = self.state[name][0]
            if hide_font and st in (C.IN_FONT, C.BY_FEATURES):
                continue
            if hide_locked and st == C.LOCKED:
                continue
            if not show_features and self.feature_only(name):
                self._hidden_features += 1
                continue
            out.append(name)
        if f and f[0] == "Attested in the corpus":
            out.sort(key=lambda n: -self.items[n].get("freq", 0))
        self.visible = out
        self.relayout()
        self.update_status()
        self.update_detail()

    # -- grid geometry -------------------------------------------------------- #

    def _columns(self, width):
        return max(1, int((width - GAP) // (TILE_W + GAP)))

    def _tile_rect(self, i, cols):
        row, col = divmod(i, cols)
        return NSMakeRect(GAP + col * (TILE_W + GAP), GAP + row * (TILE_H + GAP),
                          TILE_W, TILE_H)

    def relayout(self):
        clip = self.w.gridScroll.getNSScrollView().contentView()
        width = clip.bounds().size.width
        cols = self._columns(width)
        rows = int(math.ceil(len(self.visible) / float(cols)))
        height = max(rows * (TILE_H + GAP) + GAP, clip.bounds().size.height)
        self.grid.setFrame_(NSMakeRect(0, 0, width, height))
        self.grid.setNeedsDisplay_(True)

    def _index_at(self, pt):
        cols = self._columns(self.grid.bounds().size.width)
        col = int((pt.x - GAP) // (TILE_W + GAP))
        row = int((pt.y - GAP) // (TILE_H + GAP))
        if col < 0 or col >= cols or row < 0:
            return None
        i = row * cols + col
        if i >= len(self.visible):
            return None
        r = self._tile_rect(i, cols)
        if pt.x > r.origin.x + r.size.width or pt.y > r.origin.y + r.size.height:
            return None
        return i

    def reveal(self, name):
        if name not in self.visible:
            return
        cols = self._columns(self.grid.bounds().size.width)
        self.grid.scrollRectToVisible_(self._tile_rect(self.visible.index(name), cols))

    # -- drawing -------------------------------------------------------------- #

    def _layer_path(self, name):
        if name in self._paths:
            return self._paths[name]
        result = None
        glyph = self.font.glyphs[name]
        if glyph is not None:
            layer = glyph.layers[self.master_id]
            if layer is not None and layer.shapes:
                path = layer.completeBezierPath
                if path is not None:
                    result = (path, layer.width)
        self._paths[name] = result
        return result

    def _draw_glyph(self, name, area, big=False):
        """The font's drawing, else the grapheme in the reference font."""
        it = self.items[name]
        st = self.state[name][0]
        drawn = self._layer_path(name) if name in self.designed else None
        if drawn is not None:
            path, width = drawn
            asc, desc = self.metrics
            span = (asc - desc) * 1.5
            s = area.size.height / span
            base_y = area.origin.y + area.size.height - (-desc + (asc - desc) * 0.25) * s
            x0 = area.origin.x + (area.size.width - width * s) / 2.0
            t = NSAffineTransform.transform()
            t.translateXBy_yBy_(x0, base_y)
            t.scaleXBy_yBy_(s, -s)
            p = path.copy()
            p.transformUsingAffineTransform_(t)
            NSColor.labelColor().set()
            p.fill()
            return
        text = it.get("text") or it["name"].replace("-sinh", "")
        if st == C.LOCKED:
            color = NSColor.tertiaryLabelColor()
        elif st == C.IN_FONT:
            color = NSColor.secondaryLabelColor()       # in the font, not drawn yet
        else:
            color = NSColor.labelColor()
        font = self._ref_big if big else self._ref_small
        if not it.get("text"):
            font = NSFont.systemFontOfSize_(22 if big else 10)
        s = _attr(text, font, color)
        size = s.size()
        if size.width > area.size.width:
            scale = area.size.width / size.width
            font = NSFont.fontWithDescriptor_size_(font.fontDescriptor(), font.pointSize() * scale)
            s = _attr(text, font, color)
            size = s.size()
        s.drawAtPoint_((area.origin.x + (area.size.width - size.width) / 2.0,
                        area.origin.y + (area.size.height - size.height) / 2.0))

    def _tile_colors(self, name):
        st = self.state[name][0]
        if st == C.IN_FONT:
            c = self._color_in_font() if name in self.designed else self._color_empty()
            return _tint(c, 0.16), None
        if st == C.BY_FEATURES:
            return _tint(self._color_features(), 0.16), None
        if st == C.CHECKED:
            return _tint(self._color_checked(), 0.22), self._color_checked()
        if st == C.AVAILABLE:
            return NSColor.controlBackgroundColor(), NSColor.separatorColor()
        return _tint(NSColor.windowBackgroundColor(), 0.6), None

    def _badge(self, name):
        st, miss = self.state[name]
        mode = self.modes[name]
        if st == C.IN_FONT:
            return "in font" if name in self.designed else "empty"
        if st == C.BY_FEATURES:
            return "features"
        if st == C.CHECKED:
            return "✓ " + MODE_TITLES[self.checked[name]].lower()
        if st == C.LOCKED:
            return "🔒 needs %d" % len(miss)
        return MODE_TITLES[mode].lower()

    def draw_grid(self, rect):
        NSColor.windowBackgroundColor().set()
        NSBezierPath.fillRect_(rect)
        cols = self._columns(self.grid.bounds().size.width)
        first_row = max(0, int((rect.origin.y - GAP) // (TILE_H + GAP)))
        last_row = int((rect.origin.y + rect.size.height) // (TILE_H + GAP)) + 1
        para = _para()
        for i in range(first_row * cols, min(len(self.visible), (last_row + 1) * cols)):
            name = self.visible[i]
            r = self._tile_rect(i, cols)
            fill, stroke = self._tile_colors(name)
            box = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(r, 6, 6)
            fill.set()
            box.fill()
            if name == self.current:
                self._color_checked().set()
                box.setLineWidth_(2.5)
                box.stroke()
            elif stroke is not None:
                stroke.set()
                box.setLineWidth_(1)
                box.stroke()
            area = NSMakeRect(r.origin.x + 4, r.origin.y + 4, r.size.width - 8, GLYPH_H)
            self._draw_glyph(name, area)
            label = _attr(name, self._label_font, NSColor.secondaryLabelColor(), para)
            label.drawInRect_(NSMakeRect(r.origin.x + 2, r.origin.y + GLYPH_H + 6,
                                         r.size.width - 4, 13))
            badge = _attr(self._badge(name), self._badge_font,
                          NSColor.tertiaryLabelColor() if self.state[name][0] == C.LOCKED
                          else NSColor.secondaryLabelColor(), para)
            badge.drawInRect_(NSMakeRect(r.origin.x + 2, r.origin.y + GLYPH_H + 19,
                                         r.size.width - 4, 13))

    def draw_preview(self, bounds):
        NSColor.controlBackgroundColor().set()
        NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(bounds, 8, 8).fill()
        if self.current is None:
            hint = _attr("Click a glyph to tick it for adding;\noption-click to inspect it.",
                         NSFont.systemFontOfSize_(11), NSColor.secondaryLabelColor(), _para())
            hint.drawInRect_(NSMakeRect(10, bounds.size.height / 2 - 16, bounds.size.width - 20, 34))
            return
        area = NSMakeRect(10, 6, bounds.size.width - 20, bounds.size.height - 26)
        self._draw_glyph(self.current, area, big=True)
        source = ("this font" if self.current in self.designed
                  else "reference: %s" % self._ref_small.familyName())
        cap = _attr(source, NSFont.systemFontOfSize_(9), NSColor.tertiaryLabelColor(), _para())
        cap.drawInRect_(NSMakeRect(4, bounds.size.height - 16, bounds.size.width - 8, 13))

    # -- events --------------------------------------------------------------- #

    def grid_click(self, pt, flags):
        self.w.getNSWindow().makeFirstResponder_(self.grid)
        i = self._index_at(pt)
        if i is None:
            return
        name = self.visible[i]
        self.current = name
        if not flags & OPTION_KEY:
            self.toggle(name)
        else:
            self.update_detail()
            self.grid.setNeedsDisplay_(True)

    def grid_key(self, code, chars):
        if chars == " " and self.current:
            self.toggle(self.current)
            return True
        if code not in (KEY_LEFT, KEY_RIGHT, KEY_DOWN, KEY_UP) or not self.visible:
            return False
        cols = self._columns(self.grid.bounds().size.width)
        i = self.visible.index(self.current) if self.current in self.visible else -1
        step = {KEY_LEFT: -1, KEY_RIGHT: 1, KEY_UP: -cols, KEY_DOWN: cols}[code]
        i = min(max(0, i + step), len(self.visible) - 1)
        self.current = self.visible[i]
        self.reveal(self.current)
        self.update_detail()
        self.grid.setNeedsDisplay_(True)
        return True

    def toggle(self, name):
        st, miss = self.state[name]
        if st == C.CHECKED:
            del self.checked[name]
        elif st == C.AVAILABLE:
            self.checked[name] = self.modes[name]
        else:
            if st == C.LOCKED:
                NSBeep()
            self.update_detail()
            self.grid.setNeedsDisplay_(True)
            return
        self.recompute()

    def filterChanged_(self, sender):
        self.apply_filter()

    def modeChanged_(self, sender):
        name = self.current
        if name is None:
            return
        mode = C.MODES[sender.get()]
        if mode not in self.items[name]["modes"]:
            NSBeep()
            self.update_detail()
            return
        self.modes[name] = mode
        if name in self.checked:
            self.checked[name] = mode
        self.recompute()

    def preferChanged_(self, sender):
        self.prefer = PREFER[sender.get()][1]
        for name, it in self.items.items():
            self.modes[name] = C.default_mode(it, self.prefer)
        for name in self.checked:
            self.checked[name] = self.modes[name]
        self.recompute()

    def checkAll_(self, sender):
        self.checked = C.check_all(self.items, self.visible, self.glyphs, self.features,
                                   self.checked, self.modes)
        self.recompute()

    def clear_(self, sender):
        self.checked = {}
        self.recompute()

    def needDoubleClicked_(self, sender):
        sel = sender.getSelectedIndexes()
        if not sel or sel[0] >= len(self._need_names):
            return
        name = self._need_names[sel[0]]
        if name not in self.items:
            return
        if name not in self.visible:
            self.w.filter.set(0)
            self.w.search.set("")
            self.w.hideInFont.set(False)
            self.w.hideLocked.set(False)
            if self.feature_only(name):
                self.w.showFeatures.set(True)
            self.current = name
            self.apply_filter()
        self.current = name
        self.reveal(name)
        self.update_detail()
        self.grid.setNeedsDisplay_(True)

    def forget_(self, sender):
        name = self.current
        if name is None or name not in self.features:
            return
        feats = set(self.features)
        feats.discard(name)
        glyphbuild.set_recorded_features(self.font, feats)
        self.refresh_font()

    def becameKey_(self, sender):
        if self.font not in Glyphs.fonts:
            return
        self.refresh_font()

    def closed_(self, sender):
        NSNotificationCenter.defaultCenter().removeObserver_(self.grid)
        self.grid.ctl = None
        self.preview.ctl = None

    # -- detail + status ------------------------------------------------------ #

    def update_status(self):
        counts = {}
        for m in self.valid.values():
            counts[m] = counts.get(m, 0) + 1
        parts = ["%d %s" % (counts[m], MODE_TITLES[m].lower()) for m in C.MODES if m in counts]
        n = len(self.valid)
        text = ("%d to add (%s)" % (n, ", ".join(parts))) if n else "Nothing ticked"
        missing = sum(1 for s, _ in self.state.values() if s not in (C.IN_FONT, C.BY_FEATURES))
        text += " · %d shown · %d to go" % (len(self.visible), missing)
        if self._hidden_features:
            text += " · %d feature-only hidden" % self._hidden_features
        if self._dropped:
            text += " · unticked %d whose parents are gone" % len(self._dropped)
        self.w.status.set(text)
        self.w.add.setTitle("Add %d Glyph%s" % (n, "" if n == 1 else "s") if n else "Add")
        self.w.add.enable(bool(n))

    def update_detail(self):
        w = self.w
        name = self.current
        self.preview.setNeedsDisplay_(True)
        if name is None:
            for ctl in (w.name, w.info, w.note, w.recipe):
                ctl.set("")
            w.needs.set([])
            self._need_names = []
            w.mode.enable(False)
            w.forget.show(False)
            return
        it = self.items[name]
        st, miss = self.state[name]
        w.name.set(name)
        info = []
        if it.get("text"):
            info.append("%s  %s" % (it["text"], " ".join("U+%04X" % ord(c) for c in it["text"])))
        line = []
        line.append("stage %d" % it["stage"] if it.get("stage") is not None else "unscheduled")
        if it.get("freq"):
            line.append("in %s corpus sentences" % format(it["freq"], ","))
        info.append(" · ".join(line))
        w.info.set("\n".join(info))
        titles = {g["id"]: g["title"] for g in self.cat["groups"]}
        note = ", ".join(titles.get(g, g) for g in it["groups"])
        if it.get("note"):
            note += "\n" + it["note"]
        w.note.set(note)

        mode = self.checked.get(name) or self.modes[name]
        w.mode.enable(st not in (C.IN_FONT, C.BY_FEATURES))
        seg = w.mode.getNSSegmentedButton()
        for i, m in enumerate(C.MODES):
            seg.setEnabled_forSegment_(m in it["modes"], i)
        w.mode.set(C.MODES.index(mode))
        w.forget.show(st == C.BY_FEATURES)

        recipe = {
            C.DRAW: ("seeded from %s, then redesigned" % it["seed"] if it.get("seed")
                     else "an outline glyph" + (", started from " + " + ".join(
                         it.get("parts") or it.get("components"))
                         if (it.get("parts") or it.get("components")) else "")),
            C.COMPOSITE: " + ".join(it.get("components") or []),
            C.FEATURES: "no glyph: shaped from " + " + ".join(
                it.get("parts") or it.get("components") or ["its parts"]),
        }[mode]
        rec = "%s — %s" % (MODE_TITLES[mode], recipe)
        if mode == it["default"]:
            rec += " (recommended)"
        else:
            rec += " · recommended: %s" % MODE_TITLES[it["default"]].lower()
        if st == C.IN_FONT:
            rec = "Already in the font" + (" (drawn)" if name in self.designed else " (empty)")
        elif st == C.BY_FEATURES:
            rec = "Recorded as made by features"
        w.recipe.set(rec)

        deps = []
        for d in it.get("requires", ()):
            deps.append(d)
        for d in (it.get("components") if mode == C.COMPOSITE
                  else it.get("parts") or it.get("components")) or ():
            if d not in deps:
                deps.append(d)
        if it.get("seed") and it["seed"] not in deps:
            deps.append(it["seed"])
        rows, names = [], []
        for d in deps:
            if d in self.glyphs:
                mark = "✓  %s — in the font" % d
            elif d in self.features:
                mark = "✓  %s — by features" % d
            elif d in self.valid:
                mark = "✓  %s — ticked" % d
            elif d in miss:
                mark = "✗  %s — missing" % d
            else:
                mark = "✓  %s — seeded from %s" % (d, C.plain(d))
            rows.append(mark)
            names.append(d)
        self._need_names = names
        w.needsLabel.set("Needs (double-click to go there)" if rows else "Needs nothing")
        w.needs.set(rows)

    # -- add ------------------------------------------------------------------ #

    def add_(self, sender):
        if not self.valid:
            return NSBeep()
        if self.font not in Glyphs.fonts:
            Glyphs.showNotification(glyphbuild.TITLE, "The font was closed.")
            return self.w.close()
        plugin = self.plugin
        if plugin is not None:
            plugin._busy = True
        try:
            made = glyphbuild.add_items(self.font, self.cmap, self.items, dict(self.valid),
                                        from_parts=bool(self.w.fromParts.get()))
        except Exception:
            Glyphs.showMacroWindow()
            print(traceback.format_exc())
            Glyphs.showNotification(glyphbuild.TITLE, "Adding failed — see Macro Window.")
            return
        finally:
            if plugin is not None:
                plugin._busy = False
                plugin._known[id(self.font)] = glyphbuild.glyph_names(self.font)
        self.checked = {}
        self.refresh_font()
        self.report(made)

    def report(self, made):
        glyphs = made[C.DRAW] + made[C.COMPOSITE]
        parts = []
        for key, label in ((C.DRAW, "drawn"), (C.COMPOSITE, "composite"),
                           (C.FEATURES, "by features")):
            if made[key]:
                parts.append("%d %s" % (len(made[key]), label))
        if made["seeded"]:
            parts.append("%d sign variant(s) seeded" % len(made["seeded"]))
        msg = "Added " + (", ".join(parts) or "nothing")
        if made["skipped"]:
            msg += "; skipped %d (see Macro Window)" % len(made["skipped"])
            print("Sinhala Glyph Builder — skipped:")
            for name, reason in made["skipped"]:
                print("  %-22s %s" % (name, reason))
        Glyphs.showNotification(glyphbuild.TITLE, msg + ".")
        tab = "".join("/" + n for n in glyphs + made["seeded"])
        if tab:
            self.font.newTab(tab)

# encoding: utf-8
"""Feature Assignments dialog for the Lanka Features plugin (vanilla UI).

Two tabs:

* Rule groups — every lookup the generator produced (TouchLigatures,
  RakarLigatures, VowelLig_abvs ...). Route each to dlig / hlig / liga / clig /
  calt / ss01-ss20, moving it out of its normal feature or copying it.
* Alternates — glyphs named base.alt / base.alt2 ... form alternate indices.
  Index N feeds ssNN by default; route an index to another tag instead, or keep
  it out of every feature except aalt.

The dialog edits plain data only ({"groups": [...], "alts": {...}}, see
lankafea.assign) and hands it to ``on_save``; storing it is the plugin's job.
"""

from __future__ import division, print_function, unicode_literals

import vanilla

from lankafea.assign import (NONE_TARGET, TARGET_TAGS,
                             default_alt_tag)

GROUP_DEFAULT = "Default (as generated)"
ALT_DEFAULT = "Default (ssNN)"
ALT_NONE = "aalt only (no feature)"

GROUP_ROUTES = [GROUP_DEFAULT] + TARGET_TAGS
ALT_ROUTES = [ALT_DEFAULT, ALT_NONE] + TARGET_TAGS
MODES = ["Move", "Copy"]


class AssignmentsDialog(object):

    def __init__(self, title, info, assign, handwritten, on_save):
        """
        info        lankafea.api.Assignables for the font
        assign      current settings as plain dict (may be empty)
        handwritten feature tags the user wrote by hand (generated code for them
                    is kept out unless listed under Replace Hand-Written)
        on_save     callable(plain_assign, generate_now)
        """
        self._on_save = on_save
        self._handwritten = set(handwritten)
        assign = assign or {}

        stored = {g["group"]: g for g in (assign.get("groups") or [])}
        self._groups = []
        seen = set()
        for g in info.groups:
            cur = stored.get(g.name)
            seen.add(g.name)
            self._groups.append({
                "group": g.name,
                "default": g.feature,
                "rules": "%d / %d" % (g.present or 0, g.rules),
                "route": cur["to"] if cur else GROUP_DEFAULT,
                "mode": (cur.get("mode") or "move").capitalize() if cur else "Move",
                "comment": g.comment,
                "present": g.present or 0,
            })
        for name, cur in stored.items():           # saved, but not generated now
            if name not in seen:
                self._groups.append({
                    "group": name, "default": "—", "rules": "not generated",
                    "route": cur["to"],
                    "mode": (cur.get("mode") or "move").capitalize(),
                    "comment": "Not produced for this font any more.",
                    "present": 0,
                })
        self._group_by_name = {r["group"]: r for r in self._groups}

        stored_alts = dict((assign.get("alts") or {}))
        self._alts = []
        seen_idx = set()
        for a in info.alts:
            seen_idx.add(a.index)
            self._alts.append(self._alt_row(
                a.index, a.count, ", ".join(a.examples), stored_alts.get(str(a.index))))
        for key, tag in stored_alts.items():
            try:
                idx = int(key)
            except ValueError:
                continue
            if idx not in seen_idx:
                self._alts.append(self._alt_row(idx, 0, "(no such glyphs now)", tag))
        self._alts.sort(key=lambda r: r["index"])

        self._build(title)
        self._refilter()
        self._alt_list.set([dict(r) for r in self._alts])
        self._refresh_notes()

    # -- construction --------------------------------------------------------- #

    @staticmethod
    def _alt_row(idx, count, examples, tag):
        if tag is None or tag == default_alt_tag(idx):
            route = ALT_DEFAULT
        elif tag == NONE_TARGET:
            route = ALT_NONE
        else:
            route = tag
        return {"index": idx,
                "suffix": ".alt" if idx == 1 else ".alt%d" % idx,
                "count": count, "examples": examples, "route": route}

    def _build(self, title):
        w = self.w = vanilla.Window((860, 600), "Feature Assignments — %s" % title,
                                    minSize=(700, 460))
        w.intro = vanilla.TextBox(
            (15, 12, -15, 34),
            "Choose where generated rules end up. Settings are saved inside the "
            "font file (userData), so they travel with the .glyphspackage.",
            sizeStyle="small")
        w.tabs = vanilla.Tabs((10, 50, -10, -120),
                              ["Rule groups", "Alternates (.alt → ss / dlig)"])

        # ---- rule groups ---------------------------------------------------- #
        t = w.tabs[0]
        t.search = vanilla.SearchBox((10, 8, 260, 22), callback=self._filter_cb)
        t.onlyLive = vanilla.CheckBox(
            (280, 9, -10, 20), "Only groups with rules this font can use",
            value=False, callback=self._filter_cb, sizeStyle="small")
        t.list = vanilla.List(
            (10, 38, -10, -64), [],
            columnDescriptions=[
                {"title": "Group", "key": "group", "width": 190, "editable": False},
                {"title": "Generated in", "key": "default", "width": 90,
                 "editable": False},
                {"title": "Rules usable", "key": "rules", "width": 100,
                 "editable": False},
                {"title": "Route to", "key": "route", "width": 170,
                 "cell": vanilla.PopUpButtonListCell(GROUP_ROUTES),
                 "binding": "selectedValue"},
                {"title": "Mode", "key": "mode", "width": 80,
                 "cell": vanilla.PopUpButtonListCell(MODES),
                 "binding": "selectedValue"},
            ],
            allowsMultipleSelection=True, drawVerticalLines=True,
            selectionCallback=self._group_select, editCallback=self._group_edit)
        t.detail = vanilla.TextBox((10, -56, -10, 30), "", sizeStyle="small")
        t.bulkLabel = vanilla.TextBox((10, -24, 90, 17), "Selected rows:",
                                      sizeStyle="small")
        t.bulkRoute = vanilla.PopUpButton((100, -26, 190, 20), GROUP_ROUTES,
                                          sizeStyle="small")
        t.bulkMode = vanilla.PopUpButton((300, -26, 80, 20), MODES,
                                         sizeStyle="small")
        t.bulkSet = vanilla.Button((390, -27, 90, 20), "Set",
                                   callback=self._bulk_set, sizeStyle="small")
        self._group_list = t.list
        self._group_tab = t

        # ---- alternates ----------------------------------------------------- #
        a = w.tabs[1]
        a.help = vanilla.TextBox(
            (10, 8, -10, 46),
            "Glyphs named base.alt, base.alt2, base.alt3 … are alternates. "
            "Index N normally becomes stylistic set ssNN. Route an index "
            "elsewhere, or keep it out of every feature except aalt. If two "
            "indices share one tag, the lower index wins for a base glyph both "
            "define.", sizeStyle="small")
        a.list = vanilla.List(
            (10, 60, -10, -10), [],
            columnDescriptions=[
                {"title": "Index", "key": "suffix", "width": 70, "editable": False},
                {"title": "Glyphs", "key": "count", "width": 60, "editable": False},
                {"title": "Examples (base glyphs)", "key": "examples",
                 "width": 300, "editable": False},
                {"title": "Route to", "key": "route", "width": 190,
                 "cell": vanilla.PopUpButtonListCell(ALT_ROUTES),
                 "binding": "selectedValue"},
            ],
            allowsMultipleSelection=True, drawVerticalLines=True,
            editCallback=self._alt_edit)
        self._alt_list = a.list

        # ---- footer --------------------------------------------------------- #
        w.notes = vanilla.TextBox((15, -112, -15, 56), "", sizeStyle="small")
        w.clear = vanilla.Button((15, -46, 110, 22), "Clear All",
                                 callback=self._clear)
        w.cancel = vanilla.Button((-370, -46, 80, 22), "Cancel",
                                  callback=self._cancel)
        w.save = vanilla.Button((-280, -46, 80, 22), "Save", callback=self._save)
        w.saveGen = vanilla.Button((-190, -46, 175, 22), "Save & Generate",
                                   callback=self._save_generate)
        w.setDefaultButton(w.saveGen)
        w.open()
        w.makeKey()

    # -- group tab ------------------------------------------------------------ #

    def _filter_cb(self, sender):
        self._refilter()

    def _refilter(self):
        t = self._group_tab
        needle = (t.search.get() or "").strip().lower()
        only_live = bool(t.onlyLive.get())
        rows = []
        for r in self._groups:
            if only_live and not r["present"]:
                continue
            if needle and needle not in r["group"].lower() \
                    and needle not in r["default"].lower() \
                    and needle not in r["route"].lower():
                continue
            rows.append(dict(r))
        self._group_list.set(rows)

    def _group_edit(self, sender):
        for row in sender.get():
            master = self._group_by_name.get(row["group"])
            if master is not None:
                master["route"] = row["route"]
                master["mode"] = row["mode"]
        self._refresh_notes()

    def _group_select(self, sender):
        items = sender.get()
        sel = sender.getSelection()
        if len(sel) == 1:
            row = items[sel[0]]
            self._group_tab.detail.set(
                "%s — generated in %s. %s" % (row["group"], row["default"],
                                              row["comment"] or ""))
        else:
            self._group_tab.detail.set(
                "%d groups selected" % len(sel) if sel else "")

    def _bulk_set(self, sender):
        t = self._group_tab
        route = GROUP_ROUTES[t.bulkRoute.get()]
        mode = MODES[t.bulkMode.get()]
        items = self._group_list.get()
        for i in self._group_list.getSelection():
            master = self._group_by_name.get(items[i]["group"])
            if master is not None:
                master["route"] = route
                master["mode"] = mode
        self._refilter()
        self._refresh_notes()

    # -- alternates tab ------------------------------------------------------- #

    def _alt_edit(self, sender):
        by_index = {r["index"]: r for r in self._alts}
        for row in sender.get():
            master = by_index.get(row["index"])
            if master is not None:
                master["route"] = row["route"]
        self._refresh_notes()

    # -- result --------------------------------------------------------------- #

    def result(self):
        groups = [
            {"group": r["group"], "to": r["route"], "mode": r["mode"].lower()}
            for r in self._groups if r["route"] != GROUP_DEFAULT]
        alts = {}
        for r in self._alts:
            if r["route"] == ALT_DEFAULT:
                continue
            alts[str(r["index"])] = NONE_TARGET if r["route"] == ALT_NONE \
                else r["route"]
        return {"groups": groups, "alts": alts}

    def _refresh_notes(self):
        res = self.result()
        notes = []
        used = {}
        for g in res["groups"]:
            used.setdefault(g["to"], []).append(g["group"])
        for idx, tag in res["alts"].items():
            if tag != NONE_TARGET:
                used.setdefault(tag, []).append("alt %s" % idx)
        for r in self._alts:                       # untouched indices keep ssNN
            if r["route"] == ALT_DEFAULT:
                used.setdefault(default_alt_tag(r["index"]), []).append(
                    "alt %d" % r["index"])
        for tag in sorted(used):
            if len(used[tag]) > 1 and (tag in {g["to"] for g in res["groups"]}
                                       or tag == "dlig"):
                notes.append("%s will hold: %s." % (tag, ", ".join(used[tag])))
        clash = sorted(t for t in used if t in self._handwritten
                       and (t in {g["to"] for g in res["groups"]}
                            or t in res["alts"].values()))
        if clash:
            notes.append(
                "You already hand-wrote %s: generated code for it is kept out "
                "unless you list it under “Replace Hand-Written Features…”."
                % ", ".join(clash))
        n = len(res["groups"]) + len(res["alts"])
        head = "%d assignment%s." % (n, "" if n == 1 else "s") if n \
            else "No assignments: everything is generated in its default feature."
        self.w.notes.set(head + ("  " + "  ".join(notes) if notes else ""))

    # -- buttons -------------------------------------------------------------- #

    def _clear(self, sender):
        for r in self._groups:
            r["route"] = GROUP_DEFAULT
            r["mode"] = "Move"
        for r in self._alts:
            r["route"] = ALT_DEFAULT
        self._refilter()
        self._alt_list.set([dict(r) for r in self._alts])
        self._refresh_notes()

    def _cancel(self, sender):
        self.w.close()

    def _save(self, sender):
        self._on_save(self.result(), False)
        self.w.close()

    def _save_generate(self, sender):
        self._on_save(self.result(), True)
        self.w.close()

/*
 * Sinhala spacing workbench.
 *
 * Edits the spacing scheme (tools/_generated/sinhala-spacing.js, vendored from
 * sinhala-spacing.yaml by `python -m spacing_map export-js`) and previews it on
 * a real font:
 *
 *   - classes: drag members between classes, set reps, add classes, mark
 *     exceptions
 *   - values: per-class target sidebearing as a multiple of spacing_unit,
 *     plus optional per-font overrides in font units
 *   - preview: HarfBuzz-shaped text drawn twice — the font as-is, and with
 *     the scheme applied the way `apply` will wire it (every member takes its
 *     class target; an unset value means "inherit the rep's sidebearing")
 *
 * Exports: the scheme YAML, a per-font values file, and the model changes the
 * membership edits imply (relationships are rebuilt from the design-stages
 * model, so they must be ported there to survive `build-map`).
 */
(function () {
  "use strict";

  var VENDORED = window.SinhalaSpacing;
  var STORE_KEY = "sinhala-spacing-workbench:v1";
  var SIDES = ["left", "right"];
  var UNIT_GLYPH = "ට";            // the model's unit-defining glyph
  var DRIFT_TOLERANCE = 8;         // font units per 1000 upem (CLI audit default)
  var POOL = "__unassigned";
  var VALUE_MAX = 3;

  var PRESETS = {
    spacing: "තම්මැට්ටම්නුල",
    pangram: "බක්මහා ආරේන්දුවක් සුළං දැවැන්තය",
    prose: "ශ්‍රී විද්‍යාශේඛර විද්‍යාලයේ ශිෂ්‍ය ශිෂ්‍යාවෝ පනහක් පමණ ආචාර්‍ය්‍ය මණ්ඩලයේ සිවුදෙනෙකු සමඟ අධ්‍යාපන චාරිකාවක නිරත වූහ. ඔවුහු උදෑසන පාසල් කාර්යාලය අසලදී පඤ්ච ශීලය සමාදන් වී කොළඹ බලා පිටත් වූහ.",
  };

  // ---------------------------------------------------------------------------
  // state

  function clone(o) { return JSON.parse(JSON.stringify(o)); }

  var state = {
    scheme: clone(VENDORED),
    font: null,           // Shaper FontHandle
    fontBuffer: null,
    entryGid: new Map(),  // scheme entry -> gid
    gidEntry: new Map(),  // gid -> scheme entry
    absent: [],
    unit: { left: null, right: null },
    measuredUnit: { left: null, right: null },
    overrides: { left: {}, right: {} },
    side: "right",
    selectedClass: null,  // {side, cname}
    selectedEntry: null,
    showForms: false,
    view: { preset: "class", mode: "both", size: 56, guides: true, custom: "" },
    perFont: {},          // font name -> {unit, overrides} (persisted)
  };

  var index = { left: new Map(), right: new Map() };  // entry -> class name
  var formFamily = new Map();                          // form entry -> family id
  var baseIndex = { left: new Map(), right: new Map() };

  // ---------------------------------------------------------------------------
  // scheme helpers

  function buildIndex(scheme, into) {
    SIDES.forEach(function (side) {
      into[side] = new Map();
      var classes = (scheme.classes && scheme.classes[side]) || {};
      Object.keys(classes).forEach(function (cname) {
        (classes[cname].members || []).forEach(function (m) {
          if (!into[side].has(m)) into[side].set(m, cname);
        });
      });
      Object.keys(scheme.forms || {}).forEach(function (fam) {
        var glyphs = scheme.forms[fam].glyphs || {};
        Object.keys(glyphs).forEach(function (form) {
          var c = glyphs[form][side];
          if (c) into[side].set(form, c);
        });
      });
    });
  }

  function rebuildIndex() {
    buildIndex(state.scheme, index);
    formFamily = new Map();
    Object.keys(state.scheme.forms || {}).forEach(function (fam) {
      Object.keys(state.scheme.forms[fam].glyphs || {}).forEach(function (form) {
        formFamily.set(form, fam);
      });
    });
  }

  function isForm(entry) { return formFamily.has(entry); }

  function allEntries() {
    var s = new Set();
    SIDES.forEach(function (side) {
      index[side].forEach(function (_, e) { s.add(e); });
      (state.scheme.unassigned && state.scheme.unassigned[side] || []).forEach(function (e) { s.add(e); });
    });
    Object.keys(state.scheme.exceptions || {}).forEach(function (e) { s.add(e); });
    s.add(UNIT_GLYPH);
    return Array.from(s);
  }

  function classesOf(side) { return state.scheme.classes[side] || {}; }

  function isException(entry, side) {
    var ex = state.scheme.exceptions && state.scheme.exceptions[entry];
    return !!(ex && ex[side]);
  }

  function formsOfClass(side, cname) {
    var out = [];
    index[side].forEach(function (c, e) { if (c === cname && isForm(e)) out.push(e); });
    return out;
  }

  // ---------------------------------------------------------------------------
  // measurement

  function measured(entry) {
    if (!state.font) return null;
    var gid = state.entryGid.get(entry);
    if (gid == null) return null;
    return state.font.sidebearings(gid);
  }

  function sbOf(entry, side) {
    var m = measured(entry);
    return m ? m[side] : null;
  }

  function tolerance() {
    return state.font ? DRIFT_TOLERANCE * state.font.upem / 1000 : DRIFT_TOLERANCE;
  }

  /** Measured rep sidebearing as a multiple of the measured unit. */
  function impliedValue(side, cname) {
    var cls = classesOf(side)[cname];
    var u = state.measuredUnit[side];
    var v = cls && cls.rep ? sbOf(cls.rep, side) : null;
    if (!u || v == null) return null;
    return Math.round((v / u) * 1000) / 1000;
  }

  /** Target sidebearing (font units) for a class, and where it comes from. */
  function classTarget(side, cname) {
    var cls = classesOf(side)[cname];
    if (!cls) return null;
    var ov = state.overrides[side][cname];
    if (ov != null && ov !== "") return { v: Number(ov), src: "override" };
    if (cls.value != null && state.unit[side]) {
      return { v: Math.round(cls.value * state.unit[side]), src: "value" };
    }
    var rv = cls.rep ? sbOf(cls.rep, side) : null;
    if (rv != null) return { v: rv, src: "rep" };
    return null;
  }

  function entryTarget(entry, side) {
    if (isException(entry, side)) return null;
    var cname = index[side].get(entry);
    return cname ? classTarget(side, cname) : null;
  }

  function driftMembers(side, cname) {
    var cls = classesOf(side)[cname];
    if (!state.font || !cls || !cls.rep) return [];
    var rv = sbOf(cls.rep, side);
    if (rv == null) return [];
    var tol = tolerance();
    var out = [];
    (cls.members || []).concat(formsOfClass(side, cname)).forEach(function (e) {
      if (e === cls.rep || isException(e, side)) return;
      var v = sbOf(e, side);
      if (v != null && Math.abs(v - rv) > tol) out.push(e);
    });
    return out;
  }

  // ---------------------------------------------------------------------------
  // edits

  function moveEntry(side, entry, toClass) {
    if (toClass === POOL) toClass = null;
    var classes = classesOf(side);
    if (isForm(entry)) {
      state.scheme.forms[formFamily.get(entry)].glyphs[entry][side] = toClass;
    } else {
      Object.keys(classes).forEach(function (cname) {
        var cls = classes[cname];
        var i = (cls.members || []).indexOf(entry);
        if (i < 0 || cname === toClass) return;
        cls.members.splice(i, 1);
        if (cls.rep === entry) cls.rep = cls.members[0] || null;
      });
      var pool = state.scheme.unassigned[side];
      var pi = pool.indexOf(entry);
      if (toClass) {
        if (pi >= 0) pool.splice(pi, 1);
        var to = classes[toClass];
        if (to.members.indexOf(entry) < 0) to.members.push(entry);
        if (!to.rep) to.rep = entry;
      } else if (pi < 0) {
        pool.push(entry);
      }
    }
    changed();
  }

  function setRep(side, cname, entry) {
    var cls = classesOf(side)[cname];
    if (!cls) return;
    if (!isForm(entry) && cls.members.indexOf(entry) < 0) moveEntry(side, entry, cname);
    cls.rep = entry;
    changed();
  }

  function setException(entry, side, on) {
    var ex = state.scheme.exceptions || (state.scheme.exceptions = {});
    if (on) {
      ex[entry] = ex[entry] || {};
      ex[entry][side] = { reason: "set in spacing workbench — bespoke sidebearing" };
    } else if (ex[entry]) {
      delete ex[entry][side];
      if (!Object.keys(ex[entry]).length) delete ex[entry];
    }
    changed();
  }

  function addClass(side, name) {
    var classes = classesOf(side);
    if (classes[name]) { toast("class " + name + " already exists"); return; }
    classes[name] = { rep: null, members: [], value: null, note: "Added in the spacing workbench." };
    state.selectedClass = { side: side, cname: name };
    changed();
  }

  function setValue(side, cname, v) {
    var cls = classesOf(side)[cname];
    cls.value = v == null || isNaN(v) ? null : Math.round(v * 1000) / 1000;
    changed({ list: false });
  }

  function changed(opts) {
    opts = opts || {};
    rebuildIndex();
    persist();
    if (opts.list !== false) renderSidebar();
    else updateCardNumbers();
    renderInspector();
    if (state.view.preset === "class") setPresetText();
    renderPreview();
    renderChangeCount();
  }

  // ---------------------------------------------------------------------------
  // change tracking (vs the vendored scheme)

  function computeChanges() {
    var out = { membership: [], reps: [], newClasses: [], values: [], exceptions: [] };
    var base = VENDORED;
    SIDES.forEach(function (side) {
      var seen = new Set();
      [baseIndex[side], index[side]].forEach(function (m) { m.forEach(function (_, e) { seen.add(e); }); });
      seen.forEach(function (e) {
        var was = baseIndex[side].get(e) || null, now = index[side].get(e) || null;
        if (was !== now) out.membership.push({ side: side, entry: e, was: was, now: now, form: isForm(e) });
      });
      var cur = classesOf(side), old = base.classes[side] || {};
      Object.keys(cur).forEach(function (cname) {
        if (!old[cname]) { out.newClasses.push({ side: side, cname: cname, cls: cur[cname] }); return; }
        if (old[cname].rep !== cur[cname].rep) {
          out.reps.push({ side: side, cname: cname, was: old[cname].rep, now: cur[cname].rep });
        }
        if ((old[cname].value == null ? null : old[cname].value) !== (cur[cname].value == null ? null : cur[cname].value)) {
          out.values.push({ side: side, cname: cname, was: old[cname].value, now: cur[cname].value });
        }
      });
    });
    var exOld = base.exceptions || {}, exNew = state.scheme.exceptions || {};
    var keys = new Set(Object.keys(exOld).concat(Object.keys(exNew)));
    keys.forEach(function (e) {
      SIDES.forEach(function (side) {
        var a = !!(exOld[e] && exOld[e][side]), b = !!(exNew[e] && exNew[e][side]);
        if (a !== b) out.exceptions.push({ entry: e, side: side, now: b });
      });
    });
    return out;
  }

  function changeTotal(c) {
    return c.membership.length + c.reps.length + c.newClasses.length + c.values.length + c.exceptions.length;
  }

  function renderChangeCount() {
    var n = changeTotal(computeChanges());
    var b = $("changeCount");
    b.hidden = !n;
    b.textContent = n;
  }

  // ---------------------------------------------------------------------------
  // persistence (per-viewer convenience only; the exports are the record)

  function persist() {
    try {
      if (state.font) {
        state.perFont[state.font.name] = { unit: state.unit, overrides: state.overrides };
      }
      localStorage.setItem(STORE_KEY, JSON.stringify({
        model_version: VENDORED.meta && VENDORED.meta.model_version,
        generated: schemeFingerprint(VENDORED),
        scheme: state.scheme,
        perFont: state.perFont,
        view: state.view,
        side: state.side,
        showForms: state.showForms,
      }));
    } catch (e) { /* storage unavailable: work stays in memory */ }
  }

  function schemeFingerprint(s) {
    var c = s.meta && s.meta.counts;
    return JSON.stringify([s.meta && s.meta.model_version, c]);
  }

  function restore() {
    var saved = null;
    try { saved = JSON.parse(localStorage.getItem(STORE_KEY) || "null"); } catch (e) { saved = null; }
    if (!saved) return;
    if (saved.generated !== schemeFingerprint(VENDORED)) {
      toast("The vendored scheme changed since your last session — saved edits were set aside. Re-import an exported YAML to recover them.");
      return;
    }
    if (saved.scheme && saved.scheme.classes) state.scheme = saved.scheme;
    if (saved.perFont) state.perFont = saved.perFont;
    if (saved.view) Object.assign(state.view, saved.view);
    if (saved.side) state.side = saved.side;
    state.showForms = !!saved.showForms;
  }

  // ---------------------------------------------------------------------------
  // DOM helpers

  function $(id) { return document.getElementById(id); }

  function el(tag, attrs, children) {
    var n = document.createElement(tag);
    if (attrs) Object.keys(attrs).forEach(function (k) {
      var v = attrs[k];
      if (v == null || v === false) return;
      if (k === "class") n.className = v;
      else if (k === "text") n.textContent = v;
      else if (k.slice(0, 2) === "on") n.addEventListener(k.slice(2), v);
      else if (k === "dataset") Object.assign(n.dataset, v);
      else n.setAttribute(k, v === true ? "" : v);
    });
    (children || []).forEach(function (c) {
      if (c == null) return;
      n.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
    });
    return n;
  }

  var toastTimer = null;
  function toast(msg) {
    var t = $("toast");
    t.textContent = msg;
    t.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { t.hidden = true; }, 4200);
  }

  function fmt(v, digits) {
    if (v == null) return "—";
    return digits != null ? Number(v).toFixed(digits) : String(v);
  }

  function codepoints(s) {
    return Array.from(s).map(function (c) {
      return "U+" + c.codePointAt(0).toString(16).toUpperCase().padStart(4, "0");
    }).join(" ");
  }

  // ---------------------------------------------------------------------------
  // sidebar: class cards

  function chip(entry, side, opts) {
    opts = opts || {};
    var cls = ["chip"];
    if (opts.rep) cls.push("rep");
    if (isForm(entry)) cls.push("form");
    if (opts.drift) cls.push("drift");
    if (state.font && !state.entryGid.has(entry)) cls.push("absent");
    if (isException(entry, side)) cls.push("exception");
    if (state.selectedEntry === entry) cls.push("active");
    var flag = state.scheme.flags && state.scheme.flags[entry];
    var sb = sbOf(entry, side);
    var title = entry + "  " + codepoints(entry)
      + (sb != null ? "\n" + side + " sidebearing: " + sb : "")
      + (opts.rep ? "\nrep — sets the class sidebearing" : "")
      + (opts.drift ? "\ndrifts from the rep by more than " + Math.round(tolerance()) + " u" : "")
      + (state.font && !state.entryGid.has(entry) ? "\nnot a single glyph in this font" : "")
      + (flag ? "\n⚑ " + flag : "")
      + "\nclick: inspect · double-click: make rep · drag: move";
    var c = el("span", {
      class: cls.join(" "),
      draggable: "true",
      title: title,
      dataset: { entry: entry, side: side },
    }, [entry, flag && /FLAG/.test(flag) ? el("span", { class: "flag", text: "?" }) : null]);
    c.addEventListener("dragstart", function (ev) {
      ev.dataTransfer.setData("application/x-spacing-entry", JSON.stringify({ entry: entry, side: side }));
      ev.dataTransfer.effectAllowed = "move";
    });
    c.addEventListener("click", function (ev) {
      ev.stopPropagation();
      selectEntry(entry);
    });
    c.addEventListener("dblclick", function (ev) {
      ev.stopPropagation();
      var cname = index[side].get(entry);
      if (cname) setRep(side, cname, entry);
    });
    return c;
  }

  function dropZone(node, side, cname) {
    node.addEventListener("dragover", function (ev) {
      if (ev.dataTransfer.types.indexOf("application/x-spacing-entry") < 0) return;
      ev.preventDefault();
      node.classList.add("drag-over");
    });
    node.addEventListener("dragleave", function () { node.classList.remove("drag-over"); });
    node.addEventListener("drop", function (ev) {
      node.classList.remove("drag-over");
      var raw = ev.dataTransfer.getData("application/x-spacing-entry");
      if (!raw) return;
      ev.preventDefault();
      ev.stopPropagation();
      var d = JSON.parse(raw);
      if (d.side !== side) { toast("Classes are per side — switch tabs to move the other side."); return; }
      moveEntry(side, d.entry, cname);
    });
  }

  function classCard(side, cname) {
    var cls = classesOf(side)[cname];
    var drift = driftMembers(side, cname);
    var selected = state.selectedClass && state.selectedClass.side === side && state.selectedClass.cname === cname;
    var forms = formsOfClass(side, cname);

    var head = el("div", { class: "card-head", onclick: function () { selectClass(side, cname); } }, [
      el("span", { class: "rep-glyph", text: cls.rep || "·" }),
      el("div", null, [
        el("div", { class: "name", text: cname }),
        el("div", { class: "meta", text: (cls.members || []).length + " members" + (forms.length ? " · " + forms.length + " forms" : "") }),
      ]),
      drift.length ? el("span", { class: "drift", text: drift.length + " drift" }) : null,
    ]);

    var unset = cls.value == null;
    var range = el("input", { type: "range", min: "0", max: String(VALUE_MAX), step: "0.01",
      value: String(unset ? (impliedValue(side, cname) || 1) : cls.value) });
    var num = el("input", { type: "number", min: "0", max: "10", step: "0.01",
      value: unset ? "" : String(cls.value), placeholder: "unset" });
    range.addEventListener("input", function () {
      num.value = range.value;
      row.classList.remove("unset");
      setValue(side, cname, parseFloat(range.value));
    });
    num.addEventListener("input", function () {
      var v = num.value === "" ? null : parseFloat(num.value);
      if (v != null) range.value = String(v);
      row.classList.toggle("unset", v == null);
      setValue(side, cname, v);
    });
    var clear = el("button", { class: "btn small", type: "button", title: "Unset: members inherit the rep's own sidebearing",
      onclick: function () { num.value = ""; row.classList.add("unset"); setValue(side, cname, null); } }, ["×"]);
    var row = el("div", { class: "value-row" + (unset ? " unset" : "") }, [range, num, clear]);

    var ov = state.overrides[side][cname];
    var ovInput = el("input", { type: "number", step: "1", placeholder: "—", value: ov == null ? "" : String(ov),
      title: "Per-font override in font units — replaces value × unit for this font only", disabled: !state.font });
    ovInput.addEventListener("input", function () {
      if (ovInput.value === "") delete state.overrides[side][cname];
      else state.overrides[side][cname] = Number(ovInput.value);
      changed({ list: false });
    });

    var implied = impliedValue(side, cname);
    var adopt = implied != null ? el("button", { class: "linkish", type: "button", title: "Use the multiple measured in this font",
      onclick: function () { setValue(side, cname, implied); renderSidebar(); } }, ["use"]) : null;

    var meta = el("div", { class: "value-meta" }, [
      el("span", { class: "target", dataset: { target: side + "/" + cname } }),
      el("span", null, ["font: " + fmt(implied, 2) + "×", adopt ? " " : null, adopt]),
      el("label", null, ["override ", ovInput]),
    ]);

    var members = el("div", { class: "members", dataset: { drop: cname } });
    (cls.members || []).forEach(function (m) {
      members.appendChild(chip(m, side, { rep: m === cls.rep, drift: drift.indexOf(m) >= 0 }));
    });
    if (!(cls.members || []).length) members.appendChild(el("span", { class: "empty", text: "drop glyphs here — the first becomes the rep" }));
    dropZone(members, side, cname);

    var formsRow = null;
    if (forms.length && state.showForms) {
      var fm = el("div", { class: "members" });
      forms.forEach(function (f) { fm.appendChild(chip(f, side, { rep: f === cls.rep, drift: drift.indexOf(f) >= 0 })); });
      formsRow = el("details", { class: "forms-row", open: true }, [el("summary", { text: forms.length + " fused forms (move them here; port as form_overrides)" }), fm]);
      dropZone(fm, side, cname);
    }

    var note = cls.note ? el("div", { class: "note", text: cls.note }) : null;

    var card = el("div", { class: "card" + (selected ? " selected" : ""), dataset: { card: side + "/" + cname } },
      [head, row, meta, note, members, formsRow]);
    return card;
  }

  function poolCard(side) {
    var pool = (state.scheme.unassigned && state.scheme.unassigned[side]) || [];
    var forms = [];
    formFamily.forEach(function (_, f) { if (!index[side].get(f)) forms.push(f); });
    var members = el("div", { class: "members", dataset: { drop: POOL } });
    pool.concat(forms).forEach(function (m) { members.appendChild(chip(m, side)); });
    if (!pool.length && !forms.length) members.appendChild(el("span", { class: "empty", text: "empty — drag here to unassign" }));
    dropZone(members, side, POOL);
    return el("div", { class: "card pool" }, [
      el("div", { class: "card-head" }, [el("div", null, [
        el("div", { class: "name", text: "Unassigned" }),
        el("div", { class: "meta", text: "spacing glyphs with no " + side + " class" }),
      ])]),
      members,
    ]);
  }

  function renderSidebar() {
    document.querySelectorAll(".sidetabs button").forEach(function (b) {
      b.classList.toggle("active", b.dataset.side === state.side);
    });
    $("showForms").checked = state.showForms;
    var list = $("classList");
    var scroll = list.parentNode.scrollTop;
    list.innerHTML = "";
    list.appendChild(poolCard(state.side));
    Object.keys(classesOf(state.side)).forEach(function (cname) {
      list.appendChild(classCard(state.side, cname));
    });
    updateCardNumbers();
    list.parentNode.scrollTop = scroll;
    $("fillValues").disabled = !state.font;
  }

  /** Cheap refresh of the computed numbers without rebuilding cards (keeps slider focus). */
  function updateCardNumbers() {
    document.querySelectorAll("[data-target]").forEach(function (n) {
      var parts = n.dataset.target.split("/");
      var t = classTarget(parts[0], parts[1]);
      var src = t ? { override: "override", value: "value × unit", rep: "inherits rep" }[t.src] : "";
      n.textContent = t ? "→ " + t.v + " u (" + src + ")" : (state.font ? "→ —" : "load a font for targets");
    });
  }

  // ---------------------------------------------------------------------------
  // inspector

  function selectEntry(entry) {
    state.selectedEntry = state.selectedEntry === entry ? null : entry;
    renderSidebar();
    renderInspector();
    renderPreview();
  }

  function selectClass(side, cname) {
    var same = state.selectedClass && state.selectedClass.side === side && state.selectedClass.cname === cname;
    state.selectedClass = same ? null : { side: side, cname: cname };
    renderSidebar();
    if (state.view.preset === "class") setPresetText();
    renderPreview();
  }

  function renderInspector() {
    var box = $("inspector");
    var e = state.selectedEntry;
    if (!e) { box.hidden = true; box.innerHTML = ""; return; }
    box.hidden = false;
    box.innerHTML = "";
    var m = measured(e);
    var gid = state.entryGid.get(e);
    var facts = el("div", { class: "facts" }, [
      el("div", null, [el("code", { text: codepoints(e) })]),
      el("div", { text: isForm(e) ? "fused form · family " + formFamily.get(e) : "character" }),
      el("div", { text: state.font
        ? (gid != null ? "glyph id " + gid + " · advance " + fmt(m && m.adv) : "not a single glyph in this font")
        : "load a font to measure" }),
    ]);
    box.appendChild(el("div", { class: "top" }, [
      el("div", { class: "big", text: e }),
      facts,
      el("button", { class: "close", title: "close", onclick: function () { selectEntry(e); } }, ["×"]),
    ]));

    var rows = SIDES.map(function (side) {
      var cname = index[side].get(e) || "";
      var sel = el("select", { title: "Move to another " + side + " class" });
      sel.appendChild(el("option", { value: POOL, text: "— unassigned —" }));
      Object.keys(classesOf(side)).forEach(function (c) {
        sel.appendChild(el("option", { value: c, text: c, selected: c === cname }));
      });
      if (!cname) sel.value = POOL;
      sel.addEventListener("change", function () { moveEntry(side, e, sel.value); });
      var cls = cname ? classesOf(side)[cname] : null;
      var t = entryTarget(e, side);
      var repBtn = cls && cls.rep !== e
        ? el("button", { class: "btn small", type: "button", onclick: function () { setRep(side, cname, e); } }, ["make rep"])
        : (cls ? el("span", { class: "muted", text: "rep" }) : null);
      var exc = el("input", { type: "checkbox", checked: isException(e, side) });
      exc.addEventListener("change", function () { setException(e, side, exc.checked); });
      return el("tr", null, [
        el("th", { text: side }),
        el("td", null, [sel]),
        el("td", { text: "sb " + fmt(m && m[side]) + (t ? " → " + t.v : "") }),
        el("td", null, [repBtn]),
        el("td", { title: "Exception: keeps its own sidebearing on this side" }, [el("label", { class: "check" }, [exc, "own"])]),
      ]);
    });
    box.appendChild(el("table", null, rows));
    var flag = state.scheme.flags && state.scheme.flags[e];
    if (flag) box.appendChild(el("div", { class: "flagnote", text: "⚑ " + flag }));
  }

  // ---------------------------------------------------------------------------
  // font loading

  function loadFontFile(file) {
    if (!/\.(ttf|otf)$/i.test(file.name)) {
      toast("Use a .ttf or .otf (WOFF/WOFF2 aren't decoded by the shaper).");
      return;
    }
    $("fontName").textContent = "loading " + file.name + "…";
    file.arrayBuffer().then(function (buf) {
      return Shaper.loadFont(buf.slice(0), file.name).then(function (handle) {
        if (state.font) state.font.destroy();
        state.font = handle;
        state.fontBuffer = buf;
        return installFontFace(buf);
      });
    }).then(function () {
      mapEntries();
      var saved = state.perFont[state.font.name];
      state.unit = saved && saved.unit ? saved.unit : Object.assign({}, state.measuredUnit);
      state.overrides = saved && saved.overrides ? saved.overrides : { left: {}, right: {} };
      SIDES.forEach(function (s) { state.overrides[s] = state.overrides[s] || {}; });
      $("fontName").textContent = state.font.name + " · " + state.font.upem + " upem";
      $("dropHint").hidden = true;
      ["unitLeft", "unitRight", "unitReset"].forEach(function (id) { $(id).disabled = false; });
      renderUnit();
      persist();
      renderSidebar();
      renderInspector();
      renderPreview();
    }).catch(function (err) {
      console.error(err);
      $("fontName").textContent = "could not load " + file.name;
      toast("Font load failed: " + err.message);
    });
  }

  var fontFace = null;
  function installFontFace(buf) {
    if (fontFace) document.fonts.delete(fontFace);
    fontFace = new FontFace("WorkbenchFont", buf);
    return fontFace.load().then(function (f) { document.fonts.add(f); }).catch(function () { /* chips fall back */ });
  }

  function mapEntries() {
    state.entryGid = new Map();
    state.gidEntry = new Map();
    state.absent = [];
    allEntries().forEach(function (e) {
      var r = state.font.resolve(e);
      if (!r) { state.absent.push(e); return; }
      state.entryGid.set(e, r.gid);
      if (!state.gidEntry.has(r.gid)) state.gidEntry.set(r.gid, e);
    });
    var u = measured(UNIT_GLYPH);
    state.measuredUnit = { left: u ? u.left : null, right: u ? u.right : null };
  }

  function renderUnit() {
    $("unitLeft").value = state.unit.left == null ? "" : state.unit.left;
    $("unitRight").value = state.unit.right == null ? "" : state.unit.right;
  }

  // ---------------------------------------------------------------------------
  // preview text

  function isDependent(ch) {
    var c = ch.codePointAt(0);
    return (c >= 0x0D81 && c <= 0x0D83) || (c >= 0x0DCA && c <= 0x0DDF) || c === 0x0DF2 || c === 0x0DF3;
  }

  function unitString(e) { return isDependent(e) ? UNIT_GLYPH + e : e; }

  function setPresetText() {
    var p = state.view.preset, text;
    if (p === "custom") text = state.view.custom;
    else if (p === "class") text = classStrings();
    else if (p === "letters") text = letterStrings();
    else if (p === "forms") text = formStrings();
    else text = PRESETS[p] || "";
    $("text").value = text;
    $("text").readOnly = p !== "custom";
  }

  function classStrings() {
    var sc = state.selectedClass;
    if (!sc) return "ටටකටකකටට ටටගටගගටට ටටදටදදටට ටටපටපපටට ටටඔටඔඔටට";  // generic until a class card is selected
    var cls = classesOf(sc.side)[sc.cname];
    if (!cls) return "";
    var rep = cls.rep ? unitString(cls.rep) : UNIT_GLYPH;
    var entries = (cls.members || []).concat(formsOfClass(sc.side, sc.cname));
    return entries.map(function (m) {
      var u = unitString(m);
      return "ටට" + u + "ට" + u + u + "ටට  " + rep + u + rep + u + rep;
    }).join("\n");
  }

  function letterStrings() {
    var seen = [];
    SIDES.forEach(function (side) {
      index[side].forEach(function (_, e) {
        if (!isForm(e) && !isDependent(e) && Array.from(e).length === 1 && seen.indexOf(e) < 0) seen.push(e);
      });
    });
    seen.sort();
    var lines = [];
    for (var i = 0; i < seen.length; i += 8) {
      lines.push(seen.slice(i, i + 8).map(function (e) { return "ට" + e + "ට"; }).join(" "));
    }
    return lines.join("\n");
  }

  function formStrings() {
    var forms = Array.from(formFamily.keys());
    var lines = [];
    for (var i = 0; i < forms.length; i += 8) {
      lines.push(forms.slice(i, i + 8).map(function (f) { return "ට" + f + "ට"; }).join(" "));
    }
    return lines.join("\n");
  }

  // ---------------------------------------------------------------------------
  // preview rendering

  var hitBoxes = [];

  /** Shape one line and position it, optionally with the scheme applied. */
  function layoutLine(text, applied) {
    var f = state.font;
    var out = f.shape(text);
    var pen = 0, lastDR = 0, glyphs = [];
    var chars = text;
    out.forEach(function (g) {
      var entry = state.gidEntry.get(g.g) || null;
      var isMark = g.ax === 0;
      var dL = 0, dR = 0, tL = null, tR = null;
      var sb = isMark ? null : f.sidebearings(g.g, f.advance.get(g.g));
      if (applied && entry && sb) {
        tL = entryTarget(entry, "left");
        tR = entryTarget(entry, "right");
        if (tL) dL = tL.v - sb.left;
        if (tR) dR = tR.v - sb.right;
      }
      var x = pen + g.dx + dL - (isMark ? lastDR : 0);
      if (!isMark) lastDR = dR;
      glyphs.push({
        gid: g.g, entry: entry, x: x, y: g.dy, pen: pen, adv: g.ax + dL + dR, isMark: isMark,
        sb: sb, dL: dL, dR: dR, space: chars.charAt(g.cl) === " ",
      });
      pen += g.ax + dL + dR;
    });
    return { glyphs: glyphs, width: pen };
  }

  /** Greedy wrap at space glyphs. Returns rows of {glyphs, offset}. */
  function wrap(line, maxWidth) {
    var rows = [], start = 0, rowStartX = 0, lastBreak = -1;
    var g = line.glyphs;
    for (var i = 0; i < g.length; i++) {
      if (g[i].space) lastBreak = i;
      if (g[i].pen + g[i].adv - rowStartX > maxWidth && lastBreak > start) {
        rows.push({ glyphs: g.slice(start, lastBreak), offset: rowStartX });
        start = lastBreak + 1;
        rowStartX = start < g.length ? g[start].pen : 0;
        lastBreak = -1;
      }
    }
    rows.push({ glyphs: g.slice(start), offset: rowStartX });
    return rows;
  }

  function cssVar(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }

  function renderPreview() {
    var canvas = $("preview");
    var wrapEl = $("canvasWrap");
    var ctx = canvas.getContext("2d");
    hitBoxes = [];
    if (!state.font) { canvas.width = 0; canvas.height = 0; renderStatus(); return; }

    var dpr = window.devicePixelRatio || 1;
    var width = Math.max(200, wrapEl.clientWidth - 32);
    var size = state.view.size;
    var scale = size / state.font.upem;
    var gutter = state.view.mode === "both" ? 18 : 0;
    var maxUnits = (width - gutter - 8) / scale;
    var rowH = Math.round(size * 1.55);
    var baseline = Math.round(size * 1.05);

    var modes = state.view.mode === "both" ? [false, true] : [state.view.mode === "scheme"];
    var lines = $("text").value.split("\n");
    var blocks = [];
    lines.forEach(function (text) {
      if (!text.trim()) { blocks.push({ gap: true }); return; }
      var laid = modes.map(function (applied) { return { applied: applied, rows: wrap(layoutLine(text, applied), maxUnits) }; });
      var n = Math.max.apply(null, laid.map(function (l) { return l.rows.length; }));
      for (var r = 0; r < n; r++) {
        laid.forEach(function (l, k) {
          blocks.push({ applied: l.applied, row: l.rows[r], first: k === 0, last: k === laid.length - 1 });
        });
      }
    });

    var height = 8;
    blocks.forEach(function (b) { height += b.gap ? rowH * 0.4 : (b.last && modes.length > 1 ? rowH + 10 : rowH); });
    canvas.style.width = width + "px";
    canvas.style.height = height + "px";
    canvas.width = Math.round(width * dpr);
    canvas.height = Math.round(height * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, width, height);

    var ink = cssVar("--ink"), muted = cssVar("--muted");
    var leftTint = cssVar("--left-tint"), rightTint = cssVar("--right-tint");
    var guide = cssVar("--guide"), guide2 = cssVar("--guide-2"), warn = cssVar("--warn");
    var sel = state.selectedClass;

    var y = 4;
    blocks.forEach(function (b) {
      if (b.gap) { y += rowH * 0.4; return; }
      if (!b.row) { y += rowH; return; }
      var base = y + baseline;
      if (gutter) {
        ctx.fillStyle = muted;
        ctx.font = "600 10px " + cssVar("--font-ui");
        ctx.fillText(b.applied ? "S" : "F", 2, base);
      }
      var x0 = gutter;
      b.row.glyphs.forEach(function (g, i) {
        var gx = x0 + (g.pen - b.row.offset) * scale;
        var info = state.font.glyph(g.gid);
        if (state.view.guides && !g.isMark) {
          ctx.fillStyle = i % 2 ? guide2 : guide;
          ctx.fillRect(gx, y + 2, g.adv * scale, rowH - 8);
          var inSel = sel && g.entry && index[sel.side].get(g.entry) === sel.cname && !isException(g.entry, sel.side);
          if (info.bounds && g.sb) {
            var lsb = (g.sb.left + g.dL) * scale, rsb = (g.sb.right + g.dR) * scale;
            if (inSel && sel.side === "left") { ctx.fillStyle = leftTint; ctx.fillRect(gx, y + 2, lsb, rowH - 8); }
            if (inSel && sel.side === "right") { ctx.fillStyle = rightTint; ctx.fillRect(gx + g.adv * scale - rsb, y + 2, rsb, rowH - 8); }
          }
          if (!g.entry && !g.space && info.bounds) {
            ctx.strokeStyle = warn;
            ctx.setLineDash([2, 2]);
            ctx.beginPath();
            ctx.moveTo(gx + 1, y + rowH - 5);
            ctx.lineTo(gx + g.adv * scale - 1, y + rowH - 5);
            ctx.stroke();
            ctx.setLineDash([]);
          }
        }
        if (info.path) {
          var drawX = x0 + (g.x - b.row.offset) * scale;
          ctx.save();
          ctx.translate(drawX, base - g.y * scale);
          ctx.scale(scale, -scale);
          // Black-and-white: a selected entry stays ink, everything else greys out.
          ctx.fillStyle = state.selectedEntry && g.entry !== state.selectedEntry ? muted : ink;
          ctx.fill(info.path);
          ctx.restore();
        }
        if (!g.isMark) {
          hitBoxes.push({ x0: gx, x1: gx + g.adv * scale, y0: y, y1: y + rowH, g: g, applied: b.applied });
        }
      });
      y += b.last && modes.length > 1 ? rowH + 10 : rowH;
    });
    renderStatus();
  }

  function renderStatus() {
    var s = $("status");
    s.innerHTML = "";
    if (!state.font) {
      s.appendChild(el("span", { text: "No font loaded. Scheme: " + Object.keys(classesOf("right")).length
        + " right / " + Object.keys(classesOf("left")).length + " left classes." }));
      return;
    }
    var total = allEntries().length;
    var drift = 0;
    SIDES.forEach(function (side) { Object.keys(classesOf(side)).forEach(function (c) { drift += driftMembers(side, c).length; }); });
    s.appendChild(el("span", { text: (total - state.absent.length) + "/" + total + " scheme entries are single glyphs in this font",
      title: state.absent.length ? "absent: " + state.absent.join(" ") : "" }));
    s.appendChild(el("span", { text: drift + " members drift from their rep (±" + Math.round(tolerance()) + " u)" }));
    s.appendChild(el("span", { text: "ට measures L " + fmt(state.measuredUnit.left) + " / R " + fmt(state.measuredUnit.right) }));
    s.appendChild(el("span", { class: "legend" }, [el("span", { class: "sw", style: "background:" + cssVar("--left-tint") }), "sidebearings of the selected class"]));
    s.appendChild(el("span", { class: "legend" }, [el("span", { class: "sw", style: "border-bottom:2px dashed " + cssVar("--warn") }), "glyph not in the scheme"]));
  }

  function hit(ev) {
    var r = $("preview").getBoundingClientRect();
    var x = ev.clientX - r.left, y = ev.clientY - r.top;
    for (var i = 0; i < hitBoxes.length; i++) {
      var h = hitBoxes[i];
      if (x >= h.x0 && x < h.x1 && y >= h.y0 && y < h.y1) return h;
    }
    return null;
  }

  function onCanvasMove(ev) {
    var tip = $("tooltip");
    var h = hit(ev);
    if (!h || h.g.space) { tip.hidden = true; return; }
    var g = h.g, e = g.entry;
    var lines = [];
    lines.push(e ? el("b", { text: e }) : el("span", { text: "glyph " + g.gid + " — not in the scheme" }));
    if (g.sb) {
      lines.push(el("div", { text: "L " + (g.sb.left + g.dL) + (g.dL ? " (" + (g.dL > 0 ? "+" : "") + g.dL + ")" : "")
        + "   R " + (g.sb.right + g.dR) + (g.dR ? " (" + (g.dR > 0 ? "+" : "") + g.dR + ")" : "") }));
    }
    if (e) {
      lines.push(el("div", { text: "left " + (index.left.get(e) || "—") + (isException(e, "left") ? " (own)" : "")
        + " · right " + (index.right.get(e) || "—") + (isException(e, "right") ? " (own)" : "") }));
    }
    lines.push(el("div", { class: "muted", text: h.applied ? "scheme applied" : "font as-is" }));
    tip.innerHTML = "";
    lines.forEach(function (n) { tip.appendChild(n); });
    var wr = $("canvasWrap").getBoundingClientRect();
    tip.style.left = (ev.clientX - wr.left + $("canvasWrap").scrollLeft + 14) + "px";
    tip.style.top = (ev.clientY - wr.top + $("canvasWrap").scrollTop + 14) + "px";
    tip.hidden = false;
  }

  function onCanvasClick(ev) {
    var h = hit(ev);
    if (h && h.g.entry) selectEntry(h.g.entry);
  }

  // ---------------------------------------------------------------------------
  // import / export

  function dumpYaml(obj) {
    return jsyaml.dump(obj, { lineWidth: 100, noRefs: true, sortKeys: false });
  }

  function today() { return new Date().toISOString().slice(0, 10); }

  function exportScheme() {
    var c = computeChanges();
    var head = [
      "# sinhala-spacing.yaml — exported from tools/spacing-workbench on " + today() + ".",
      "# Values, notes and exceptions survive `python -m spacing_map build-map`.",
    ];
    if (c.membership.length || c.reps.length || c.newClasses.length) {
      head.push("# This file also carries " + (c.membership.length + c.reps.length + c.newClasses.length)
        + " relationship edit(s); build-map rebuilds relationships from the",
        "# design-stages model, so port them there too (see the workbench's Model changes tab).");
    }
    return head.join("\n") + "\n" + dumpYaml(state.scheme);
  }

  function exportValues() {
    if (!state.font) return null;
    var measuredVals = { right: {}, left: {} };
    SIDES.forEach(function (side) {
      Object.keys(classesOf(side)).forEach(function (cname) {
        var v = impliedValue(side, cname);
        if (v != null) measuredVals[side][cname] = v;
      });
    });
    var targets = { right: {}, left: {} };
    SIDES.forEach(function (side) {
      Object.keys(classesOf(side)).forEach(function (cname) {
        var t = classTarget(side, cname);
        if (t) targets[side][cname] = t.v;
      });
    });
    var doc = {
      meta: {
        kind: "spacing-values",
        font: state.font.name,
        upem: state.font.upem,
        scheme_model_version: VENDORED.meta && VENDORED.meta.model_version,
        exported_by: "tools/spacing-workbench",
        exported: today(),
        note: "spacing_unit and overrides are authored for this font; targets and measured are informational.",
      },
      spacing_unit: { left: state.unit.left, right: state.unit.right },
      overrides: { right: state.overrides.right, left: state.overrides.left },
      targets: targets,
      measured: measuredVals,
    };
    return "# Per-font spacing values — exported from tools/spacing-workbench.\n" + dumpYaml(doc);
  }

  function exportModelChanges() {
    var c = computeChanges();
    var L = [
      "# Spacing workbench — relationship edits, " + today() + ".",
      "# Port these into model/sinhala-design-dependencies.yaml, then",
      "# run `python -m spacing_map build-map`. Until then build-map reverts them in",
      "# sinhala-spacing.yaml.",
      "",
    ];
    var glyph = c.membership.filter(function (m) { return !m.form; });
    var forms = c.membership.filter(function (m) { return m.form; });
    if (glyph.length) {
      L.push("# per-glyph `spacing:` declarations (core members lists may need the same move)");
      var byEntry = {};
      glyph.forEach(function (m) { (byEntry[m.entry] = byEntry[m.entry] || []).push(m); });
      Object.keys(byEntry).forEach(function (e) {
        var parts = byEntry[e].map(function (m) { return m.side + ": " + (m.now || "null"); });
        var was = byEntry[e].map(function (m) { return m.side + " was " + (m.was || "unassigned"); });
        L.push(e + ":  spacing: {" + parts.join(", ") + "}    # " + was.join(", "));
      });
      L.push("");
    }
    if (forms.length) {
      L.push("# fused forms → the family's form_overrides");
      var byFam = {};
      forms.forEach(function (m) { (byFam[formFamily.get(m.entry)] = byFam[formFamily.get(m.entry)] || []).push(m); });
      Object.keys(byFam).forEach(function (fam) {
        L.push(fam + ":");
        L.push("  form_overrides:");
        byFam[fam].forEach(function (m) {
          L.push("    " + m.entry + ": {" + m.side + ": " + (m.now || "null") + "}    # was " + (m.was || "unassigned"));
        });
      });
      L.push("");
    }
    if (c.reps.length) {
      L.push("# class reps — spacing_classes.<side>.<class>.rep");
      c.reps.forEach(function (r) { L.push(r.side + "." + r.cname + ".rep: " + r.now + "    # was " + r.was); });
      L.push("");
    }
    if (c.newClasses.length) {
      L.push("# new classes — add under spacing_classes.<side>");
      c.newClasses.forEach(function (n) {
        L.push(n.side + "." + n.cname + ": {rep: " + (n.cls.rep || "null") + ", members: [" + (n.cls.members || []).join(", ") + "]}");
      });
      L.push("");
    }
    if (c.values.length || c.exceptions.length) {
      L.push("# (values and exceptions live in sinhala-spacing.yaml itself — nothing to port:");
      L.push("#  " + c.values.length + " value change(s), " + c.exceptions.length + " exception change(s))");
    }
    if (L.length === 5) L.push("# no relationship edits — nothing to port.");
    return L.join("\n") + "\n";
  }

  var exportTab = "scheme";
  function renderExport() {
    document.querySelectorAll("#exportDialog .tabs button").forEach(function (b) {
      b.classList.toggle("active", b.dataset.tab === exportTab);
    });
    var c = computeChanges();
    var text, note;
    if (exportTab === "scheme") {
      text = exportScheme();
      note = "Replace sinhala-spacing.yaml with this, then run `python -m spacing_map export-js` to refresh the workbench data. "
        + c.values.length + " value change(s), " + c.exceptions.length + " exception change(s), "
        + (c.membership.length + c.reps.length + c.newClasses.length) + " relationship edit(s).";
    } else if (exportTab === "values") {
      text = exportValues();
      note = text ? "Per-font values for " + state.font.name + ": the spacing unit in font units plus per-class overrides. Re-import it here to restore a session."
        : "Load a font to export its values file.";
      text = text || "";
    } else {
      text = exportModelChanges();
      note = "Relationship edits (membership, reps, new classes) as model edits — the model is their source of truth.";
    }
    $("exportText").value = text;
    $("exportNote").textContent = note;
  }

  function exportFilename() {
    if (exportTab === "scheme") return "sinhala-spacing.yaml";
    if (exportTab === "values") return "spacing-values-" + (state.font ? state.font.name.replace(/\.[^.]+$/, "") : "font") + ".yaml";
    return "spacing-model-changes.yaml";
  }

  function download(name, text) {
    var a = el("a", { href: URL.createObjectURL(new Blob([text], { type: "text/yaml;charset=utf-8" })), download: name });
    document.body.appendChild(a);
    a.click();
    setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 0);
  }

  function importYaml(file) {
    file.text().then(function (txt) {
      var doc = jsyaml.load(txt);
      if (!doc || typeof doc !== "object") throw new Error("empty YAML");
      if (doc.classes && doc.classes.right && doc.classes.left) {
        state.scheme = doc;
        ["forms", "exceptions", "flags"].forEach(function (k) { if (!state.scheme[k]) state.scheme[k] = {}; });
        if (!state.scheme.unassigned) state.scheme.unassigned = { left: [], right: [] };
        if (state.font) { rebuildIndex(); mapEntries(); }
        toast("Imported scheme from " + file.name);
      } else if (doc.spacing_unit && (doc.overrides || (doc.meta && doc.meta.kind === "spacing-values"))) {
        if (!state.font) throw new Error("load the font first, then import its values file");
        state.unit = { left: doc.spacing_unit.left, right: doc.spacing_unit.right };
        state.overrides = { left: (doc.overrides && doc.overrides.left) || {}, right: (doc.overrides && doc.overrides.right) || {} };
        renderUnit();
        toast("Imported unit + " + (Object.keys(state.overrides.left).length + Object.keys(state.overrides.right).length) + " override(s)");
      } else if (doc.values && doc.meta && doc.meta.spacing_unit) {
        // `spacing_map audit --emit-values` output: measured multiples
        var n = 0;
        SIDES.forEach(function (side) {
          Object.keys(doc.values[side] || {}).forEach(function (cname) {
            if (classesOf(side)[cname]) { classesOf(side)[cname].value = doc.values[side][cname]; n++; }
          });
        });
        if (state.font && doc.meta.font && doc.meta.spacing_unit) {
          state.unit = { left: doc.meta.spacing_unit.left, right: doc.meta.spacing_unit.right };
          renderUnit();
        }
        toast("Imported " + n + " measured value(s) from " + (doc.meta.font || file.name) + " as scheme values");
      } else {
        throw new Error("not a spacing scheme, values file, or audit --emit-values output");
      }
      changed();
    }).catch(function (err) { toast("Import failed: " + err.message); });
  }

  // ---------------------------------------------------------------------------
  // wiring

  function wire() {
    $("fontInput").addEventListener("change", function (ev) { if (ev.target.files[0]) loadFontFile(ev.target.files[0]); ev.target.value = ""; });
    $("yamlInput").addEventListener("change", function (ev) { if (ev.target.files[0]) importYaml(ev.target.files[0]); ev.target.value = ""; });

    var dragDepth = 0;
    document.addEventListener("dragenter", function (ev) {
      if (ev.dataTransfer.types.indexOf("Files") >= 0) { dragDepth++; document.body.classList.add("dragging"); }
    });
    document.addEventListener("dragleave", function (ev) {
      if (ev.dataTransfer.types.indexOf("Files") >= 0 && --dragDepth <= 0) { dragDepth = 0; document.body.classList.remove("dragging"); }
    });
    document.addEventListener("dragover", function (ev) { if (ev.dataTransfer.types.indexOf("Files") >= 0) ev.preventDefault(); });
    document.addEventListener("drop", function (ev) {
      if (!ev.dataTransfer.files.length) return;
      ev.preventDefault();
      dragDepth = 0;
      document.body.classList.remove("dragging");
      Array.from(ev.dataTransfer.files).forEach(function (f) {
        if (/\.ya?ml$/i.test(f.name)) importYaml(f); else loadFontFile(f);
      });
    });

    document.querySelectorAll(".sidetabs button").forEach(function (b) {
      b.addEventListener("click", function () { state.side = b.dataset.side; persist(); renderSidebar(); });
    });
    $("showForms").addEventListener("change", function (ev) { state.showForms = ev.target.checked; persist(); renderSidebar(); });

    $("addClassForm").addEventListener("submit", function (ev) {
      ev.preventDefault();
      var name = $("newClassName").value.trim();
      if (!name) return;
      var prefix = state.side === "right" ? "R-" : "L-";
      if (!/^[RL]-/.test(name)) name = prefix + name;
      addClass(state.side, name);
      $("newClassName").value = "";
    });

    $("fillValues").addEventListener("click", function () {
      var n = 0;
      SIDES.forEach(function (side) {
        Object.keys(classesOf(side)).forEach(function (cname) {
          var cls = classesOf(side)[cname], v = impliedValue(side, cname);
          if (cls.value == null && v != null) { cls.value = v; n++; }
        });
      });
      toast(n ? "Filled " + n + " unset value(s) from " + state.font.name : "No unset values to fill");
      changed();
    });

    function unitInput(side, id) {
      $(id).addEventListener("input", function () {
        state.unit[side] = $(id).value === "" ? null : Number($(id).value);
        changed({ list: false });
      });
    }
    unitInput("left", "unitLeft");
    unitInput("right", "unitRight");
    $("unitReset").addEventListener("click", function () {
      state.unit = Object.assign({}, state.measuredUnit);
      renderUnit();
      changed({ list: false });
    });

    $("preset").addEventListener("change", function (ev) { state.view.preset = ev.target.value; setPresetText(); persist(); renderPreview(); });
    $("mode").addEventListener("change", function (ev) { state.view.mode = ev.target.value; persist(); renderPreview(); });
    $("size").addEventListener("input", function (ev) {
      state.view.size = Number(ev.target.value);
      $("sizeOut").textContent = ev.target.value;
      renderPreview();
    });
    $("size").addEventListener("change", persist);
    $("guides").addEventListener("change", function (ev) { state.view.guides = ev.target.checked; persist(); renderPreview(); });
    $("text").addEventListener("input", function () {
      if (state.view.preset === "custom") state.view.custom = $("text").value;
      persist();
      renderPreview();
    });
    $("text").addEventListener("focus", function () {
      if (state.view.preset !== "custom") {
        state.view.custom = $("text").value;
        state.view.preset = "custom";
        $("preset").value = "custom";
        $("text").readOnly = false;
      }
    });

    $("preview").addEventListener("mousemove", onCanvasMove);
    $("preview").addEventListener("mouseleave", function () { $("tooltip").hidden = true; });
    $("preview").addEventListener("click", onCanvasClick);
    var rt = null;
    window.addEventListener("resize", function () { clearTimeout(rt); rt = setTimeout(renderPreview, 80); });
    if (window.matchMedia) {
      window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", renderPreview);
    }

    $("exportBtn").addEventListener("click", function () { renderExport(); $("exportDialog").showModal(); });
    document.querySelectorAll("#exportDialog .tabs button").forEach(function (b) {
      b.addEventListener("click", function () { exportTab = b.dataset.tab; renderExport(); });
    });
    $("downloadBtn").addEventListener("click", function () {
      if ($("exportText").value) download(exportFilename(), $("exportText").value);
    });
    $("copyBtn").addEventListener("click", function () {
      navigator.clipboard.writeText($("exportText").value).then(
        function () { toast("Copied"); }, function () { $("exportText").select(); toast("Select-all done — copy with ⌘C"); });
    });
    var armed = false;
    $("discardBtn").addEventListener("click", function () {
      if (!armed) {
        armed = true;
        $("discardBtn").textContent = "Click again to discard";
        setTimeout(function () { armed = false; $("discardBtn").textContent = "Discard all edits"; }, 3000);
        return;
      }
      armed = false;
      $("discardBtn").textContent = "Discard all edits";
      state.scheme = clone(VENDORED);
      state.overrides = { left: {}, right: {} };
      state.unit = Object.assign({}, state.measuredUnit);
      state.selectedClass = null;
      state.selectedEntry = null;
      if (state.font) { rebuildIndex(); mapEntries(); }
      renderUnit();
      changed();
      renderExport();
      toast("Reset to the vendored scheme");
    });
  }

  function init() {
    if (!VENDORED) {
      document.body.innerHTML = "<p style='padding:2em'>Missing ../_generated/sinhala-spacing.js — run <code>python -m spacing_map export-js</code> in tools/spacing-map.</p>";
      return;
    }
    buildIndex(VENDORED, baseIndex);
    restore();
    rebuildIndex();
    var m = VENDORED.meta || {};
    $("schemeInfo").textContent = "scheme · model " + (m.model_version || "?") + " · "
      + Object.keys(VENDORED.classes.right).length + "R / " + Object.keys(VENDORED.classes.left).length + "L classes · "
      + Object.keys(VENDORED.forms || {}).length + " form families";
    $("preset").value = state.view.preset;
    $("mode").value = state.view.mode;
    $("size").value = state.view.size;
    $("sizeOut").textContent = state.view.size;
    $("guides").checked = state.view.guides;
    wire();
    setPresetText();
    renderSidebar();
    renderInspector();
    renderPreview();
    renderChangeCount();
    Shaper.init().catch(function (err) { toast("HarfBuzz failed to load (needs network for the CDN): " + err.message); });
  }

  init();
})();

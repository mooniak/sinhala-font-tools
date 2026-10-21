/*
 * shaper.js — HarfBuzz (harfbuzzjs WASM) wrapper for the spacing workbench.
 *
 * Shapes text, hands out glyph outlines as Path2D, and measures sidebearings
 * from outline bounds exactly as Glyphs displays them:
 *   LSB = xMin,  RSB = advance − xMax
 *
 * Scheme entries are resolved to glyphs BY SHAPING, not by name: an entry
 * (a letter, a sign, or a fused form such as ටි / ක්‍රි) maps to a glyph when
 * shaping its string yields exactly one glyph. That is naming-agnostic, and it
 * measures fusion policy the same way the CLI audit does — a font that
 * positions ි as a separate mark simply has no single glyph for ටි.
 */
(function (root) {
  "use strict";

  var HB_VERSION = "0.3.6";
  var HB_BASE = "https://cdn.jsdelivr.net/npm/harfbuzzjs@" + HB_VERSION + "/";
  var SHAPE_FLAGS = ["BOT", "EOT", "DO_NOT_INSERT_DOTTED_CIRCLE"];

  var hbPromise = null;

  function loadScript(src) {
    return new Promise(function (resolve, reject) {
      var s = document.createElement("script");
      s.src = src;
      s.onload = resolve;
      s.onerror = function () { reject(new Error("could not load " + src)); };
      document.head.appendChild(s);
    });
  }

  /** Load hbjs.js + hb.wasm once. */
  function init() {
    if (hbPromise) return hbPromise;
    hbPromise = loadScript(HB_BASE + "hbjs.js")
      .then(function () { return fetch(HB_BASE + "hb.wasm"); })
      .then(function (r) {
        if (!r.ok) throw new Error("hb.wasm: HTTP " + r.status);
        return r.arrayBuffer();
      })
      .then(function (bytes) { return WebAssembly.instantiate(bytes); })
      .then(function (result) { return root.hbjs(result.instance); });
    return hbPromise;
  }

  // --- outline bounds -------------------------------------------------------

  function extendQuad(b, p0, p1, p2, axis) {
    var d = p0 - 2 * p1 + p2;
    if (d === 0) return;
    var t = (p0 - p1) / d;
    if (t > 0 && t < 1) {
      var v = (1 - t) * (1 - t) * p0 + 2 * (1 - t) * t * p1 + t * t * p2;
      if (v < b[axis][0]) b[axis][0] = v;
      if (v > b[axis][1]) b[axis][1] = v;
    }
  }

  function extendCubic(b, p0, p1, p2, p3, axis) {
    // derivative: a t² + b t + c
    var a = -p0 + 3 * p1 - 3 * p2 + p3;
    var bb = 2 * (p0 - 2 * p1 + p2);
    var c = p1 - p0;
    var ts = [];
    if (Math.abs(a) < 1e-12) {
      if (bb !== 0) ts.push(-c / bb);
    } else {
      var disc = bb * bb - 4 * a * c;
      if (disc >= 0) {
        var sq = Math.sqrt(disc);
        ts.push((-bb + sq) / (2 * a), (-bb - sq) / (2 * a));
      }
    }
    ts.forEach(function (t) {
      if (t > 0 && t < 1) {
        var mt = 1 - t;
        var v = mt * mt * mt * p0 + 3 * mt * mt * t * p1 + 3 * mt * t * t * p2 + t * t * t * p3;
        if (v < b[axis][0]) b[axis][0] = v;
        if (v > b[axis][1]) b[axis][1] = v;
      }
    });
  }

  /** Exact bounds of an hb SVG path (absolute M/L/Q/C/Z commands). */
  function pathBounds(d) {
    var b = { x: [Infinity, -Infinity], y: [Infinity, -Infinity] };
    var cx = 0, cy = 0;
    function pt(x, y) {
      if (x < b.x[0]) b.x[0] = x;
      if (x > b.x[1]) b.x[1] = x;
      if (y < b.y[0]) b.y[0] = y;
      if (y > b.y[1]) b.y[1] = y;
    }
    var re = /([MLQCZ])([^MLQCZ]*)/g, m;
    while ((m = re.exec(d))) {
      var n = (m[2].match(/-?\d*\.?\d+(?:e[-+]?\d+)?/gi) || []).map(Number);
      switch (m[1]) {
        case "M": case "L":
          cx = n[0]; cy = n[1]; pt(cx, cy); break;
        case "Q":
          extendQuad(b, cx, n[0], n[2], "x"); extendQuad(b, cy, n[1], n[3], "y");
          cx = n[2]; cy = n[3]; pt(cx, cy); break;
        case "C":
          extendCubic(b, cx, n[0], n[2], n[4], "x"); extendCubic(b, cy, n[1], n[3], n[5], "y");
          cx = n[4]; cy = n[5]; pt(cx, cy); break;
      }
    }
    if (b.x[0] === Infinity) return null;
    return { xMin: b.x[0], xMax: b.x[1], yMin: b.y[0], yMax: b.y[1] };
  }

  // --- font handle ----------------------------------------------------------

  function FontHandle(hb, buffer, name) {
    this.hb = hb;
    this.name = name;
    this.blob = hb.createBlob(buffer);
    this.face = hb.createFace(this.blob, 0);
    this.font = hb.createFont(this.face);
    this.upem = this.face.upem;
    this._glyphs = new Map();     // gid -> outline info
    this.advance = new Map();     // gid -> nominal advance (from isolated shaping)
  }

  FontHandle.prototype.shape = function (text) {
    var b = this.hb.createBuffer();
    b.addText(text);
    b.guessSegmentProperties();
    b.setFlags(SHAPE_FLAGS);
    this.hb.shape(this.font, b);
    var out = b.json();
    b.destroy();
    for (var i = 0; i < out.length; i++) {
      if (!this.advance.has(out[i].g) && out[i].ax) this.advance.set(out[i].g, out[i].ax);
    }
    return out;
  };

  /** Outline + bounds for a glyph id (cached). */
  FontHandle.prototype.glyph = function (gid) {
    var g = this._glyphs.get(gid);
    if (g) return g;
    var d = this.font.glyphToPath(gid);
    var bounds = d ? pathBounds(d) : null;
    g = { gid: gid, d: d, path: d ? new Path2D(d) : null, bounds: bounds };
    this._glyphs.set(gid, g);
    return g;
  };

  /** Measured sidebearings of a glyph at a given advance (null if empty). */
  FontHandle.prototype.sidebearings = function (gid, adv) {
    var g = this.glyph(gid);
    if (adv == null) adv = this.advance.get(gid);
    if (!g.bounds || adv == null) return null;
    return {
      left: Math.round(g.bounds.xMin),
      right: Math.round(adv - g.bounds.xMax),
      adv: adv,
    };
  };

  /**
   * Resolve a scheme entry to a glyph by shaping it in isolation.
   * Returns {gid, adv} or null when it is not a single glyph in this font.
   */
  FontHandle.prototype.resolve = function (entry) {
    var gl = this.shape(entry).filter(function (g) { return g.g !== 0; });
    if (gl.length !== 1) return null;
    return { gid: gl[0].g, adv: gl[0].ax };
  };

  FontHandle.prototype.destroy = function () {
    this.font.destroy();
    this.face.destroy();
    this.blob.destroy();
  };

  function loadFont(buffer, name) {
    return init().then(function (hb) { return new FontHandle(hb, buffer, name); });
  }

  root.Shaper = { init: init, loadFont: loadFont, pathBounds: pathBounds, HB_VERSION: HB_VERSION };
})(typeof globalThis !== "undefined" ? globalThis : this);

/*
 * shaping-exceptions.js — GENERATED, DO NOT EDIT BY HAND.
 * Regenerate with: node tools/_generated/build-shaping-exceptions.js
 * Source of truth: glyphsets/shaping-exceptions.yaml
 */
(function (root) {
  "use strict";
  var DATA = {
  "rakaransaya": [
    "ඞ",
    "ඟ",
    "ඡ",
    "ජ",
    "ඤ",
    "ඥ",
    "ඨ",
    "ඪ",
    "ණ",
    "ඬ",
    "ථ",
    "න",
    "ඳ",
    "ඵ",
    "ඹ",
    "ය",
    "ර",
    "ල",
    "ළ",
    "ඞ්‍ග"
  ],
  "repaya": [
    "ඤ",
    "ඬ",
    "ර",
    "ක්‍ෂ",
    "ඞ්‍ග"
  ],
  "yansaya": [
    "ඥ",
    "ඹ",
    "ඤ්‍ජ"
  ]
};
  var EXPORTS = {
    rakaransayaExceptions: new Set(DATA.rakaransaya),
    repayaExceptions: new Set(DATA.repaya),
    yansayaExceptions: new Set(DATA.yansaya)
  };
  if (typeof module !== "undefined" && module.exports) {
    module.exports = EXPORTS;
  } else {
    root.LankaShapingExceptions = EXPORTS;
  }
})(typeof globalThis !== "undefined" ? globalThis : this);

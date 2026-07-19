"""Serialise the composite map to a vendored CommonJS/browser module, matching
the house style of tools/_generated/lanka-glyph-data.js (IIFE that exports via
module.exports for Node and a global for <script> loading)."""
import json

_HEADER = """/*
 * sinhala-composites.js — GENERATED, DO NOT EDIT BY HAND.
 * Regenerate with:  python -m composite_map export-js
 * Source of truth:  sinhala-composites.yaml  (built from Abhaya Libre + Noto Sans Sinhala)
 */
(function (root) {
  "use strict";
  var DATA = """

_FOOTER = """;
  if (typeof module !== "undefined" && module.exports) {
    module.exports = DATA;
  } else {
    root.SinhalaComposites = DATA;
  }
})(typeof globalThis !== "undefined" ? globalThis : this);
"""


def to_js(map_data):
    """Emit the browser/Node-consumable subset. The heavy provenance blocks
    (review, keep_drawn) stay in the YAML; the JS carries what tools render:
    the composite decomposition, the atoms, and the anchor system."""
    payload = {
        "meta": map_data.get("meta", {}),
        "atoms": map_data.get("atoms", {}),
        "anchors": map_data.get("anchors", {}),
        "composites": {
            name: spec["components"]
            for name, spec in map_data.get("composites", {}).items()
        },
    }
    body = json.dumps(payload, ensure_ascii=False, indent=2)
    body = "\n".join("  " + line for line in body.splitlines()).lstrip()
    return _HEADER + body + _FOOTER

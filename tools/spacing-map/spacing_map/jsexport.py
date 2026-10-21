"""Serialise the spacing scheme to a vendored CommonJS/browser module for the
spacing workbench, in the house style of tools/_generated/sinhala-composites.js
(IIFE that exports via module.exports for Node and a global for <script>
loading)."""
import json

_HEADER = """/*
 * sinhala-spacing.js — GENERATED, DO NOT EDIT BY HAND.
 * Regenerate with:  python -m spacing_map export-js
 * Source of truth:  sinhala-spacing.yaml  (built from the design-stages model)
 */
(function (root) {
  "use strict";
  var DATA = """

_FOOTER = """;
  if (typeof module !== "undefined" && module.exports) {
    module.exports = DATA;
  } else {
    root.SinhalaSpacing = DATA;
  }
})(typeof globalThis !== "undefined" ? globalThis : this);
"""

# top-level scheme sections the workbench reads; anything else stays in the YAML
SECTIONS = ("meta", "classes", "forms", "forms_note", "exceptions",
            "unassigned", "nonspacing", "flags")


def to_js(scheme):
    """Emit the whole scheme — it is small, and the workbench round-trips it
    back to YAML, so nothing it may re-export should be dropped."""
    payload = {k: scheme[k] for k in SECTIONS if k in scheme}
    body = json.dumps(payload, ensure_ascii=False, indent=2)
    body = "\n".join("  " + line for line in body.splitlines()).lstrip()
    return _HEADER + body + _FOOTER

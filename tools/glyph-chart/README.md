# Sinhala Glyph Chart

A browser-based font testing tool for Sinhala type designers: a 2D grid of
**base letters × vowel marks / compound signs**. Drag-and-drop a `.ttf`/`.otf`/`.woff`
font onto the page to see every glyph combination rendered in that font, with
Unicode tooltips and copy-to-clipboard for any cell, row, or column.

Based on research by **Pushpananda Ekanayake and Pathum Egodawatta**.

Open `index.html` in a browser — no server, no build step.

## Files

| File | Role |
|---|---|
| `sinhala-definitions.js` | Data layer — consonants, vowel marks, compound signs, conjunct/touching-cluster pairs (from the generated data in `../_generated/`), and shaping-exception sets. |
| `sinhala-sorting.js` | Sorting orders — default, alphabetical, frequency, phonetic, uMatra, custom. |
| `sinhala-chart.js` | Chart renderer and UI logic — grid, copy actions, font drag-and-drop, sidebar. |
| `index.html` | Shell — CSS, sidebar filters, sort dropdown. |
| `font-tester.html` / `font-tester.js` | A separate, simpler font-testing tool that shares `sinhala-definitions.js`. |
| `generate-glyphnames.js` | Node script — enumerates every possible composite glyph name a designer might need to draw. |

## Data dependency

The letter/conjunct/touching-cluster inventory and the rakaransaya/repaya/yansaya
shaping-exception sets are **generated data**, vendored from the
[lanka-glyphsets](https://github.com/mooniak/lanka-glyphsets) standard repo into
`../_generated/` (see that directory's README for the sync command).
`generate-glyphnames.js` also uses a vendored copy of the name⇄Unicode engine at
`../glyphname-unicode-converter/lankaglyphset-map.js`. This repo does not
redefine the standard — if the inventory, exceptions, or naming rules need to
change, the change lands in lanka-glyphsets first.

## Related

The typographic shape-group taxonomy for planned shape-based filtering (not
yet wired into the JS above) now lives in
[`../../sinhala-design-stages/sinhala-design-dependencies.yaml`](../../sinhala-design-stages/sinhala-design-dependencies.yaml)
(`skeletons`, `elements`, `spacing_classes`, `mark_systems`, `density`),
the cross-cutting design-stages model that also backs `tools/composite-map`.
Its machine view is `../../sinhala-design-stages/stages.json`.

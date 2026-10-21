# spacing-workbench

Browser tool for authoring the Sinhala spacing scheme
([`sinhala-spacing.yaml`](../../model/sinhala-spacing.yaml)) against a real font.
Static, no build step. It reads the scheme from the vendored
`../_generated/sinhala-spacing.js`.

```
sinhala-spacing.yaml ──export-js──► _generated/sinhala-spacing.js ──► workbench
        ▲                                                                │
        └──────────── exported scheme YAML / values / model changes ◄────┘
```

## Running

Serve the repo root and open the page (a plain `file://` open also works in
most browsers):

```sh
python3 -m http.server 8000      # from the repo root
open http://localhost:8000/tools/spacing-workbench/
```

Drop a `.ttf`/`.otf` anywhere on the page. Shaping uses HarfBuzz
(`harfbuzzjs@0.3.6` WASM) and YAML uses `js-yaml@4.1.0`, both loaded from
jsDelivr, so you need a network connection.

After changing `sinhala-spacing.yaml` (by hand or with `build-map`), refresh the
data:

```sh
cd tools/spacing-map && ./venv/bin/python -m spacing_map export-js
```

## What it does

**Class editor (left).** One tab per side. Each card is a spacing class:

- **rep** (outlined chip): the glyph whose sidebearing the class copies.
  Double-click a chip, or use **make rep** in the inspector, to change it.
- **members**: drag chips between cards (or to *Unassigned*) to move them.
  You can also pick a class from the inspector's dropdown. Tick **show fused
  forms** to see and move fused forms (ටි කු …) as well.
- **value**: the rep's target sidebearing as a multiple of `spacing_unit`.
  *Unset* means members just copy the rep's sidebearing. **font: 1.07× use**
  shows the multiple measured in the loaded font and adopts it in one click.
  **Fill unset values from font** does that for every unset class.
- **override**: a per-font target in font units. It replaces value × unit for
  this font only.
- Badges: orange chips **drift** from their rep by more than 8 u per 1000
  upem (same tolerance as `spacing_map audit`), **?** marks a provisional
  `FLAG` guess, faded chips aren't a single glyph in this font, and
  struck-through chips are exceptions (they keep their own sidebearing).

**Unit (top bar).** `spacing_unit` per side in font units. It defaults to ට's
measured sidebearings, because the model defines the unit by ට.

**Preview (right).** HarfBuzz-shaped text drawn twice. **F** is the font as it
is. **S** is the font with the scheme applied the way `apply` will wire it:
every member's sidebearing is replaced by its class target. Zero-advance marks
move with their base. With guides on, the selected class's sidebearings are
tinted, and glyphs the scheme doesn't cover get a dashed underline. Hover a
glyph for its numbers, and click it to inspect it. The **Control strings**
preset builds `ටට X ට X X ටට  rep X rep X rep` lines for the selected class.

### How entries are matched to glyphs

Each scheme entry is shaped on its own. If it comes out as **exactly one
glyph**, that glyph is the entry. Glyph names are never consulted, so this
works for any naming convention. It also measures fusion policy the same way
the CLI audit does. AbhayaLibre resolves 195/203 entries. Noto Sans Sinhala
resolves 130, because it places ි/ී as contextual marks instead of fusing
them.

## Exports (Export button)

| tab | file | what to do with it |
|---|---|---|
| Scheme YAML | `sinhala-spacing.yaml` | Replace the repo file, then run `export-js`. Values, notes and exceptions survive `build-map`. |
| Font values | `spacing-values-<font>.yaml` | Per-font `spacing_unit` + `overrides` (also lists the current targets and the measured multiples). Re-import it to restore a session. |
| Model changes | `spacing-model-changes.yaml` | Membership, rep and new-class edits written as model edits. Port them into `model/sinhala-design-dependencies.yaml`, because `build-map` rebuilds relationships from the model and would otherwise revert them. |

**Import YAML…** (or drop a `.yaml`) accepts any of three files:

- an exported scheme
- a font values file
- the output of `spacing_map audit --emit-values` (imported as scheme values)

Edits autosave in this browser's localStorage. That's only a convenience; the
exported files are the record. Saved edits are set aside when the vendored
scheme changes underneath them.

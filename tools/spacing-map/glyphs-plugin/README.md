# Sinhala Spacing — Glyphs 3 plugin

Wires the spacing scheme (`sinhala-spacing.yaml`) into the open font as
**metrics keys**: each class member's `leftMetricsKey` / `rightMetricsKey`
points at its class rep, so it inherits the rep's sidebearing.

## Install

```sh
ln -s "$PWD/tools/spacing-map/glyphs-plugin/SinhalaSpacing.glyphsPlugin" \
      ~/Library/Application\ Support/Glyphs\ 3/Plugins/
```

Restart Glyphs. The menu is **Glyph → Sinhala Spacing**.

## What it does

| menu item | |
|---|---|
| **Auto-Apply Keys to New Glyphs** | on by default (a global setting, not stored in the font). When a glyph is added — or renamed — into a scheme entry, it gets the keys the map gives it, and drawn layers are re-synced. |
| **Apply Keys to Whole Font…** | fills every missing key in the font, after a confirmation that lists counts. Use this once on a font that predates the plugin. |
| **Override Disagreeing Keys — Selected Glyphs… / Whole Font…** | replaces keys that disagree with the map (the one place the plugin overwrites), after a confirmation listing what will be lost. Per-master key overrides on those sides are cleared too, and sidebearings are re-synced from the reps. One undo step per glyph. |
| **Key Report** | Macro Window listing of keys that disagree, keys that are missing, and glyphs waiting for a rep; opens a tab with the disagreeing glyphs (first line) and the missing ones (second). |

Rules, in every mode:

- **Automatic runs fill keys, never overwrite.** A key that disagrees with the
  map — hand-set, carried over from a copy, or a formula like `=|ta-sinh` — is
  flagged (notification + Macro Window), and left alone until you choose
  Override Disagreeing Keys.
- **Only new glyphs are touched automatically.** Opening a font, or turning
  auto mode back on, takes a snapshot of what's there; nothing existing changes.
- **Reps and exceptions get no key**: the rep is the source of the sidebearing,
  and sides under the scheme's `exceptions:` are spaced by hand.
- **Composites fall back to their base.** A composite from
  `sinhala-composites.yaml` (`sU-sinh` = `sa-sinh` + `usign-sinh.medium`) that the
  scheme doesn't key on a side is keyed to its base glyph there, so it keeps
  the base's sidebearing measured *outside* any sign hanging past the base.
- **Auto-aligned glyphs are skipped** (listed in Key Report): a composite with a
  spacing sign (ආ = අ + ා) is spaced by its components, and Glyphs can't
  apply name keys to an auto-aligned layer.
- **Waiting glyphs**: a member added before its rep is remembered and keyed
  as soon as the rep is added (within the session).
- Sidebearings are re-synced only on master layers where both the glyph and
  its rep have outlines; a key on an empty glyph takes effect once it's drawn
  (use Glyphs' Update Metrics then — Sinhala Glyph Builder syncs the glyphs it
  builds).
- Each glyph's change is one undo step.

Glyph names resolve like `spacing-map audit`: letters by codepoint, fused forms
(ටි කු ක්) by the lanka-glyphsets naming convention. A font using other names
for fused forms can store a mapping in its font-level user data under
`com.mooniak.SinhalaSpacing.names`, e.g. `{"ඨි": "ThI-sinh"}`.

## Updating the bundled scheme

`Contents/Resources/sinhala_spacing/` is generated — the scheme as JSON plus
copies of `keyplan.py` and `names.py`, so the plugin needs no PyYAML and reads
no repo paths. After changing `sinhala-spacing.yaml` or those modules:

```sh
cd tools/spacing-map
./venv/bin/python -m spacing_map build-plugin          # then restart Glyphs
./venv/bin/python -m spacing_map build-plugin --check  # fail if stale
```

`Contents/MacOS/plugin` is the standard GlyphsSDK Python plugin loader.

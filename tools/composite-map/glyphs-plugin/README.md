# Sinhala Glyph Builder — Glyphs 3 plugin

Adds and builds Sinhala glyphs. **Add Glyphs…** is a visual picker over every
glyph a Sinhala font may contain; the composite commands build the composite
map (`sinhala-composites.yaml`) into a font.

## Install

```sh
ln -s "$PWD/tools/composite-map/glyphs-plugin/SinhalaGlyphBuilder.glyphsPlugin" \
      ~/Library/Application\ Support/Glyphs\ 3/Plugins/
```

Restart Glyphs. The menu is **Glyph → Sinhala Glyph Builder**. (This plugin
was called Sinhala Composites; remove an old `SinhalaComposites.glyphsPlugin`
link from the Plugins folder.)

## Add Glyphs…

A grid of tiles, one per glyph in the catalogue
(`tools/_generated/sinhala-glyph-catalogue.json`, 1 292 glyphs):

- every glyph of the design stages — letters, marks, the ි ු ් form
  families, the Stage 8 sweeps, the Stage 9 conjunct systems;
- every grapheme attested in the corpus (890), e.g. `s-sinh` ස්, `vAa-sinh`
  වා, `kO-sinh` කො, `kRI-sinh` ක්‍රි;
- the composite map's composites, keep-drawn and review glyphs;
- the sign variants (`usign-sinh.medium` …) and i-sign alternates.

A tile shows the font's own drawing when it has one, otherwise the grapheme
set in a reference Sinhala font (Noto Sans/Serif Sinhala, else the system's
Sinhala Sangam MN). Its colour is its state: **in font** (drawn), **empty**,
**features**, **to add** or **locked**.

| control | |
|---|---|
| filter menu | All glyphs · Stage 1–10 · Not scheduled · Consonants, ි ී forms, Rakaransaya … · Attested in the corpus (most frequent first) · the composite map's sections |
| search | glyph name or Sinhala text (`ස` shows every glyph containing ස) |
| Hide in font · Hide locked | narrow the grid to what can still be added |
| Show feature-only glyphs | off by default: glyphs recommended as **Features** (527) are hidden — base + ා ැ ෑ ෙ ේ ො ෝ ෛ ෞ ෘ ෲ ෟ or ්‍ය, which shaping assembles from their parts, so precomposing them is almost always optional. Ticked ones and ones already in the font stay visible; fused forms the map keeps drawn (රැ, the ද-shape below forms) are not feature-only. |
| click | tick / untick for adding; **option-click** only inspects; arrows move, space ticks |
| Make as | **Draw**, **Composite** or **Features** for the selected glyph |
| Prefer | switch every glyph to draw / composite / features where it allows it, or back to the recommendation |
| Tick all in view | ticks everything shown that is or becomes addable — a whole stage at once |
| Start drawings from parts | a drawn glyph starts as its parts' outlines, decomposed (කු starts as ක + ු) |

### Three ways to make a glyph

| mode | what is added |
|---|---|
| **Draw** | an outline glyph. A sign variant is seeded from its plain sign (orange). |
| **Composite** | the glyph as components, aligned by anchors (see below). |
| **Features** | no glyph: GSUB/GPOS shape the grapheme from its parts. The decision is recorded in the font (`font.userData["com.mooniak.SinhalaGlyphBuilder.features"]`), so the glyph shows as done; *Forget the features decision* undoes it. |

Every multi-part grapheme offers all three, so `s-sinh` (ස්) can be drawn,
composed as `sa-sinh + virama-sinh`, or left to mark positioning. The
recommendation comes from the data: the composite map's composites →
Composite; its keep-drawn forms (කු, ටි …) and review guesses → Draw; a sign
that sits beside the base (ා ෙ ො ්‍ය …) → Features; any other decomposable
form → Composite; a letter or sign → Draw.

### Parents first

A glyph is **locked** until what it depends on is in the font, recorded as
features, or ticked with it:

- its **design parents** from the stage model — ච needs ට and ඩ; a form-family
  member needs the family's parents (කු needs ක ග ත ු);
- its **parts** — `s-sinh` needs `sa-sinh` and `virama-sinh`; `kRI-sinh` needs
  `kRa-sinh` and `isign-sinh`.

For Composite the components must be glyphs; a missing sign variant is fine
when its plain sign is there, because the build seeds it. Untick a parent and
its ticked dependants are unticked. The detail panel lists what the glyph
needs; double-click an entry to go to it. Glyphs are added in dependency
order, so ticking ස, ් and ස් together works.

## Composite commands

| menu item | |
|---|---|
| **Auto-Build New Composites** | on by default (a global setting). A glyph added under a mapped name — e.g. via Glyph → Add Glyphs — is built while it is still empty. Glyphs added by the picker are made as chosen there instead. |
| **Build Composites by Name…** | type names (`ttU-sinh sU-sinh`); missing ones are created and built. Drawn glyphs are left alone. |
| **Build Selected Composites…** | rebuilds the selection; replacing drawn outlines asks first. |
| **Build All Composites…** | creates every missing composite, fills empty ones and updates composites whose components differ from the map. Drawn glyphs are never touched. |
| **Composite Report** | what Build All Composites would do, in the Macro Window, plus a tab. |

| glyph | built as |
|---|---|
| `ttU-sinh` | `tta-sinh` + `usign-sinh.tta` |
| `sU-sinh` | `sa-sinh` + `usign-sinh.medium` |
| `hU-sinh` | `ha-sinh` + `usign-sinh.long` |
| `sRa-sinh` | `sa-sinh` + `rasign-sinh.short` |
| `kRa-sinh` | `ka-sinh` + `rasign-sinh.long` |

Rules, in every mode:

- **One rule, canonical names.** No per-font name tables and no fallback to
  the plain sign.
- **Missing sign variants are seeded.** If the font lacks `usign-sinh.medium`
  (or any variant the map references), it is created as a copy of the plain
  sign (outlines, anchors, width), coloured **orange** and noted for redesign.
  The composite is right from the start and updates when the variant is drawn.
- **Exceptions come only from the map**: `keep_drawn` (fused forms like කු,
  ක්, ටි) and `review` glyphs are never built by these commands (the picker
  builds them only when you choose Composite).
- Signs use automatic alignment, so placement comes from the font's own
  `uvowel` / `rakar` / `repaya` / `iVowel` / `alSign` anchors.
- **Spacing follows the sign.** With an attached sign (ු ්‍ර ි repha ්) the
  base sits at the origin with automatic alignment **off**, and the glyph is
  spaced by metrics keys — the spacing scheme's, or its base glyph's (Sinhala
  Spacing writes them; this plugin syncs them after a build). Left aligned,
  Glyphs would copy the base's width and a sign hanging past the base's right
  edge would eat the sidebearing. With a spacing sign (ා ැ ෑ ෟ …), or a
  pre-base sign leading the components (කො = `esign-sinh` + `ka-sinh` +
  `aasign-sinh`), the whole glyph stays auto-aligned so every part advances,
  and any keys are cleared — Glyphs can't apply name keys to an auto-aligned
  layer. This needs the signs' "Spacing Combining" subcategory from
  lanka-glyphsets' `GlyphData.xml`. A composite whose alignment doesn't match
  is rebuilt as an update.
- Each glyph's build is one undo step.

## Updating the bundled data

`Contents/Resources/sinhala_glyph_builder/` is generated: the map and the
glyph catalogue as JSON plus copies of `buildplan.py` and `catalogue.py`.
After rebuilding the map, the design model or the corpus data, or editing
those modules:

```sh
cd tools/composite-map
./venv/bin/python -m composite_map build-plugin          # then restart Glyphs
./venv/bin/python -m composite_map build-plugin --check  # fail if stale
```

`build-plugin` first runs `node glyph-catalogue/build.js` (when Node is on the
PATH) to regenerate the catalogue.

| file | |
|---|---|
| `Contents/Resources/plugin.py` | the menu and the composite commands |
| `Contents/Resources/add_glyphs.py` | the Add Glyphs window |
| `Contents/Resources/glyphbuild.py` | font edits shared by both |
| `Contents/MacOS/plugin` | the standard GlyphsSDK Python plugin loader |

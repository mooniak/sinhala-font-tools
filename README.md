# Sinhala Font Design

Design research, design processes and design-side tooling for Sinhala type, by
[mooniak](https://github.com/mooniak).

This repo answers **how to design a Sinhala typeface** — anatomy, what order to
draw glyphs in, how spacing inherits, which forms are composites, what to test
with, and the browser tools to look at all of it. It deliberately stops where
engineering begins.

> **Renaming.** This repository is being renamed from `sinhala-font-tools` to
> **`sinhala-font-design`** to match that scope. Existing clone URLs will keep
> redirecting, but update your remotes when you next pull.

## Where the boundary is

Design lives here. Font engineering — glyph inventories, glyph naming,
encoding, OpenType features, building, QA and release — lives in three other
places, and this repo defers to them rather than duplicating them:

| Standard / project | What it governs | Use it for |
|---|---|---|
| **[lanka-glyphsets](https://github.com/mooniak/lanka-glyphsets)** | The glyphset standard for Sri Lankan fonts: cumulative Sinhala levels (Kernel / Core / Plus / Pro) mapped to ICTA Levels 1–3, plus a Tamil glyphset, and the normative **glyph-naming standard** (visual-form names such as `kRa-sinh`). Ships `@mooniak/lankaglyphsets` (npm). | What a font must contain and what each glyph is called. |
| **SLS 1134** | The Sri Lanka Standard for Sinhala character encoding, published by the Sri Lanka Standards Institution — the national standard behind Sinhala in Unicode: character repertoire, code points and how Sinhala text is encoded. | Encoding, `cmap`, codepoint questions, conformance claims. |
| **[mooniak-font-tools](https://github.com/mooniak/mooniak-font-tools)** (`mnik`) | The production toolchain across all mooniak font repos: building with gftools, QA/fontspector, proof PDFs, build manifests, release channels, native Glyphs export, and the font directory/dashboard. | Building, QA-ing, proofing, releasing and tracking a font project. |

**Glyph names used throughout this repo are lanka-glyphsets names.** If a model
here disagrees with lanka-glyphsets, lanka-glyphsets wins.

## What's here

### Models (the design data)

All three live in [model/](model/); see [model/README.md](model/README.md).

- **[model/sinhala-design-dependencies.yaml](model/sinhala-design-dependencies.yaml)** — a dependency-based
  development model. Every design *decision* (a metric, a skeleton, a spacing
  class, a mark-join convention) is introduced once by one glyph and inherited
  by every glyph that depends on it; stages are scheduled by hand and
  validated against that graph, and drills and coverage are computed from it. Orthogonal to lanka-glyphsets levels: levels say *what* a
  font must contain, stages say *in what order to draw it*. Rendered as a
  visual explainer by [tools/design-stages/](tools/design-stages/).
- **[model/sinhala-spacing.yaml](model/sinhala-spacing.yaml)** — the spacing scheme:
  sidebearing relationships derived from the stages model, applied to sources
  as Glyphs metrics keys.
- **[model/sinhala-composites.yaml](model/sinhala-composites.yaml)** — which glyphs should
  be assembled from components rather than drawn as merged outlines.

### Tools

- **[tools/glyph-chart/](tools/glyph-chart/)** — browser font tester: a grid of
  base letters × vowel marks/compound signs. Drop in a `.ttf`/`.otf`/`.woff`.
- **[tools/spacing-map/](tools/spacing-map/)** — builds `model/sinhala-spacing.yaml`
  from the stages model and audits a font's sidebearings against it (writing
  metrics keys into `.glyphspackage` sources is on its roadmap).
- **[tools/composite-map/](tools/composite-map/)** — builds the composite map
  and rebuilds atomic glyphs into proper composites in Glyphs sources; its
  **Sinhala Glyph Builder** Glyphs plugin adds glyphs from a visual catalogue
  of every stage glyph and attested grapheme (draw, composite or features),
  parents first.
- **[tools/glyphs-filters/](tools/glyphs-filters/)** — generates Glyphs 3
  sidebar filters from these models, so a working font's sidebar is a live view
  of the model. Output in [filters/](filters/).
- **[tools/test-generator/](tools/test-generator/)** — adhesiontext-style test
  text generator: list the graphemes a font has (ටු, කෝ, ක්‍රි… as units, drawn
  or composed) and get real words and running text that use only those.
- **[test-texts/corpus-build/](test-texts/corpus-build/)** — builds, from the raw UCSC
  Sinhala corpora (not in the repo), the data bundle `test-generator` loads:
  cleaned words and frequencies, word pairs, a word-building model and ~150k real
  sentences sharded by rarest grapheme.
- **[tools/font-comparison/](tools/font-comparison/)** — side-by-side rendering
  comparison across fonts. Ships with just the system fonts; see its README
  to set up your own default collection.
- **[tools/feature-generator/](tools/feature-generator/)** — `lankafea`
  (PyPI `mnik-lankafea`): generates Sinhala/Tamil OpenType features from the
  lanka-glyphsets standard, gated on the glyphs a font actually has, and
  reports dependency blockers and orphans. Its Glyphs 3 plugin, **Lanka
  Features**, is in [glyphs-plugin/](tools/feature-generator/glyphs-plugin/).
  Moved here from lanka-glyphsets so that repo holds only the standard; it
  reads the glyphset YAMLs from a sibling `lanka-glyphsets` checkout.
- **[tools/glyphname-unicode-converter/](tools/glyphname-unicode-converter/)** —
  glyph name ↔ Unicode converter: paste Sinhala clusters to get LankaGlyphset
  names, or names to get the Unicode. Vendored from lanka-glyphsets, web tool
  and engine; the engine (`lankaglyphset-map.js`) is also used by glyph-chart,
  glyphs-filters and test-generator.

### Reference material

- **[test-texts/](test-texts/)** — the canonical Sinhala test-text corpus:
  display paragraphs, kern pairs, conjuncts, marks, numerals, punctuation,
  classical/Pali/Sanskrit text, pangrams, multiscript samples. Vendored into
  `mnik`'s proof PDFs and into
  [polytypetester](https://github.com/mooniak/polytypetester) — see
  [test-texts/README.md](test-texts/README.md) for the sync mapping.
- **[resources/](resources/)** — Sinhala anatomy notes, character-frequency
  analysis, reference fonts.

## Getting started

Most of the browser tools are static — open the `index.html` and drop a font in,
no build step. The Python tools (`spacing-map`, `composite-map`) each have their
own README with setup instructions. `tools/glyphs-filters` reuses `js-yaml` from
`tools/design-stages/node_modules`.

All the browser tools share one black-and-white palette,
[`tools/_shared/bw.css`](tools/_shared/bw.css). Use its tokens rather than
colours: show differences with fill, weight and solid/dashed borders, not hue.

If you are **starting a Sinhala font**, the order is roughly:

1. Pick a target level in [lanka-glyphsets](https://github.com/mooniak/lanka-glyphsets) — that's your inventory and your glyph names.
2. Design in the order given by [tools/design-stages/](tools/design-stages/), using the Glyphs filters in [filters/](filters/) to see what should exist by now.
3. Apply spacing and composites with the tools above.
4. Generate features and validate with lanka-glyphsets (`mnik-lankafea`).
5. Build, QA, proof and release with [`mnik`](https://github.com/mooniak/mooniak-font-tools).

## Licence

The models and tools authored in this repo are [GPL-3.0](LICENSE.md).

Some vendored and reference content carries its own licence instead:

| Content | Licence |
|---|---|
| [`test-texts/`](test-texts/) (most files) | CC-BY-SA-4.0, per each file's `license:` frontmatter |
| [`test-texts/libreoffice-ui-strings.md`](test-texts/libreoffice-ui-strings.md) | Extracted from LibreOffice's Sinhala `.po` files; frontmatter says CC-BY-SA-4.0, but upstream LibreOffice is MPL-2.0 — confirm before reuse |
| [`resources/Hodipotha-9.ttf`](resources/Hodipotha-9.ttf) | © ICTA 2014, CC BY-ND 4.0 — see [`resources/README.md`](resources/README.md) |
| [`resources/sinhala-frequency-analysis/sinhala/Corpus/`](resources/sinhala-frequency-analysis/) | Sinhala newspaper text (e.g. Silumina, ANCL, 2004); no licence recorded — check redistribution terms before reuse |
| [`tools/_generated/lanka-glyph-data.js`](tools/_generated/), [`shaping-exceptions.js`](tools/_generated/), [`tools/glyphname-unicode-converter/`](tools/glyphname-unicode-converter/) (`index.html`, `converter.js`, `lankaglyphset-map.js`) | Vendored from [lanka-glyphsets](https://github.com/mooniak/lanka-glyphsets); see that repo's licence |

When in doubt about a specific file, check its own header/frontmatter first — it overrides this table.

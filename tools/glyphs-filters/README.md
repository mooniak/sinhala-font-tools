# glyphs-filters

Generates **Glyphs 3 sidebar filters** from this repo's models. Every filter is
a derived set — a design stage, a spacing class, a mark form family, a
composite tier, a metric's reopen closure — so the sidebar of a working font
becomes a live view of the model instead of a hand-curated list that drifts.

```
sinhala-design-dependencies.yaml ┐
sinhala-spacing.yaml             ├─►  build.js  ─►  filters/CustomFilter*.plist
sinhala-composites.yaml          │                  filters/manifest.json
tools/_generated/*.js            ┘                  filters/README.md
```

## Usage

No install: it reuses `js-yaml` from `sinhala-design-stages/node_modules`.

```sh
node tools/glyphs-filters/build.js               # filters/CustomFilter MNIK Sinhala.plist
node tools/glyphs-filters/build.js --check       # validate + report, write nothing
node tools/glyphs-filters/build.js --list        # print the catalogue with counts
node tools/glyphs-filters/build.js --split       # one file per section instead
node tools/glyphs-filters/build.js --flat        # no subfolders, one folder per section
node tools/glyphs-filters/build.js --title "…"   # sidebar heading (default: MNIK Sinhala)
node tools/glyphs-filters/build.js --only Spacing,Stages
node tools/glyphs-filters/build.js --out ~/path/next/to/MyFont.glyphspackage
```

Then either:

- **project-scoped** — copy the plist next to the `.glyphs`/`.glyphspackage`
  file, or
- **global** — copy it into `~/Library/Application Support/Glyphs 3/`

and restart Glyphs. The filename **must** start with `CustomFilter`; whatever
follows it is the sidebar heading (`CustomFilter MNIK Sinhala.plist` → a
"MNIK Sinhala" heading), so rename freely.

## How Glyphs stores this

Verified against `~/Library/Application Support/Glyphs 3/CustomFilter.plist`
and `GSSidebarItem.h`. A filter file is a plist array of dicts, each with
`name` plus **either**:

- `list` — an array of bare glyph names (what this tool emits),
- `predicate` — a **plain** NSPredicate format string (`export == 1`), not an
  archived object, or
- `subGroup` — an array of further dicts, which Glyphs shows as a **folder**.
  Verified against Typotheque's project files (`CustomFilter TPTQ
  Devanagari.plist`), which nest exactly this way; `GSSidebarItem.subItems` is
  the object behind it.

Filters are never stored inside the `.glyphs` file, and the Python API has no
filter class (`Glyphs.filters` is the Filter *menu*), which is why generating
plists is the right path: no Obj-C, no running app, diffable in git.

**The trap this tool exists to avoid:** the sidebar's list field splits pasted
text on *whitespace only*. Paste a comma-separated list or one with a `#`
comment header and you get entries like `si_Ba.reph,` or a lone `#` that match
nothing, silently. `plist.js` refuses to emit any name containing whitespace or
punctuation, and `build.js` runs `plutil -lint` on everything it writes.

## Sections

One file, `CustomFilter MNIK Sinhala.plist`, holding eight folders:

| Folder | What it slices by | Subfolders |
|---|---|---|
| Stages | design schedule | by stage · cumulative |
| Structure | skeletons and structural elements | skeletons · elements |
| Spacing | sidebearing classes | left · right · work sets |
| Mark forms | the 20 form families and the Stage 8 sweeps | ි · ු · ් · roll-ups |
| Composites | build vs keep-drawn decisions | tier · source · keep-drawn reason |
| Conjuncts | rakaransaya/repaya/yansaya — applies *and* excluded | — |
| Dependencies | what reopens when a decision changes | metric closures · archetype descendants |
| Inventory | level, frequency, density, type, coverage, gaps | six |

`--split` writes them as eight separate `CustomFilter<Section>.plist` files
instead (eight sidebar headings, no top-level folder); `--flat` drops the
subfolders if the nesting depth ever proves awkward.

`filters/README.md` is regenerated with every filter, its member count and the
exact field it came from; `filters/manifest.json` carries the same data plus
the glyph lists, for other tools to consume.

## Naming

Glyph names are LankaGlyphSets (`name-sinh`), resolved through the vendored
`tools/glyphname-unicode-converter/lankaglyphset-map.js` — the same standard
`composite-map` and `spacing-map` assume. A vendor using different glyph names
would need a different `name()` in `sources.js`; nothing else in the tool knows
about naming.

## Empty filters are a signal

A filter with no members means the model has a hole, so the build **reports it
and refuses to write it** rather than shipping an empty sidebar entry. None
currently — the last one (`conjunct-i-forms`, an empty stub for the ග්‍රි
group) was resolved 2026-07-20 by folding its members into fam-i-di,
fam-i-ndi, fam-i-nyi and fam-i-tthi's `conjunct_hosts` (see gap
`conjunct-i-forms-resolution` in sinhala-design-dependencies.yaml).

## Files

| File | Role |
|---|---|
| `build.js` | CLI: report, render, `plutil -lint`, write |
| `catalogue.js` | **The catalogue.** Every filter, its members and its provenance |
| `sources.js` | Loads the YAMLs + generated JS; character sequence → LGS name |
| `plist.js` | Minimal `CustomFilter*.plist` writer + glyph-name sanity check |

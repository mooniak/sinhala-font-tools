# LankaGlyphset ⇄ Unicode Converter (vendored)

A **vendored copy** of
[lanka-glyphsets/tools/glyphname-unicode-converter](https://github.com/mooniak/lanka-glyphsets/tree/main/tools/glyphname-unicode-converter):
a bidirectional converter between LankaGlyphset glyph names (`kRa-sinh`,
`kSsa-sinh`, `daa._c-sinh` …) and the Sinhala Unicode string each renders.
lanka-glyphsets owns the naming standard; this copy exists so the browser tool
and the tools here that use the engine work without a sibling checkout.

**Do not edit these files here.** Change them upstream and re-sync.

## The web tool

Open **`index.html`** in a browser (no server, no build).

- **Unicode → Name**: paste Sinhala text, one cluster per line, get the
  LankaGlyphset name, codepoints and glyphset tier.
- **Name → Unicode**: paste names (`-sinh` optional), get the Unicode string.
- Names in the authoritative glyphset show their tier
  (`kernel`/`core`/`plus`/`pro`); well-formed names not enumerated there are
  marked `derived`. Click any row to copy.

## The engine: `lankaglyphset-map.js`

Shared by the browser and Node, with an embedded `GLYPHSET` table so it needs
no server or YAML loading at runtime.

```js
const L = require("./lankaglyphset-map.js");
L.unicodeToName("ක්‍ර");      // { name: "kRa-sinh", tier: "derived", canonical: false }
L.nameToUnicode("kSsa-sinh"); // { unicode: "ක්‍ෂ", hex: "U+0D9A U+0DCA U+200D U+0DC2", ... }
```

Used in this repo by:

- [`tools/glyph-chart/generate-glyphnames.js`](../glyph-chart/generate-glyphnames.js)
- [`tools/glyphs-filters/`](../glyphs-filters/)
- [`tools/test-generator/`](../test-generator/)

The local `package.json` scopes this folder to CommonJS so `require()` works.

## What's vendored

| File | Upstream |
|---|---|
| `index.html`, `converter.js` | the web tool |
| `lankaglyphset-map.js` | the engine |

Not vendored: `build-glyphset.js`, which regenerates the embedded `GLYPHSET`
from the glyphset YAMLs and only runs inside lanka-glyphsets.

## Syncing

After the standard changes, from a lanka-glyphsets checkout, regenerate the
engine there (`node tools/glyphname-unicode-converter/build-glyphset.js`), then:

```bash
U=../lanka-glyphsets/tools/glyphname-unicode-converter
for f in index.html converter.js lankaglyphset-map.js; do
  cp "$U/$f" tools/glyphname-unicode-converter/ && diff -q "$U/$f" tools/glyphname-unicode-converter/$f
done
```

For naming rules and edge cases, see the upstream README and lanka-glyphsets'
`docs/naming-standard.md`.

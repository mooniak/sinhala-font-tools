# Generated data

Two provenances live here:

- **Vendored** from another repo: `lanka-glyph-data.js`, `shaping-exceptions.js`
  (see below).
- **Generated locally** by a tool in this repo: `sinhala-composites.js`, emitted
  by [`tools/composite-map`](../composite-map/) from `sinhala-composites.yaml`.
  Regenerate with `python -m composite_map export-js`; do not edit by hand.

## Vendored copies

`lanka-glyph-data.js` and `shaping-exceptions.js` are **vendored copies**, not
authored here. They are generated in the
[lanka-glyphsets](https://github.com/mooniak/lanka-glyphsets) standard repo and
copied byte-for-byte into this directory so `tools/glyph-chart/` can run
standalone (same pattern as `tools/feature-generator/src/lankafea/data/glyphsets/`
in that repo, which vendors the glyphset YAMLs for the same reason).

Do not edit these files by hand. To sync after the standard changes, from a
checkout of lanka-glyphsets:

```bash
npm run build && node dist/cli/index.js export-json --format js -o tools/_generated/lanka-glyph-data.js
node tools/_generated/build-shaping-exceptions.js
```

then copy both files into this directory and verify with `diff -q`.

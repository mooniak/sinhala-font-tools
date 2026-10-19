# Lanka Features — Glyphs 3 plugin

Runs the [`lankafea`](../feature-generator) generator inside Glyphs: Sinhala /
Tamil OpenType features, gated on the glyphs actually in the font. The plugin
bundles `lankafea` (and PyYAML), so there is nothing to `pip install`.

## Install

```sh
./build.sh --install    # then restart Glyphs
```

## Use — Glyph menu ▸ Lanka Features

| Item | What it does |
|---|---|
| Generate Features Now | Builds and writes features into the front font |
| Auto-Generate When Glyphs Change | Per-font toggle; regenerates when glyphs are added, removed, renamed or re-encoded (checked about once a second, plus on open/save/switch) |
| Dependency Report | Prints the blockers / orphans report in the Macro window |
| Add ZWJ / ZWNJ Control Glyphs | Inserts the zero-width controls the rules depend on |
| Script / Sinhala Level | Override auto-detection and pick the glyphset tier (0–3) |

Settings live in the font (`userData`), so they travel with the file.

Hand-written features are never overwritten: only code carrying the
`# lankafea:generated` marker is replaced. If you hand-wrote a tag the
generator also emits, yours is kept and the notification says so.

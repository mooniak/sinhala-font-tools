# Custom rule injection

Files here are merged into the generated features **before** presence-gating, so
injected rules are pruned to the font's glyphs exactly like generated ones.

- `*.yaml` — declarative rules (see `sinhala-shape-groups.example.yaml`).
- `*.fea` — raw feature code, appended verbatim (not gated).

Bare glyph names (`va`, `usign`) are namespaced automatically (`va-sinh`). Tokens
already suffixed, `@class` references, and control glyphs (`zerowidthjoiner`) are
left untouched. A trailing `'` marks a contextual input glyph.

Pass a directory with `--inject inject/` or individual files with
`--inject-file path.yaml` (repeatable).

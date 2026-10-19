# lankafea — Roadmap

Status of the LankaGlyphset feature toolkit (`lankafea validate|generate`)
and the path forward, grounded in real-font evaluation.

PyPI `mnik-lankafea` v0.2.0 · import `lankafea` · 37/37 tests green · CLI
`lankafea`. The [lanka-glyphsets](https://github.com/mooniak/lanka-glyphsets)
repo remains the home of the naming standard; this is the font-side toolkit.

## Guiding principle

Every glyph is a **dependency**. A rule needs its input glyphs and its output
glyph present; the tool generates a broad candidate set and *validates* it
against the font, so the same generators serve any font and the validator can
explain exactly what is missing and why. Fonts range between two valid poles —
**Abhaya Libre** (descriptive: a precomposed glyph per outcome) and **Noto Sans
Sinhala** (optimised: shape-group classes + anchor GPOS) — and adaptation is
driven by glyph *presence*, never a mode switch.

## Shipped (v0.1 → v0.2)

- **Dependency validator** (`validate`): satisfiable/blocked per feature, blockers
  ranked by impact with fix-it hints, orphan detection with name-parsed
  narratives, JSON + human reports, `--fail-on-blockers` for CI.
- **Generators**: akhn (conjuncts incl. full C×C cartesian + halant forms in
  abvs), rphf, vatu (+ rakar ligatures), abvs/blws/psts vowel ligatures, repha
  ligatures (post-reorder, in psts), yansaya-sign chains, touch clusters,
  da-shape `._c`, dist, aalt/ssNN from `.altN` glyphs.
- **ZWJ handling**: `--fix-zwj` inserts bundled authored ZWJ/ZWNJ control glyphs;
  nonstandard ZWJ names auto-aliased before gating.
- **Glyphs sources**: native `.glyphspackage` read/write; `--glyphs-out`
  **preserves hand-written features/prefixes/classes** (ownership-marker model)
  with keep/replace collision policy (`--replace-tags`/`--keep-tags`).
- **Noto-pole adaptation**: harvests source shape-group classes, emits class-gated
  variant selection, reports anchor-coverage gaps.

### Acceptance

| Font | Result |
|---|---|
| aggnni (fontmaster) | 351→464 rules, **0 orphans**, ZWJ blocker surfaced + auto-fixed |
| fontmaster sweep (35) | all validate ~426 rules; universal top blocker = missing ZWJ |
| Abhaya Libre (descriptive pole) | 6/6 shaping parity vs hand-written; 90.6% output-glyph coverage; Tamil ss auto-built from dead `.alt` inventory |

## In progress / next

### R1 — Multi-script sources (HIGH — blocks Abhaya writeback) · ~1 day
Abhaya carries Sinhala **and** Tamil in one source with **duplicate feature tags**
(`akhn` ×2, scoped `script sinh;` / `script taml;`). Today:
- the `# lankafea:generated` marker is not script-aware → sequential
  `--glyphs-out --script sinhala` then `--script tamil` would clobber each other;
- collision logic assumes unique tags → `--replace-tags akhn` would delete both.

Fix: script-tagged ownership marker; emit script-scoped generated bodies
(`script sinh; …`); duplicate-tag-aware collision resolution keyed on (tag,
script). **Until shipped: do not run `--glyphs-out` on multi-script sources.**

### R2 — Numbered & misplaced variants (MED) · ~0.5 day
`.001–.009` numbered variants (Abhaya reph) are invisible to both `.altN`
detection and orphan detection — any suffix after `-sinh` escapes the namespace
`endswith` check. Misplaced Tamil suffix `aisign-taml.alt` matches no pattern.
Fix: variant parser handles `.NNN` and suffix-before/after-namespace; orphan
namespace matching tolerates trailing `.suffix`.

### R3 — Remaining generators (LOW) · ~0.5 day
From Abhaya's real orphans: da-shape yansaya `._c` forms (`dya._c`), third-order
yasign chains (`yasign_repha_usign`), `.rasign` sign-variant selection
(`usign.rasign`). Small, presence-gated additions.

### R4 — Full multi-script writeback dry-run (after R1–R3)
`--glyphs-out` onto a copy of Abhaya; verify in Glyphs that all 27 hand-written
features + both prefixes survive intact alongside generated Sinhala + Tamil code.

## Later / candidate

- **GPOS mark generation** — currently out of scope (Glyphs auto-builds
  mark/mkmk from anchors); revisit only if a target needs `.fea`-level marks.
- **rlig / contextual reph-variant selection** — Abhaya's `.001–.010` positional
  reph logic is contextual and font-specific; stays hand-written and preserved.
  Consider a template/inject helper rather than generation.
- **Batch driver** — one command to validate/fix-zwj/generate across a whole
  collection (the 35 fontmaster repos) with a summary table.
- **Coverage delta reporting** — before/after glyph-reachability diff as a first-
  class `validate` output.
- **pres feature** — pre-base `e/ee/ai` handling once split-vowel test fonts exist.

## Non-goals

- Not the home of the naming standard (that is lanka-glyphsets).
- Not a general FEA authoring tool — it generates the productive, presence-gated
  rules and preserves everything hand-authored; it does not replace a type
  designer's contextual/aesthetic lookups.

## References

- Sinhala shaping: n8willis `opentype-shaping-sinhala.md` (script tag `sinh`;
  basic `akhn rphf pstf vatu`, presentation `pres abvs blws psts`, GPOS `dist`).
- Reference fonts: Abhaya Libre (descriptive), Noto Sans Sinhala (optimised).
- Evaluation data behind R1–R3: see the Abhaya eval run (validator JSON, coverage
  and rule-comparison scripts, shaping parity results).

# lankafea — Roadmap

Status of the LankaGlyphset feature toolkit (`lankafea validate|generate`)
and the path forward, grounded in real-font evaluation.

PyPI `mnik-lankafea` v0.2.0 · import `lankafea` · 127 tests green · CLI
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

## Shipped with the Tamil work

- **Tamil model** (`tamil.py`): forms met by a ligature OR a shape-group alternate,
  `ss09` traditional forms, requirement levels 0–2, a resolver so the route a font did
  not take is never reported. Acceptance against Ralex, Yaldevi and Abhaya Libre: see
  the README (Abhaya identical; the others differ only by glyphs now reachable).
- **R1 — multi-script sources.** Script-tagged ownership, per-script class manifest and
  `Languagesystems`, collisions keyed on (tag, script), `script taml;`-scoped bodies.
  `--glyphs-out` is now safe on Abhaya-style sources (generate one script, then the other).
  The Glyphs plugin shares the rules.
- **R2 — variants.** Both positions of a dot-suffix and numbered `.NNN` variants are
  recognised; `--aliases` / `--adopt-legacy-names` for fonts not yet migrated.

## In progress / next

### Tamil: what is left
- **Glyph-info check for Tamil.** The Mark/Spacing check covers Sinhala only; the Tamil
  equivalent is ீ ஂ ் nonspacing (Mn) and the other signs spacing (Mc), and ஃ a letter.
- **Group-number aliases are per font.** `--adopt-legacy-names` finds the deterministic
  renames; which numbered `isign.altN` is which shape group still needs a table per font
  (Ralex, Yaldevi done; Abhaya's alt3–alt7 are unverified and unused by its features).
- **Vineetha** (a copy of Ralex's Tamil) and **Lankaverse Sans** (old-style names) have
  not been run through the acceptance check.
- **Plugin in Glyphs.** The plugin's writeback is tested against a stand-in Glyphs API, not
  inside Glyphs. It generates one script at a time (the Script menu); a "both scripts"
  action would call it twice.

### R3 — Remaining generators (LOW) · ~0.5 day
From Abhaya's real orphans: da-shape yansaya `._c` forms (`dya._c`), third-order
yasign chains (`yasign_repha_usign`), `.rasign` sign-variant selection
(`usign.rasign`). Small, presence-gated additions.

### R4 — Full multi-script writeback dry-run (R1 done; after R3)
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

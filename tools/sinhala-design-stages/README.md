# Sinhala Design Stages — a dependency-based development model

A mechanical, dependency-driven development order for Sinhala fonts.

The core idea: **stage decisions, not glyphs.** Every design decision — a
metric, a skeleton, a structural element, a spacing class, a mark-join
convention — is introduced exactly once by one glyph and inherited by every
later glyph that uses it. A glyph may enter the schedule only when everything
it depends on already exists. Stages, drills and coverage numbers are then
*computed* from the graph, so the documentation can never disagree with the
data.

This is **orthogonal to the lanka-glyphsets levels** (`glyphsets/*.yaml`):
levels define *what a font must contain*; these stages define *in what order
to design it*. Every entry carries a `level` tag so a shipping target is a
computed slice: design in stage order, stop when the level inventory is
covered.

## Files

| File | Role |
|---|---|
| `sinhala-design-dependencies.yaml` | **Source of truth.** The whole model: metrics, skeletons, elements, spacing classes, mark systems, stages, every glyph with its parents and schedule, AI guidance, open gaps. |
| `build.js` | Validator + generator. Checks the graph, validates/generates test texts, writes `index.html` and `stages.json`. |
| `index.html` | **Generated** visual explainer (Abhaya Libre). Never hand-edit. |
| `stages.json` | **Generated** machine view for other tools (chart tool, test-string generators, AI agents). |
| `extract-noto.js` | Mines `docs/NotoSansSinhala.glyphspackage` for its OT classes and substitution behaviour; writes `docs/sinhala.min.yaml` and prints a diff against the model. |
| `docs/` | Working sources: the WIP shape-groups/stages/anatomy files, the Noto Sans Sinhala Glyphs package (production reference), and the **generated** `sinhala.min.yaml`. |

## Completing the taxonomy against a production font

The WIP taxonomy files in `docs/` are intentionally incomplete. Instead of
completing them by intuition, mine a highly optimised production font and
diff its behaviour against the model:

```sh
node extract-noto.js   # regenerates docs/sinhala.min.yaml + prints the diff
```

Noto processes every mark through a **three-tier system** — default mark
form, contextual alternate (per class), or a fully fused ligature glyph —
and its classes map almost one-to-one onto this model's form families
(`iVowelAlt3` = කි family, `iVowelAlt6` = ලි family, …). Findings already
folded back into the model this way:

- The ් (virama) system has **four forms**: the default *kodiya* flag, the
  *rahena* wrap fused over top-terminal bases (ට ඩ ඬ ච ධ ඛ බ ම ඹ ව ඣ ඞ),
  a trap-top alternate (ඨ ඪ ථ ඵ) and a ja-shape alternate (ඡ ජ ඦ).
- The formerly "unassigned" ි hosts (ම ය ව බ ඛ ධ ණ …) are fused
  top-terminal wrap hosts — now `fam-i-term`.
- Noto reuses the ැ glyph for රු, and fuses ලු ඳු ඤු ඥු beyond our current
  ු families — recorded in `gaps` pending a design decision.

The workflow generalises: drop another well-made font's Glyphs package into
`docs/`, point the extractor at it, and every disagreement becomes a listed
decision instead of an unnoticed hole.

## Workflow

```sh
npm install        # once
npm run build      # validate + regenerate index.html and stages.json
node build.js --check   # validate only
```

If your process changes — a glyph moves stages, a new element, different
spacing classes — edit the YAML and rebuild. The build **fails** on any
violation of the model, so the page is always a valid state of the process.

## What the validator enforces

1. Every `parent` exists and is scheduled strictly before its child
   (`stage`, then `order` within a stage).
2. A glyph's `skeleton` and `elements` are introduced (by their
   `introduced_by` glyph) at or before the glyph itself.
3. A spacing-class **representative** (`rep`) is designed before every other
   member of the class — reps set sidebearings, members inherit.
4. Unique `(stage, order)` slots; all stages declared in the `stages` block.
5. **Test texts only use what exists.** For every authored drill, word and
   sentence at stage *n*: every character is scheduled ≤ *n*, and mark joins
   respect the form-family schedule —
   - `ි ී` on a host requires that host's ි family (e.g. සි needs
     `fam-i-ghi`, කි needs `fam-i-ki`); hosts in no family produce a
     *warning* (a real taxonomy gap, kept visible on purpose);
   - `ු ූ` distinguishes the regular join from `u-special` (කු ගු තු …),
     `du-form` (දු) and `ra-forms` (රු);
   - `්` distinguishes the flag from the `hal-cap` form (ම් ඹ්);
   - vowel signs on independent vowels are errors;
   - ZWJ sequences require the Stage 9 conjunct systems.
6. Generated drills are built from the same rules: each stage's drill block
   lists exactly the base+mark joins that *became available* at that stage,
   plus rhythm lines for new bases.

## Schema (glyph entries)

```yaml
ට:                     # key: the character itself, or a slug for families
  type: base           # base | vowel | mark | composite | form-family |
                       # conjunct-system | sign | process
  codepoint: 0DA7
  translit: ṭa
  stage: 1             # scheduled stage
  order: 1             # design order within the stage
  parents: []          # design derivation — validated, drives everything
  requires: [base_height, stroke]   # metric dependencies
  skeleton: bowl       # from `skeletons`
  elements: []         # from `elements`
  spacing: {left: L-tta, right: R-bowl}   # primary class membership
  level: sinhala-0-kernel                 # lanka-glyphsets level tag
  frequency: medium    # qualitative until corpus coverage is computed
  ai:
    construction: ...  # the derivation recipe (what to reuse, what changes)
    checks: [...]      # per-glyph verification steps
```

Form families (`type: form-family`) are single decisions covering many
combinations: `mark` + `hosts` + a `display` label. The family is introduced
by its first designed member and later hosts inherit the convention (e.g.
`fam-i-ghi` is introduced by සි in Stage 3; ඝ inherits it in Stage 6).

## For AI font tools

The `ai_guidance` block in the YAML is written for machine consumption: the
traversal algorithm (topological order over `parents`), spacing inheritance
from class representatives, the freeze/reopen rule (editing a frozen glyph
reopens its transitive descendants), per-glyph `ai.construction` /
`ai.checks`, output naming (`name-sinh`), and an explicit "do not" list.
`stages.json` provides the same data pre-computed. An agent should be able to
build a font stage-by-stage from these two files without reading this README.

## Sources and provenance

Derived from, and intended to supersede, the draft staging in
`tools/sinhala-glyph-chart/font-developemnt-stages.md`, using:

- `tools/sinhala-glyph-chart/sinhala-shape-groups.yaml` — shape taxonomy
  (primary shape groups, elements, side-similarity families, ligature
  families, mark positions)
- `tools/sinhala-glyph-chart/sinhala-anatomy.md` — anatomical vocabulary
  (akshi, pāsha, grantika, …)
- `glyphsets/sinhala-*.yaml` — level inventories
- Research by Pushpananda Ekanayake and Pathum Egodawatta

Unresolved questions inherited from the sources are **data**, not footnotes:
see the `gaps` block in the YAML (rendered at the bottom of the page). The
five build warnings about ම ය ව බ ඛ ධ ණ having no ි family are deliberate —
they keep the taxonomy gap visible until it is resolved.

## Relationship to the other tools

- `tools/sinhala-glyph-chart/` — the base × mark grid used as the Stage 8
  completion-sweep gate; its planned shape-group filters share the same
  taxonomy.
- `tools/feature-generator/` — OpenType feature generation for the Stage 9
  conjunct layer.
- `stages.json` is the integration point: per-stage glyph lists, generated
  drills and cumulative counts, consumable by any of the above.

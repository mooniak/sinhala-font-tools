# composite-map

Builds a **Sinhala composite-glyph map** — which glyphs should be assembled from
component references (base consonant/conjunct + vowel-sign/mark) rather than
drawn as a single merged outline — and applies it to font sources: it can
**rebuild** atomically-drawn or overlap-removed glyphs into proper composites
in any Glyphs source.

## Why

Some Sinhala consonant+mark forms are genuinely compositional — a base plus a
shape-invariant, anchor-attached mark — while others are *not*, even though
their names look regular. A GSUB-based source (Abhaya Libre) draws hundreds of
these atomically; a GPOS-optimised source (Noto Sans Sinhala) attaches the
shape-invariant ones by anchors. This tool learns which forms exist from the
first, the attachment anchors from the second, and — critically — **which forms
are only apparently compositional** from the design-stages form-family model, so
it never claims a false decomposition.

Mark attachment is not uniform (see
[`sinhala-design-stages`](../../sinhala-design-stages/) `mark_systems`):

| mark | composable? |
|------|-------------|
| **rasign** (රකාරාංශය) / **repha** | yes — anchor-driven (`rakar` / `repaya`), all hosts bar per-base exceptions |
| **ුූ** (papilla) | only the DEFAULT below-join (සු). `කු ගු තු භු ශු ඟු` are `u-special`, `දු` `du-form`, `ළු` `llu-form`, `රු` `ra-forms` — fused, **kept drawn** |
| **්** (halkirima) | only the DEFAULT `kodiya` flag. `rahena` (ට් ම් …), `trap` (ඨ් ථ් …), `ja` (ජ්) alternates are fused — **kept drawn** |
| **ිී** (ispilla) | Noto's **three-tier** system: **fused** ligatures (`yI` `khI` `ttI` …) are kept drawn; everything else is a composite of the base + the right i-sign — a per-class **contextual alternate** (`isign-sinh.altN`, from Noto's `iVowelAltN` classes: alt3 = ක ත න, alt6 = ල ළ …) or the **default** `isign-sinh` |

So `kU-sinh` is **not** `ka + usign` (කු is a special right-joined form); it is
recorded in `keep_drawn` with reason `u-special`. Only `sU-sinh` (regular join)
is the composite `sa + usign`. And `kI-sinh` = `ka + isign-sinh.alt3` (ka is in
`iVowelAlt3`), `ghI-sinh` = `gha + isign-sinh` (default), while `yI-sinh` stays
drawn (`ispilla-fused`). The ispilla model is mined live from the anchor
reference's OT classes and precomposed glyphs (see `ispilla.py`).

## The two reference roles

| role | default source | what it contributes |
|------|----------------|---------------------|
| **inventory reference** | Abhaya Libre (`AbhayaLibre.glyphspackage`) | the widest set of drawn conjunct/sign forms → *which* composites exist and their base+sign decomposition |
| **anchor reference** | Noto Sans Sinhala (`NotoSansSinhala.glyphspackage`) | base/mark anchors (`rakar`, `repaya`, `uvowel`, `iVowel`, `alSign`) → *how* each sign attaches |

Both are read-only. Override either with `--inventory` / `--anchor` to build a
map from any other pair of `.glyphs`/`.glyphspackage` sources. The map is then
applied to whatever target font you point `rebuild` at — **not** limited to the
two references.

## Outputs

- **`sinhala-composites.yaml`** (repo root) — hand-editable source of truth.
  Sections: `atoms`, `anchors`, `composites` (with confidence `tier`), `review`
  (sign forms on conjunct bases the family model does not cover — a best-effort
  guess is attached for a human to confirm), and `keep_drawn` (name → reason:
  `ispilla:<family>`, `u-special`, `du-form`, `llu-form`, `hal-rahena`,
  `hal-trap`, `hal-ja`, `ra-forms`, `rakaransaya-exception`, `repaya-exception`,
  or `irreducible` for conjunct bases / ligatures / special forms).
- **`tools/_generated/sinhala-composites.js`** — generated CommonJS/browser
  module (same vendoring pattern as `lanka-glyph-data.js`) for the browser tools.

### Confidence tiers

| tier | meaning | auto-applied |
|------|---------|--------------|
| 0 | already a composite in the inventory source (harvested verbatim) | yes |
| 1 | deterministic consonant + shape-invariant mark (default u/uu/virama, rasign) | yes |
| 2 | `X_repha` = base + repha (repaya anchor, any base) | yes |
| 3 | ispilla ිී = base + `isign-sinh[.altN]` — needs the alternate i-signs in the target, so **opt-in** via `--tiers 0,1,2,3` | no (default) |
| — `review` | u/uu/virama/rasign form on a conjunct base the family model doesn't cover | **no** |
| — `keep_drawn` | fused / atomically-designed / special form (see reasons above) | **no** |

Tier 3 is excluded from the default rebuild because its alternate i-signs
(`isign-sinh.alt3` …) live in the anchor reference, not most cleanup targets; on
a font that lacks them `audit`/`rebuild` report those forms as `blocked` rather
than corrupting them. `atoms.ispilla_alternates` lists the i-sign inventory a
target needs to rebuild them.

The composable-vs-drawn decision is read from the design-stages form-family
model (`sinhala-design-stages/sinhala-design-dependencies.yaml`) plus the
rakaransaya/repaya exceptions in `tools/_generated/shaping-exceptions.js`, so
the map tracks the taxonomy instead of guessing from names.

## Setup

```bash
cd tools/composite-map
python3 -m venv venv && ./venv/bin/pip install -r requirements.txt
```

## Usage

```bash
# 1. build the map from the reference sources  ->  sinhala-composites.yaml
python -m composite_map build-map
#    (or point at other sources)
python -m composite_map build-map --inventory PATH.glyphspackage --anchor PATH.glyphspackage

# 2. export the vendored JS module  ->  tools/_generated/sinhala-composites.js
python -m composite_map export-js

# 3. audit any target font against the map (read-only)
python -m composite_map audit --font path/to/Source.glyphspackage -v

# 4. rebuild drawn/mixed glyphs as composites — DRY-RUN by default
python -m composite_map rebuild --font path/to/Source.glyphspackage
#    write the changes (git is the undo; --backup also copies the source first)
python -m composite_map rebuild --font path/to/Source.glyphspackage --apply
#    restrict to specific tiers
python -m composite_map rebuild --font path/to/Source.glyphspackage --apply --tiers 1,2
```

`rebuild` only touches glyphs the map marks as composites **and** that are
currently drawn (atomic/mixed) **and** whose components exist in the target
font. Glyph entries are never added or removed, so GSUB/GPOS feature code that
references these glyph names keeps working. `review` and `keep_drawn` glyphs are
never modified.

## How writes are made

- A **`.glyphspackage`** is edited glyph-file by glyph-file: only the changed
  `glyphs/*.glyph` files are rewritten (openstep-plist, Glyphs-native
  formatting); `fontinfo.plist`, `order.plist` and every untouched glyph stay
  byte-for-byte identical.
- A single **`.glyphs`** file is mutated and saved through `glyphsLib`.

In both cases each rebuilt layer keeps its advance width (drawn Sinhala base+mark
forms already advance by the base width) and gets component references with
automatic (anchor-driven) alignment; positioning then relies on the target
font's own base/mark anchors when opened in Glyphs.

## Files

```
composite_map/
  lanka_data.py   canonical letter inventory + consonant/vowel/sign classification
  families.py     form-family / mark-system model (which forms are NOT composites)
  ispilla.py      Noto's three-tier ිී system, mined from the anchor reference
  grammar.py      family-grounded base+mark classification (composite/drawn/review)
  glyphsio.py     glyphsLib read/classification helpers
  mapbuild.py     derive the map from the two references + the family model
  packageio.py    surgical openstep-plist writer for .glyphspackage
  rebuild.py      audit / plan / apply engine (format-dispatching)
  jsexport.py     YAML map -> vendored JS module
  cli.py          `build-map` · `export-js` · `audit` · `rebuild`
```

The letter classification is validated against
`tools/_generated/lanka-glyph-data.js` on every run; if lanka-glyphsets adds or
removes a letter the build fails loudly rather than miscategorising it.

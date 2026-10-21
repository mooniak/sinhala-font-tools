# Sinhala letter anatomy

The vocabulary this repo uses for the parts of Sinhala letterforms: what each
part is called, what it looks like, and where it shows up in the
[design-stages model](sinhala-design-dependencies.yaml).

The model's `elements` block points here through its `anatomy:` field. Terms
used in the model's `ai.construction` and `ai.checks` notes (akshi, grantika,
pāsha …) are defined below.

## Sources and status

- **Terminology** (§2–§4): collected from dissertation research on Sinhala
  letterform anatomy, which gives the parts their traditional names and sorts
  some of them into named variants. The original citation still needs to be
  added. Romanisations follow the source. Where the source spelling looks
  garbled, the normalised form is shown with the source spelling in a note.
- **Design notes** (§5): from
  [`resources/sinhala-anatomy-notes.pdf`](../resources/sinhala-anatomy-notes.pdf),
  a set of annotated drawings of Sinhala letter groups.
- **Model mapping**: the right-hand columns show where a term is used in
  `sinhala-design-dependencies.yaml`. A blank cell means the model does not
  yet use that part as a reusable element.

## 1. Vertical zones

Sinhala letters sit almost entirely in one band. The model names each line as
a metric that one glyph commits (see `metrics:` in the model).

| Zone / line | Model metric | Committed by | Notes |
|---|---|---|---|
| Base height (the Sinhala "x-height") | `base_height` | ස | Top of the letter body. Nearly every glyph lives between this and the baseline. |
| Above-mark zone | `mark_height` | ි | Ceiling for ි ී and the ් flag. |
| Below-mark depth | `mark_depth` | ු | Depth of ු ූ (and ෘ ෲ). |
| Consonant tail depth | `tail_depth` | ඩ | Descenders of letters such as ඩ ඬ. |
| Aeda-pilla depth | `hook_depth` | ැ | The ැ ෑ hooks below the baseline. |
| Conjunct depth | `conjunct_depth` | rakaransaya | Depth budget for ්‍ර and stacked conjuncts. |

The drawings in the anatomy notes use the same lines: baseline and base height
inside, ascender and descender limits outside.

## 2. Script components

The linguistic building blocks. These are units of the writing system rather
than parts of a stroke, but each one has its own design problem.

| Component | Traditional term | What it is | In the model |
|---|---|---|---|
| Independent vowel | — | A vowel written on its own, at the start of a word (අ ආ ඉ …). | `type: vowel` |
| Consonant | — | The core letters; each carries an inherent *a*. | `type: base` |
| Vowel sign | *pili* / *pillama* | A dependent mark that changes the inherent vowel. The upper sign ි is *ispilla*; the lower sign ු is *papilla*. | `mark_systems.ispilla`, `mark_systems.papilla` |
| Virama | *al-lakuna* / *hal kirīma* | Removes the inherent vowel. The source names two looks, a **flag** (ක්) and a **cap** (ම්) for letters with counter-clockwise strokes. The model splits it into four forms: kodiya flag, rahena wrap, trap-top and ja-shape. | `mark_systems.halkirima` |
| Special consonant signs | *yansaya*, *repaya*, *rakaransaya* | Combined forms used in writing but not part of the alphabet. | Stage 9 conjunct systems |
| Conjunct consonant | *baddha akshara* (bandi akuru) | Two or more consonants joined into one unit to save space. | Stage 9; element `twin_body` |

## 3. Stroke primitives

The parts a letter is drawn from.

| Part | Term | Definition | Variants named in the source | Model element |
|---|---|---|---|---|
| Eye | *Akshi* | A curved stroke that closes on itself into a small counter. | Opened (*Vivṛta*), Closed (*Sanvṛta*), Horned (*Śṛṅgika*), Trunk (*Śuṇḍa*), Navel (*Nābhi*) | `eye_ka` (closed eye of the arch family); `eye_line` (eye reached by an entry stroke) |
| Body / base stroke | *Skandha* | The main structural part, sitting on the baseline. | Full (*Pūrṇa*), Frontward-backward (*Pūrva-apara*), Broken (*Bāṅgika*), Pointed (*Śulita*) | expressed as `skeletons` (bowl, trap body, double bowl, arch, U-bottom, diagonal) |
| Ascender stroke | *Ārohana* | Rises from the middle of the letter toward the top line. | — | — |
| Descender stroke | *Avarohana* | Drops from the baseline toward the bottom line. | — | `tail` (with a knot) |
| Knot | *Grantika* | Formed where strokes overlap or cross each other. | — | `tail` |
| Hook / bearer | *Dhāraka* | An in-between stroke that joins parts, e.g. an eye to an ascender. | — | — |
| Hump | *Gaṇḍa* | A horizontal stroke, parallel to the baseline, joining two halves of a letter. | — | `twin_body` |
| Stem / arm | *Bāhuva* | A straight stroke. | Horizontal (*Tiryak*), Fallen/vertical (*Avanata*), Upward (*Unnata*) | `diagonal` (an inclined bāhuva) |
| Spiral | *Śaṅkaya* | A clockwise turning stroke drawn at base height. | — | — (kunddaliya ෴ uses it) |
| Shoulder | *Uro* | A curve drawn parallel to the body, either joined to it or beside it. | — | — |
| Loop | *Pāsha* | A stroke that changes direction and overlaps itself without crossing. | By zone: ascending, middle, descending | `loop` (ඔ ම ඹ); `hang` (descending pāsha) |

Spelling notes: the source writes *Pùrṇa* and *Pùrva-apara* (normalised to
*Pūrṇa*, *Pūrva-apara*), *Arohana* (normalised to *Ārohana*), *Sandi*
(normalised to *sandhi* in §4) and *Śṅkaya* (normalised to *Śaṅkaya*;
confirm against the original).

Model elements with no traditional term yet: `trap` (the open-top counter of
එ ඨ ඪ ඵ) and `fork` (the internal divider that turns ප into ය).

## 4. Joints and terminals

How strokes meet and end.

| Part | Term | Definition | Model use |
|---|---|---|---|
| Eye joint | *Akshi dhāraka sandhi* | Where the eye joins the stroke before it. | checks on ත-family glyphs ("eye joint clean") |
| Curve-to-curve joint | *Dvivakra sandhi* | Where two round shapes collide. | `twin_body` |
| Right-angle joint | *Chandra vaṇka sandhi* | A connection made with right-angled strokes. | — |
| Intersection | *Vedaka* | Where two separate strokes overlap. | — |
| Terminal | *Agra* | How a stroke ends. | the rahena ් and ි wrap forms are chosen by a base's top terminal (`hal-rahena`, `fam-i-term`) |

## 5. Design notes by letter group

From [`resources/sinhala-anatomy-notes.pdf`](../resources/sinhala-anatomy-notes.pdf).
The groups in the notes match the model's skeletons closely; the model column
shows which one.

| Group in the notes | Model skeleton / class |
|---|---|
| උ අ ද ඳ | `u_bottom` |
| ක ත න | `arch` (left class `L-ka`) |
| ග ශ හ භ | `arch` |
| ස ඝ · ය · ප ෂ ජ ඡ | `double_bowl` (right class `R-pa`); ජ ඡ carry the `diagonal` element |
| the ට bowl row (ට ච ඩ ධ …) | `bowl` |
| the එ trap row | `trap_body` |
| ම ඔ ඹ | loop (`loop` element, `R-round`) |
| ර ඊ | `diagonal` |
| also listed: ඉ, ණ, බ ඛ, ල ළ | — |

### The eye

- The eye traditionally **starts with a knot**. Dropping the knot is acceptable,
  and in practice required in monoline fonts. Typefaces like Iskoola Pota keep
  a "considered" knot.
- In letters with an eye, the curve below the eye should reach **at least as
  far left as the eye's left edge**. The eye can be pushed inward, never
  outward past the body.

### ක ත න

- The handwriting stroke order matters for this group. The notes number the
  strokes of ක to show the written path.
- The **peck-like corner at the lower left** should sit slightly further left
  than the eye.
- Iskoola Pota's variant ක shows that the group can take some change without
  looking distorted.

### ස ඝ · ය · ප ෂ ජ ඡ

- Apart from ය, these letters should look roughly **left–right symmetrical**
  in their shared base form.
- In ඝ, whether the counters close at the three junctions is a free design
  choice.
- In ජ and ඡ, the final rising stroke can be a straight line.

### ග ශ හ භ

- The shared form implies two overlapping circles and some symmetry. The
  **right half may be slightly larger** than the left.
- ප and හ come from the same writing tradition, but හ looks closer to ග. Draw
  it from the arch family, not from ප.

### ර ඊ

- ර is written as a bowl that continues into a rising diagonal. The diagonal
  is the end of the stroke, not a separate stem.

## 6. Open questions

Raised in the research and not yet answered here:

- What distinguishes the "Style A" and "Style B" letterform traditions in the
  source research?
- How did quill and ink shape the letterforms, and
  which features are writing-tool artefacts rather than structure?
- How did the eye (*akshi*) develop visually over time, and do its five
  variants match recognisable historical stages?
- Which unnamed model elements (`trap`, `fork`) have traditional names?

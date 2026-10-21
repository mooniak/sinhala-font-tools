# Generated test text

Written by [`tools/test-generator/make-test-texts.js`](../../tools/test-generator/make-test-texts.js) (seed 1) — **do not edit by hand**; rerun the script instead. Derived from the UCSC LTRL Sinhala corpora under the LGPL-LR ([licence](../corpus-build/LICENSE-LGPL-LR.txt)).

These sit in a subfolder on purpose: files in `test-texts/` itself are picked up by the proof-PDF tool, and these are copied to the two consumers only when you decide to.

| File | What it is |
|---|---|
| `stages.md` | Per design stage 1–10 (cumulative): glyph list, template sentences, running text, real sentences (when enough exist), invented words |
| `levels.md` | The same for glyphset levels Kernel and Core |
| `targeted-*.md` | Real sentences densest in rakaransaya, yansaya, repaya, conjuncts, each vowel sign, and the rare letters (in at most 6,000 corpus sentences) |

In the stage and level files **TEMPLATES** are real news sentences with the words the font cannot yet show replaced by invented words of the same shape; **TEXT** is running text from word-pair statistics; **SENTENCES** are verbatim real sentences (only where a font has enough common graphemes to have any); **INVENTED** is a list of made-up words. Invented words follow Sinhala word-shape rules but are not real words, so they are not marked in the files; the table below says how much of each section is invented. Every listed grapheme appears at least once in TEMPLATES and in TEXT.

## Statistics

| File | Section | Kind | Words | Invented | Graphemes shown |
|---|---|---|---|---|---|
| stages.md | Stage 1 — Bootstrap | templates | 55 | 78% | 13 / 13 |
| stages.md | Stage 1 — Bootstrap | chain | 60 | 38% | 13 / 13 |
| stages.md | Stage 1 — Bootstrap | invented words | 30 | 97% | 13 / 13 |
| stages.md | Stage 2 — Bowl derivatives | templates | 50 | 64% | 23 / 23 |
| stages.md | Stage 2 — Bowl derivatives | chain | 60 | 25% | 23 / 23 |
| stages.md | Stage 2 — Bowl derivatives | invented words | 30 | 97% | 23 / 23 |
| stages.md | Stage 3 — Arch family and spacing marks | templates | 58 | 55% | 65 / 65 |
| stages.md | Stage 3 — Arch family and spacing marks | chain | 60 | 3% | 65 / 65 |
| stages.md | Stage 3 — Arch family and spacing marks | invented words | 30 | 100% | 63 / 65 |
| stages.md | Stage 4 — High-frequency completion | templates | 102 | 18% | 179 / 179 |
| stages.md | Stage 4 — High-frequency completion | chain | 110 | 5% | 179 / 179 |
| stages.md | Stage 4 — High-frequency completion | real sentences | 29 | 0% | 48 / 179 |
| stages.md | Stage 4 — High-frequency completion | invented words | 30 | 93% | 81 / 179 |
| stages.md | Stage 5 — Loops, diagonals and long marks | templates | 160 | 9% | 284 / 284 |
| stages.md | Stage 5 — Loops, diagonals and long marks | chain | 177 | 7% | 284 / 284 |
| stages.md | Stage 5 — Loops, diagonals and long marks | real sentences | 40 | 0% | 70 / 284 |
| stages.md | Stage 5 — Loops, diagonals and long marks | invented words | 30 | 97% | 86 / 284 |
| stages.md | Stage 6 — Aspirates and dense derivatives | templates | 253 | 9% | 436 / 436 |
| stages.md | Stage 6 — Aspirates and dense derivatives | chain | 265 | 9% | 436 / 436 |
| stages.md | Stage 6 — Aspirates and dense derivatives | real sentences | 59 | 0% | 82 / 436 |
| stages.md | Stage 6 — Aspirates and dense derivatives | invented words | 30 | 100% | 97 / 436 |
| stages.md | Stage 7 — The hang system | templates | 296 | 13% | 495 / 495 |
| stages.md | Stage 7 — The hang system | chain | 302 | 13% | 495 / 495 |
| stages.md | Stage 7 — The hang system | real sentences | 56 | 0% | 98 / 495 |
| stages.md | Stage 7 — The hang system | invented words | 30 | 93% | 93 / 495 |
| stages.md | Stage 8 — Completion sweep | templates | 355 | 15% | 553 / 553 |
| stages.md | Stage 8 — Completion sweep | chain | 347 | 16% | 553 / 553 |
| stages.md | Stage 8 — Completion sweep | real sentences | 84 | 0% | 101 / 553 |
| stages.md | Stage 8 — Completion sweep | invented words | 30 | 100% | 103 / 553 |
| stages.md | Stage 9 — Conjunct layer | templates | 591 | 23% | 877 / 877 |
| stages.md | Stage 9 — Conjunct layer | chain | 582 | 23% | 877 / 877 |
| stages.md | Stage 9 — Conjunct layer | real sentences | 62 | 0% | 87 / 877 |
| stages.md | Stage 9 — Conjunct layer | invented words | 30 | 100% | 109 / 877 |
| stages.md | Stage 10 — Long tail and polish | templates | 595 | 24% | 888 / 888 |
| stages.md | Stage 10 — Long tail and polish | chain | 606 | 23% | 888 / 888 |
| stages.md | Stage 10 — Long tail and polish | real sentences | 96 | 0% | 116 / 888 |
| stages.md | Stage 10 — Long tail and polish | invented words | 30 | 100% | 102 / 888 |
| levels.md | Kernel (level 0) | templates | 591 | 23% | 875 / 875 |
| levels.md | Kernel (level 0) | chain | 569 | 23% | 875 / 875 |
| levels.md | Kernel (level 0) | real sentences | 77 | 0% | 108 / 875 |
| levels.md | Kernel (level 0) | invented words | 30 | 93% | 92 / 875 |
| levels.md | Core (level 1) | templates | 594 | 24% | 888 / 888 |
| levels.md | Core (level 1) | chain | 589 | 24% | 888 / 888 |
| levels.md | Core (level 1) | real sentences | 84 | 0% | 105 / 888 |
| levels.md | Core (level 1) | invented words | 30 | 97% | 104 / 888 |

Targeted collections hold real sentences only (nothing invented).

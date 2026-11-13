# Sinhala test-text corpus

Curated Sinhala (and some multi-script) test strings for font proofing and
type testing: display paragraphs, kern-pair and conjunct word lists, numeral
and punctuation samples, classical/Pali/Sanskrit text, and short pangrams.

This is the **canonical source**. It is vendored (copied, not linked) into two
downstream consumers, each for a different purpose:

- [`font-directory`](https://github.com/mooniak/font-repos)'s
  `mnik/tools/proofpdf/sections/` — renders these as pages in each font's
  proof PDF (any `.md` dropped there becomes a proof section automatically,
  see that tool's own `__init__.py`).
- [`polytypetester`](https://github.com/mooniak/polytypetester)'s
  `testing-templates/mooniak/sinhala/` — plain `.txt` (frontmatter/headers
  stripped) for that tool's live type-testing UI.

If you add, edit, or remove a file here, copy the change into both consumers
by hand (there's no automated sync yet) — see the README in each of those
directories for the exact mapping.

## Tamil

The `tamil-*.md` files (`tamil-alphabet`, `tamil-numerals`, `tamil-prose`, `tamil-kern-pairs`, plus the older
`tamil-pangram`) are Tamil test text. They live here, not in a repo of their own, so they ride the same vendor path to
the two consumers above. The proof tool shows them only to fonts that cover Tamil — see
`mnik/tools/proofpdf/gates.json` (`scripts`) in font-repos; it needs no change when a Tamil file is edited, only when
one is added (list it there).

Imported from [enathu/tamil-font-testing-page](https://github.com/enathu/tamil-font-testing-page) (Niram; itself
derived from Pablo Impallari's Font Testing Page): the akshara lettering sheet, prose, layout article and Tamil kern
strings, with the markup stripped. Its Latin text, hinting charset, world-script blocks and Latin kerning strings were
not imported. Credits are in each file's frontmatter (`source:` is the upstream repo).

## Generated text

[`generated/`](generated/) holds realistic text written by
[`tools/test-generator/make-test-texts.js`](../tools/test-generator/make-test-texts.js)
from the UCSC corpora: text for a font at each design stage or glyphset level,
and real sentences dense in rakaransaya, yansaya, repaya, conjuncts, each vowel
sign and the rare letters. It is a subfolder so the proof-PDF tool does not pick
it up on its own; copy files to the two consumers when you want them there. Do not
edit it by hand — rerun the script. Its own README lists what each file holds and
how much of each section is invented.

## Word list

[`wordlist/si.txt`](wordlist/si.txt) is a plain Sinhala word list, one word per
line. To search it for words containing given graphemes or signs, load it into
[test-generator](../tools/test-generator/) with **Load word list…** and use
**Must include** with the *Word list* format.

## File format

Most files carry YAML frontmatter (`title`, `credits`, `license`, ...)
followed by Markdown body text. A few simple word/string lists have no
frontmatter. `## `-prefixed lines inside a file are content section headers
(e.g. grouping conjunct test words by cluster), not document structure.

## Provenance

Several files are researched/attested content, not placeholder text — keep
existing `credits` / `copyright` frontmatter intact when editing. Notably
`display-strings.md` credits Mooniak, Pushpanada Ekanayake, and LTRL/UCSC; do
not casually rephrase the sample paragraphs.

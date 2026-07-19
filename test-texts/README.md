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

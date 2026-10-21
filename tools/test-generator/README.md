# test-generator

A test-text generator for Sinhala, in the spirit of
[adhesiontext](https://adhesiontext.com): list the graphemes a font has so far,
and get text that uses **only those graphemes** — real sentences where the set is
large enough, real sentence shapes with invented words where it is not.

The unit is the **grapheme**: what a designer draws or composes, not a Unicode
code point. ටු, කෝ, ක්, ක්‍රි and ර්‍කා are each one grapheme. A font may draw
ටු as one glyph or compose it from ට + ු; either way, ටු is one grapheme.

## Running

Serve the repo root (the page fetches the data bundle and the stage model):

```sh
python3 -m http.server 8000      # from the repo root
open http://localhost:8000/tools/test-generator/
```

The text comes from [`data/`](data/), built from the UCSC Sinhala corpora by
[`test-texts/corpus-build`](../../test-texts/corpus-build/) (`node test-texts/corpus-build/build.js`; the
raw corpus is not in the repo). Drop a font (`.ttf`/`.otf`/`.woff`/`.woff2`) to
preview the output in it. Dropping or loading a `.txt` / `.md` replaces only the
*word list* behind Word list, Lines of words and the Unlock / Coverage panels.

## Grapheme set

Type glyph names, Sinhala text, or both — or start from a **preset**: what a font
has reached by a design stage 1–10 ([design-stages](../design-stages/),
cumulative) or by glyphset level Kernel / Core. Presets list letters and signs and
turn on *also build from parts*.

```
tta-sinh sa ttI-sinh kU      ← names (with or without -sinh)
සට ටුසු පසු                   ← text: split into graphemes ට ස ටු සු ප සු
```

Names follow lanka-glyphsets; a name resolves if the standard defines it or
any grapheme in the corpus carries it (e.g. `kOo-sinh` for කෝ).

**Also build from parts** — off by default, so ටු is available only when ටු
is listed. When on, a grapheme is also available when it can be assembled from
listed pieces: base + signs (ට + ු), rakaransaya / yansaya / repaya pieces
(ක + `rasign` + ි), or a listed ligature plus signs (`kRa` + ි).

## Numerals & punctuation

Numbers, dates, times and punctuation marks can be added to the engine formats
(templates, running text, real and targeted sentences). *Where* puts each item
between sentences (a line of its own in one-per-line layout) or inside a
sentence after a word; *How often* sets the share of sentences that get one;
*Digits* picks 0–9, Sinhala Lith digits ෦–෯, or a mix. Items are digits and marks
only (`2026-10-20`, `14:30`, `1,250.50`, `…`), never letters, so the grapheme
set still holds. Not applied to Word list, Lines of words or Invented words, and
not counted in the stats. Code: [`extras.js`](extras.js).

## Output

| Format | What it gives |
|---|---|
| **Template sentences** | Real news sentences; words the font can render are kept, the rest become invented words of the same shape. Default; works at any set size. |
| **Running text** | Text from corpus word-pair statistics. |
| **Real sentences** | Verbatim sentences. Needs roughly 90+ common graphemes, otherwise the page says so. |
| **Targeted sentences** | Real sentences densest in the target typed in *Must include*: graphemes, a sign (`usign`), or `rakar` `yansa` `repha` `conjunct`. |
| **Invented words** | A list of invented words. *Must include* graphemes are cycled through them. |
| **Lines of words**, **Word list** | Real words from the word list, as before. *Must include* filters them. |

- **Natural ↔ coverage** pulls word choice toward graphemes not yet shown.
- **Invent when needed, at most N %** invents only when real words cannot supply
  length or graphemes; **Invent a share of N %** always invents that share. In
  template sentences the words the font cannot show are always replaced, and the
  cap only picks sentences that need the fewest.
- **Show every grapheme at least once** is guaranteed for the generated formats.
  When a set has more graphemes than the text has room for, the rest are added in
  short extra sentences, so the output can run past the requested count.
- **Underline invented words** is display only: **Copy** and **Download** are
  always clean text.
- **Sources** choose news / other sentences and headlines, names and dictionary
  words, Latin text and explicit ZWNJ forms (both off by default).
- **Show grapheme names** annotates each word; downloaded word lists then include
  them (tab-separated).
- **New text** draws a new seed; the same seed and settings give the same text.

## Analysis panels

- **Unlock** — graphemes that are the only thing missing from the most words.
  Click to add.
- **Coverage** — matching words per listed grapheme; graphemes with no words
  are flagged.
- **Corpus graphemes** — every grapheme in the corpus by frequency, coloured by
  availability (green: listed, blue: built from parts). Click to toggle.
- **Analyse text** — split any text into graphemes; use the result as the set.

## Files

- `graphemes.js` — segmentation, naming and availability (UMD; usable from
  Node: `require("./graphemes.js")`).
- `textgen.js` — the text engine, below.
- `presets.js` — the stage / level grapheme sets, shared by the page and the script below.
- `make-test-texts.js` — writes [`test-texts/generated/`](../../test-texts/generated/) (see below).
- `app.js`, `index.html`, `styles.css` — the page.
- `data/` — the generated bundle; `test/` — engine tests.
- Names come from
  [`../glyphname-unicode-converter/lankaglyphset-map.js`](../glyphname-unicode-converter/lankaglyphset-map.js).

## Text engine (`textgen.js`)

The engine behind the generated formats, usable from the browser and from Node. It
reads the [data bundle](data/) built by [`test-texts/corpus-build`](../../test-texts/corpus-build/).

```js
const TG = require("./textgen.js");
const eng = await TG.load(TG.dirReader("data"));        // browser: TG.load(path => fetch(…).then(r => r.text()))
const s = eng.session(TG.expand(["ක", "ට", "ස"], ["ි", "ු"]));   // the font's graphemes
TG.render(s.chain({ seed: 1, words: 60 }));
```

| Call | What you get |
|---|---|
| `s.chain({seed, words, coverage, invent, cover})` | Running text from corpus word-pair statistics. `coverage` 0–1 pulls toward under-used graphemes; `cover` (default on) guarantees every listed grapheme appears. |
| `await s.templates({seed, count, …})` | Real news sentences with the words the font can render kept and the rest replaced by invented words of the same shape; punctuation and numerals stay. Best for small sets. |
| `await s.loadSentences()` then `s.sentences({seed, count, minWords, exclude, sources})` | Verbatim real sentences. Only the shards that can hold a usable sentence are fetched. A font needs roughly 90+ common graphemes before there are any. |
| `s.targeted({graphemes, signs, classes}, {count, minHits})` | Real sentences densest in a grapheme, a sign, or `rakar` / `yansa` / `repha` / `conjunct`. |
| `s.pseudo({seed, count, contains})` | A list of invented words, one per "sentence". |
| `s.info()` | Real words available, graphemes with no real word, signs and pieces listed on their own. |

Every result is `{ sentences: [[{t, w, inv}]], stats }`; `inv` marks invented
words and `stats` has `words`, `invented`, `inventedPct`, `shown`, `missing`.
`TG.render(result)` gives plain text (invented words unmarked).

Session options: `fromParts` (as in the page), `sources` (`{running, names, dict}`),
`minFreq` (running-text words seen fewer times are treated as typos, default 3),
`zwnj` (allow words with an explicit ZWNJ, off). Sentence filters take
`exclude` tag letters (default `"ln"`: Latin, ZWNJ) and `sources` (`"12pe"…`).

### Invention

`invent: { mode: "auto", max: 0.4 }` (default) invents only when needed — a real
vocabulary too small to avoid repeating itself, or a grapheme no real word uses
— and never beyond `max`. `invent: { mode: "ratio", ratio: 0..1 }` invents that
share regardless. An invented word is made by, in order of use:

1. **pattern swap** — a real word's sign sequence (`∅ ි ∅`) with new letters;
   a sign the font lacks becomes its nearest relative (ී→ි, ේ→ෙ, ෝ→ො, ෑ→ැ, …);
2. a **learned model** — letters chosen by how often they start/continue words
   and take each sign;
3. a **random permutation**.

All three obey the same hard rules, and a result that turns out to be a real word
is reported as real:

| | Rule |
|---|---|
| H1 | independent vowels (අ ආ ඉ…) only open a word |
| H2 | ං ඃ never open a word, follow a hal form, or follow each other |
| H3 | a hal form opens a word only if the corpus shows it (ස් ක් ද් ප් බ් න් ම් ග් ත් ෆ්) |
| H4 | no hal form after a hal form |
| H5 | no grapheme three times in a row |
| H6 | invented words have at least two graphemes |

`eng.violations(word)` lists the rules a word breaks. Against held-out corpus
words (never seen in training) the model finds real words 2.4× as often as
random permutation does (1.10 % vs 0.46 %).

### Generating test-texts

```sh
node tools/test-generator/make-test-texts.js [--out DIR] [--seed N]    # ~12 s
```

Writes per-stage and per-level text (glyph list, template sentences, running text,
real sentences where a font has enough graphemes, invented words) and real-sentence
collections for rakaransaya, yansaya, repaya, conjuncts, each vowel sign and the
rare letters, into `test-texts/generated/`. Deterministic for a seed and data
bundle; invented words are unmarked in the files and quantified in that folder's
README.

### Tests

```sh
node --test tools/test-generator/test/textgen.test.js            # needs data/ (node test-texts/corpus-build/build.js)
node --test tools/test-generator/test/extras.test.js              # no data needed
node --test tools/test-generator/test/make-test-texts.test.js    # generates twice; ~30 s
```

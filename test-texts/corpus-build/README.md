# corpus-build

Turns the raw [UCSC LTRL Sinhala corpora](http://ltrl.ucsc.lk) into the compact
data bundle that [`test-generator`](../../tools/test-generator/) loads: words and their
frequencies, word-pair counts, a word-invention model, and a sharded set of real
sentences. The raw corpus (94 MB) is **not** in the repo; only what this tool
derives from it is.

```sh
# put the corpus at test-texts/sinhala-corpora-master/ (gitignored), then:
node test-texts/corpus-build/build.js
```

No dependencies (Node ≥ 18). It reads sentence segmentation from
[`test-generator/graphemes.js`](../../tools/test-generator/graphemes.js), so what the build
and the browser call a grapheme can never drift apart. A full run takes ~12 s
and is deterministic (hash-seeded, no timestamps), so re-running on the same
corpus gives byte-identical files. **Rebuild rarely** — the shards are ~29 MB,
and every rebuild that changes them adds to the repo's history.

## What it does

1. **Reads** every source — news V1/V2 (2004–07, 2010–13), the English–Sinhala
   parallel text (Sinhala side), NER-tagged sentences, WordNet glosses, proper
   names, the ingiya dictionary and the functional-word lists. Files are UTF-16
   (both byte orders) and UTF-8 mixed; all are decoded and NFC-normalised.
2. **Cleans** each Sinhala run (see below).
3. **Counts** words (running-text frequency; which word lists carry them),
   word pairs, and the statistics of how words are built.
4. **Selects** sentences: filters, de-duplicates, ranks graphemes by use, files
   each sentence under its rarest grapheme and keeps up to *K* per grapheme
   (*K* is chosen to land on `--sentences`).
5. **Writes** `tools/test-generator/data/` and a `manifest.json` with every count,
   the cleaning tallies, sentence-reject reasons and file sizes.

## Cleaning

Applied per Sinhala run, so Latin, digits and punctuation around it are untouched.

| | Rule | Why |
|---|---|---|
| repair | `ZWJ ්` → `් ZWJ` | older files type the joiner first (≈2.9k runs) |
| repair | ZWJ not between `්` and a consonant → dropped | stray joiners, word-initial and word-final |
| repair | ZWNJ other than `් ZWNJ C` → dropped | legacy typesetting artefact (≈68k) |
| keep | `් ZWNJ C` (ස්‌ට) | deliberate non-joining; the sentence is tagged `n` |
| reject | starts with a sign; two signs in a row; sign after `්` or after an independent vowel or after ං/ඃ; `්්`; unassigned code points | corrupted font conversion (≈3.9k runs) |

A rejected run drops that word, and any sentence that contained it. The
suffix-splitting seen in the 2004–07 files (`ලංකාව ට`) turned out to be rare
outside the numeral particle `ක්`, so words are **not** re-joined.

Sentences are kept when they are at least 25 characters (there is no upper
limit), have ≥ 4 Sinhala words, ≥ 60 %
Sinhala letters, use only Sinhala/Latin/digits/common punctuation, start with a
Sinhala letter or digit, have balanced brackets and quotes, and either end in
`. ? !` or are a whole short line (a headline, tag `h`).

## Output

All under `tools/test-generator/data/`:

| File | Content |
|---|---|
| `words.txt` | `word<TAB>frequency[<TAB>mask]`, most frequent first. Frequency counts running text only; `mask` bits say which word lists carry it: 1 person name, 2 place, 4 water body (river/reservoir), 8 dictionary, 16 functional word. Kept when seen ≥ `--wordsMin` times or listed by any word list. |
| `bigrams.json` | Word pairs. `next[c]` is `"j:n,j:n,…"`, the most common words after context `c`. Index 0 sentence start, 1 `,`, 2–4 `.` `?` `!`, and `5+i` = row *i* of `words.txt`. Only the `vocab` most frequent words take part. |
| `model.json` | What the word-invention model learns: grapheme-count distribution, sign "skeletons" (e.g. `∅ ි ∅`), which bases open/continue a word, which sign each base takes where, the sign that follows a sign, and which hal forms may open a word. Counts are `sqrt(freq)×10`. |
| `templates.txt` | 20 000 ordinary sentences of 6–16 words, for template mode. |
| `names.txt` | `kind<TAB>name`, kind = person / place / water. |
| `sentences/index.json`, `sentences/s-NN.txt` | The real sentences. `index.json` lists graphemes most- to least-used and, per shard, the rank range `[lo, hi]` of the rarest grapheme of its sentences. A font with grapheme set *S* needs only shards whose range contains a grapheme of *S*. |

Sentence lines are `tags<TAB>text`. Tags: `1` `2` news V1/V2, `p` parallel
text, `e` NER, `g` gloss · `h` headline/short line · `l` contains Latin ·
`d` contains digits · `n` contains ZWNJ.

## Options

`--corpus DIR`, `--out DIR`, `--sentences 150000`, `--shard 5000`,
`--templates 20000`, `--forcedMax 2000`, `--wordsMin 2`, `--vocabMin 5`,
`--pairMin 4`, `--maxSucc 60`, `--modelMin 3`, `--seed 1`.

`--sentences` trades size for coverage on small fonts. The build prints how
many complete sentences a font with only the N most-used graphemes can show
(`coverageByTopGraphemes` in the manifest). At the default, every such sentence
is shipped up to 100 graphemes (5 538), 94 % at 120, 60 % at 160 and 45 % at 200 —
the cut falls where sentences become abundant.

## Licence

The corpora are © Language Technology Research Laboratory, University of Colombo
School of Computing, under the **LGPL-LR** (Lesser General Public License for
Linguistic Resources): free for research and for software distributed under
open-source licences; contact LTRL for commercial use. The licence text is in
[LICENSE-LGPL-LR.txt](LICENSE-LGPL-LR.txt). Data derived by this tool carries
the same terms. The `names.txt` and `words.txt` lists are word-level extracts;
the sentence shards are verbatim sentences from the news corpora.

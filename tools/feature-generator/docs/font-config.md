# Per-font settings: `sources/lankafea.yaml`

lankafea generates a font's Sinhala (and Tamil) OpenType features from the LankaGlyphset
standard and the glyphs the font has. What the standard can't know, a font keeps in one
file beside its source, `sources/lankafea.yaml`. `lankafea generate` and `lankafea validate`
find it there on their own; `--config FILE` points elsewhere and `--no-config` ignores it.

The file has one section per script, so a source with both scripts keeps one file:

```yaml
sinhala:
  inject: [lankafea]
  assign:
    groups:
      - {group: DaShape, to: dlig, mode: copy}
      - {group: AnusvaraSha, to: ss03}
  dist: -113
  numerals: {lith: ss07, lithTens: rlig, archaic: ss08}
  featureNames:
    ss01: Sinhala Da forms
tamil:
  inject: [tamil-styles.fea]
```

Every setting is optional. An unknown one is reported and ignored.

## `inject`

Directories or files, relative to the settings file, of extra rules merged into the
generated features (see `inject/README.md`). YAML rules are gated on the font's glyphs like
generated ones; `.fea` files are copied in as they are. A directory's files merge in name
order, which matters when one file's rules work on another's output.

Use it for what is the font's own design and not the standard's, such as Abhaya Libre's
positional repaya and candrabindu variants (`repha-sinh.001`–`.010`).

## `assign`

Routes generated rule groups (lookups) and numbered alternates to other features: the
`--assign` JSON, written in YAML. `mode: move` (the default) takes the group out of its
feature; `mode: copy` keeps it there too.

```yaml
assign:
  groups:
    - {group: DaShape, to: dlig, mode: copy}   # Da forms in dlig as well as ss01
    - {group: AnusvaraSha, to: ss03}           # ං + ශ in ss03 instead of dlig
  alts: {"2": dlig, "3": none}                 # .alt2 glyphs in dlig; .alt3 in aalt only
```

`lankafea validate` lists the groups a font has.

## `dist`

How far a touching cluster's second consonant moves towards the first (GPOS `dist` on
`touch-sinh`), in font units. Default −90.

## `numerals`

The standard names the Lith digits and the archaic numbers but no feature for them, so
these sets are generated only when a font says where they go:

| Key | Rules | Example |
|---|---|---|
| `lith` | ASCII digits → Lith digits, then the ten-ligatures | `7 → lithseven`, `10 → lithone_lithzero` |
| `lithTens` | Lith digit + Lith zero → the ten-ligature | `෧෦ → lithone_lithzero` |
| `archaic` | ASCII digits → archaic numbers: units, tens, 100, 1000 | `90 → archaicninety` |

Each takes a tag or a list of tags. Sets on ASCII digits are registered for `DFLT` and
`latn` as well as `sinh`, because HarfBuzz shapes a run of digits as `DFLT`.

## `featureNames`

The name an app shows for a stylistic set. Without one, a set the standard defines gets the
standard's name ("ss01 Da Forms" → "Da Forms"). Fonts released before should keep the names
their users know.

## Regenerating

In a Mooniak font repo, `make features` runs lankafea for every script in the settings file
and writes the result into the source. Only the source's layout code (classes, feature
prefixes, features) changes; hand-written features lankafea doesn't own are kept. Commit the
result: the build itself doesn't need lankafea.

```sh
make features
make features LANKAFEA="path/to/lankafea"     # another lankafea
```

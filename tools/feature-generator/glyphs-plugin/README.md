# Lanka Features — Glyphs 3 plugin

Runs the [`lankafea`](..) generator inside Glyphs: Sinhala /
Tamil OpenType features, gated on the glyphs actually in the font. The plugin
bundles `lankafea` (and PyYAML), so there is nothing to `pip install`.

## Install

```sh
./build.sh --install    # then restart Glyphs
```

## Use — Glyph menu ▸ Lanka Features

| Item | What it does |
|---|---|
| Generate Features Now | Builds and writes features into the front font |
| Auto-Generate When Glyphs Change | Per-font toggle; regenerates when glyphs are added, removed, renamed or re-encoded (checked about once a second, plus on open/save/switch) |
| Dependency Report | Prints the blockers / orphans report in the Macro window |
| Feature Assignments (dlig / ss)… | Opens the assignment dialog (below); the menu title shows how many assignments are active |
| Add ZWJ / ZWNJ Control Glyphs | Inserts the zero-width controls the rules depend on |
| Script / Sinhala Level | Override auto-detection and pick the glyphset tier (0–3) |

Settings live in the font (`userData["com.mooniak.lankafea"]`), so they travel
with the `.glyphspackage` — nothing is stored in app preferences.

## Feature Assignments

Route generated rules into `dlig`, `hlig`, `liga`, `clig`, `calt` or `ss01`–`ss20`.

* **Rule groups tab** — every lookup the generator produced (`TouchLigatures`,
  `RakarLigatures`, `VowelLig_abvs`, `PureConjuncts`, …). Pick a target per row,
  and *Move* (leaves its normal feature) or *Copy* (stays and also appears in
  the new feature). Multi-select + **Set** assigns several at once. A group's
  “Rules usable” is how many of its candidate rules the font's glyphs satisfy.
* **Alternates tab** — glyphs named `base.alt`, `base.alt2`, … form alternate
  indices. Index N feeds `ssNN` by default; send an index to another tag, or to
  *aalt only*. Two indices on one tag stay separate lookups, lower index first.

The footer flags tags you hand-wrote (generated code for them is kept out unless
listed under *Replace Hand-Written Features…*). After a generate, notes such as
“RakarLigatures now in dlig forms glyphs VowelLig_psts needs” appear in the
Macro window: a moved group's output only exists while its new feature is on.

CLI equivalent: `--assign FILE.json` with
`{"groups": [{"group": "TouchLigatures", "to": "dlig", "mode": "move"}], "alts": {"2": "ss07"}}`.

Hand-written features are never overwritten: only code carrying the
`# lankafea:generated` marker is replaced. If you hand-wrote a tag the
generator also emits, yours is kept and the notification says so.

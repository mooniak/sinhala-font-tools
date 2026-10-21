# model — the Sinhala design models

The hand-editable sources of truth. Everything else in this repo (the
explainer pages, Glyphs filters, plugins, `tools/_generated/` data) is derived
from these files. Edit here, then regenerate.

| File | What it models | Seeded / checked by |
|---|---|---|
| [`sinhala-design-dependencies.yaml`](sinhala-design-dependencies.yaml) | The design-stages model: metrics, skeletons, elements, spacing classes, mark systems, stages, every glyph with its parents and schedule. The root model. | [`tools/design-stages/build.js`](../tools/design-stages/) validates it |
| [`sinhala-spacing.yaml`](sinhala-spacing.yaml) | The spacing scheme: each glyph's left/right class and sidebearing relationship, applied to sources as Glyphs metrics keys. | [`tools/spacing-map`](../tools/spacing-map/) `build-map` (from the model) |
| [`sinhala-composites.yaml`](sinhala-composites.yaml) | Which glyphs are assembled from components, which stay drawn and why, and what is awaiting review. | [`tools/composite-map`](../tools/composite-map/) (from the model + reference fonts) |

[`sinhala-anatomy.md`](sinhala-anatomy.md) is the letterform vocabulary
(akshi, pāsha, grantika, …) the models' skeletons and elements are named from.

```
sinhala-design-dependencies.yaml ──┬─► sinhala-spacing.yaml
                                   └─► sinhala-composites.yaml
```

After editing any of them, rerun the generators listed in the
[top-level README](../README.md) so the derived files stay in step.

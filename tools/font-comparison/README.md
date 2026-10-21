# Font Comparison

Browser tool for side-by-side rendering comparison across fonts: gallery,
thumbnail and compare views, with adjustable size, letter spacing and tile
spacing. Static, no build step — open `index.html` in a browser.

Drag and drop `.ttf`/`.otf`/`.woff`/`.woff2` files onto the page to add fonts
for the session (kept in `localStorage`, not uploaded anywhere).

## Default fonts

[`default-fonts.js`](default-fonts.js) lists the fonts loaded automatically
when the page opens. It ships with Hodipotha (the repo's reference font), Sinhala Sangam MN, and four
Latin system fonts (Arial, Times New Roman, Helvetica, Georgia), so the page
works with nothing to set up.

Fonts are drawn by the browser's own text shaper (via `FontFace`), so Sinhala
conjuncts, vowel signs and OpenType features render correctly.

Most Sinhala comparison fonts are commercial or otherwise not freely
redistributable, so they aren't vendored into this repo. To compare your own
collection by default instead of dragging files in every time:

1. Drop your font files into `tools/font-comparison/fonts/` (gitignored).
2. Copy [`default-fonts.local.example.js`](default-fonts.local.example.js) to
   `default-fonts.local.js` (also gitignored) and edit the list to match your
   files.

`default-fonts.local.js` is merged with `default-fonts.js` automatically if
present; if it's missing, the page falls back to the system fonts only, with
no error.
